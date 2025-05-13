import time
import logging
from dataclasses import dataclass, field

import config
import filters
from solana.rpc.api import Client
from solana.rpc.core import RPCException

@dataclass
class TokenInfo:
    """Data class to hold information about a token and its relevant metrics."""
    mint_address: str
    symbol: str = "<unknown>"
    detected_time: float = field(default_factory=time.time)
    liquidity_usd: float = 0.0
    price: float = 0.0
    total_supply: float = 0.0
    fdv: float = 0.0
    mint_authority: str = None
    freeze_authority: str = None

class TokenMonitor:
    def __init__(self, token_cache):
        """
        Monitor that processes tokens from the token_cache, applies filters, 
        and triggers actions (e.g., buy) for tokens that pass all filters.
        """
        self.token_cache = token_cache
        # Dictionary to keep track of tokens under monitoring (address -> TokenInfo)
        self.tokens = {}
        # Initialize RPC client for Solana calls
        self.client = Client(config.RPC_HTTP_ENDPOINT, commitment=config.COMMITMENT)
        # Track tokens that are pending recheck (not yet passed filters but within recheck window)
        self.pending_tokens = {}

    def _fetch_token_data(self, mint_address):
        """
        Fetch necessary data for a given token mint address from the Solana RPC.
        Returns a TokenInfo object with filled in fields. Uses retry logic for robustness.
        """
        token = TokenInfo(mint_address=mint_address)
        try:
            # Fetch mint account info (includes total supply, decimals, and authorities)
            account_info = filters._rpc_call_with_retry(self.client.get_account_info, mint_address, {"encoding": "jsonParsed"})
        except Exception as e:
            logging.error(f"RPC error fetching account info for token {mint_address}: {e}")
            return None
        # Parse mint account data if available
        value = account_info.get("result", {}).get("value")
        if value and value.get("data"):
            try:
                # If using jsonParsed, the data should include the parsed info
                parsed = value["data"]["parsed"]["info"]
                supply_str = parsed.get("supply")
                decimals = int(parsed.get("decimals", 0))
                # supply_str might be a raw integer string (total tokens * 10^decimals)
                if supply_str is not None:
                    token.total_supply = float(supply_str) / (10 ** decimals)
                # Mint and freeze authority
                token.mint_authority = parsed.get("mintAuthority")
                token.freeze_authority = parsed.get("freezeAuthority")
            except Exception as parse_error:
                logging.error(f"Error parsing account info for token {mint_address}: {parse_error}")
        else:
            logging.warning(f"No account info found for token {mint_address}.")
        # Fetch token supply via RPC (could also use get_token_supply for easier supply retrieval)
        if token.total_supply == 0:
            try:
                supply_resp = filters._rpc_call_with_retry(self.client.get_token_supply, mint_address)
                if "result" in supply_resp and supply_resp["result"]["value"]:
                    supply_info = supply_resp["result"]["value"]
                    amount = float(supply_info.get("uiAmount", 0))
                    token.total_supply = amount
                else:
                    logging.warning(f"Token {mint_address}: Unable to fetch total supply.")
            except Exception as e:
                logging.error(f"RPC error fetching token supply for {mint_address}: {e}")
        # Attempt to fetch token symbol and name via token metadata program (if needed)
        # (This part depends on whether metadata is available. It may require an additional RPC call to fetch metadata PDA.)
        # For simplicity, not implemented here. We'll rely on the mint address or any provided symbol from elsewhere.

        # Fetch liquidity and price information (assuming token pair with USDC or SOL is known via cache or detection event)
        # This likely requires knowing the pool address or using a Dex API. 
        # Here we assume token_cache or listener provided initial liquidity info, or a separate method exists.
        # We'll check if token_cache has liquidity info stored (e.g., token_cache might store a struct with liquidity).
        initial_data = getattr(self.token_cache, "initial_data", None)
        if initial_data and mint_address in initial_data:
            # Use any precomputed liquidity/price info if available
            token.liquidity_usd = initial_data[mint_address].get("liquidity_usd", 0.0)
            token.price = initial_data[mint_address].get("price", 0.0)
        else:
            # If no initial data, we may need to compute or fetch from an API (not fully implemented here).
            token.liquidity_usd = 0.0
            token.price = 0.0
        # Calculate FDV if possible
        if token.total_supply and token.price:
            token.fdv = token.total_supply * token.price
        else:
            token.fdv = 0.0

        # Log some details about the fetched token data
        logging.debug(f"Fetched data for token {mint_address}: supply={token.total_supply}, liquidity_usd={token.liquidity_usd}, price={token.price}, FDV={token.fdv}, mint_auth={token.mint_authority}, freeze_auth={token.freeze_authority}")
        return token

    def run(self):
        """Continuously monitors new tokens from the cache and applies filters."""
        logging.info("TokenMonitor running. Waiting for new tokens to process...")
        while True:
            try:
                # Get next token to process: first check pending tokens, then new tokens from cache
                mint_address = None
                token_obj = None
                # If any pending tokens exist, pick one to recheck (round-robin or any order)
                if self.pending_tokens:
                    # Take one pending token (could iterate through all in each loop as well)
                    mint_address, token_obj = next(iter(self.pending_tokens.items()))
                    # Remove it from pending list to process now
                    self.pending_tokens.pop(mint_address, None)
                    logging.debug(f"Rechecking token {mint_address} after initial rejection...")
                else:
                    # No pending token ready, get new token from cache (non-blocking)
                    mint_address = self.token_cache.get_token()
                if mint_address is None and token_obj is None:
                    # No tokens to process, sleep briefly and continue
                    time.sleep(1)
                    continue

                # If we got an address without a TokenInfo object, fetch its data
                if token_obj is None:
                    logging.info(f"New token detected: {mint_address}. Fetching data and applying filters...")
                    token_obj = self._fetch_token_data(mint_address)
                    if token_obj is None:
                        # Failed to fetch data, skip this token
                        logging.error(f"Skipping token {mint_address} due to data fetch failure.")
                        continue
                    # Store it in internal cache for potential rechecks
                    self.tokens[mint_address] = token_obj

                # Apply filters to the token
                passes = False
                try:
                    passes = filters.basic_filter(token_obj)
                except Exception as e:
                    # Catch any unexpected exceptions during filtering to avoid breaking the loop
                    logging.error(f"Exception during filtering token {mint_address}: {e}", exc_info=True)
                    # If filtering fails unexpectedly, skip further processing of this token for now
                    continue

                if not passes:
                    # Token failed one or more filters. Detailed reason was logged in filters.basic_filter.
                    # Determine if we should keep the token for rechecking later.
                    token_age = time.time() - token_obj.detected_time
                    if token_age < config.RECHECK_WINDOW_SEC:
                        # Within recheck window: keep token for another try later
                        self.pending_tokens[mint_address] = token_obj
                        logging.info(f"Token {token_obj.mint_address} failed filters, will recheck after some time (age {int(token_age)}s, within {config.RECHECK_WINDOW_SEC}s window).")
                    else:
                        # Outside recheck window: give up on this token
                        logging.info(f"Token {token_obj.mint_address} failed filters and exceeded recheck window (age {int(token_age)}s). Skipping permanently.")
                    # Move to next token
                    continue

                # If token passes all filters:
                logging.info(f"[FILTER] PASSED: {token_obj.symbol} (mint {token_obj.mint_address}) - All checks OK. Proceeding to buy logic...")
                # TODO: Implement buying logic (e.g., send transaction to purchase the token)
                # For now, just log that we would trigger a buy.
                try:
                    # Here we would call the trading module or function to execute the buy
                    # e.g., trader.buy_token(token_obj)
                    logging.info(f"Buying token {token_obj.symbol} ({token_obj.mint_address})...")
                except Exception as buy_error:
                    logging.error(f"Error during buy operation for {token_obj.mint_address}: {buy_error}", exc_info=True)
                    # We do not re-add token to pending here, as buy either succeeds or not.

                # After attempting buy, we remove token from monitoring (to avoid duplicate attempts)
                if mint_address in self.tokens:
                    self.tokens.pop(mint_address, None)
                # (Optionally, could keep monitoring token for selling logic, etc., not covered here)

            except Exception as e:
                # Catch-all for any unexpected exceptions in the monitoring loop to prevent crash
                logging.error(f"Unexpected error in TokenMonitor loop: {e}", exc_info=True)
                time.sleep(1)  # small delay to avoid tight error loop
                continue

    def stop(self):
        """Stops the token monitor loop (if needed)."""
        # If we had a loop break condition, we would set it here.
        # This method can set a flag that causes the run loop to exit gracefully.
        logging.info("TokenMonitor stopping (not fully implemented stop mechanism).")
        # (Implementation of stop flag omitted for brevity)
        pass
