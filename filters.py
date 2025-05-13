import time
import logging

import config
# Assuming we have a Solana RPC client instance available for making calls:
from solana.rpc.api import Client
from solana.rpc.core import RPCException

# Initialize a Solana RPC client (synchronous) using the HTTP endpoint
_rpc_client = Client(config.RPC_HTTP_ENDPOINT, commitment=config.COMMITMENT)

def _rpc_call_with_retry(rpc_func, *args, **kwargs):
    """
    Call a Solana RPC function with retries and exponential backoff.
    If an HTTP 429 (Too Many Requests) or similar error occurs, retry with backoff.
    """
    retries = config.RPC_MAX_RETRIES
    base_delay = config.RPC_BACKOFF_FACTOR
    for attempt in range(retries):
        try:
            return rpc_func(*args, **kwargs)
        except Exception as e:
            # Determine if this is a rate limit or transient error
            # Check for HTTP 429 or "Too Many Requests" in exception message
            err_msg = str(e)
            is_rate_limit = ("429" in err_msg) or ("Too Many Requests" in err_msg)
            if is_rate_limit and attempt < retries - 1:
                # Exponential backoff before next retry
                delay = base_delay * (2 ** attempt)
                logging.warning(f"RPC call {rpc_func.__name__} hit rate limit (attempt {attempt+1}/{retries}). "
                                f"Retrying in {delay:.1f}s...")
                time.sleep(delay)
                continue
            # If not a rate limit error or no retries left, log and re-raise
            logging.error(f"RPC call {rpc_func.__name__} failed on attempt {attempt+1}: {e}")
            raise
    # If loop exits without return (shouldn't happen due to raise on last attempt), raise exception
    raise RuntimeError(f"RPC call {rpc_func.__name__} failed after {retries} retries.")

def basic_filter(token):
    """
    Apply a series of basic safety filters to the token.
    Returns True if the token passes all filters, False if any check fails.
    Logs detailed reasons for any failure.
    """
    # Calculate token age in seconds (time since detection/launch)
    current_time = time.time()
    token_age_sec = current_time - token.detected_time if hasattr(token, 'detected_time') else 0

    # 1. Liquidity filter: ensure token has sufficient liquidity in the pool
    if token.liquidity_usd < config.MIN_LIQUIDITY_USD:
        logging.info(f"[FILTER] REJECTED: {token.symbol} - Liquidity {token.liquidity_usd:.2f} < {config.MIN_LIQUIDITY_USD:.2f}")
        return False

    # 2. Fully Diluted Valuation (FDV) filter: ensure FDV is not excessive
    if token.fdv > config.MAX_FDV:
        logging.info(f"[FILTER] REJECTED: {token.symbol} - FDV {token.fdv:.2f} > {config.MAX_FDV:.2f}")
        return False

    # 3. Mint/Freeze authority filter: ensure token mint and freeze authority are renounced (none)
    mint_auth = token.mint_authority
    freeze_auth = token.freeze_authority
    if mint_auth or freeze_auth:
        reasons = []
        if mint_auth:
            reasons.append("mint authority not renounced")
        if freeze_auth:
            reasons.append("freeze authority not renounced")
        logging.info(f"[FILTER] REJECTED: {token.symbol} - " + " and ".join(reasons))
        return False

    # 4. Holder distribution filter: check top holder concentration (more lenient for recent tokens)
    # Determine allowed threshold based on token age
    allowed_percent = config.MAX_HOLDER_PERCENT
    if token_age_sec < 5 * 60:  # token is less than 5 minutes old
        allowed_percent = config.MAX_HOLDER_PERCENT_NEW
    # Ensure we have up-to-date top holder info (this may require an RPC call)
    try:
        largest_accounts = _rpc_call_with_retry(_rpc_client.get_token_largest_accounts, token.mint_address)
    except Exception as e:
        logging.error(f"Failed to fetch holder distribution for {token.symbol}: {e}")
        return False
    # Parse the largest account info to get the top holder amount
    if "result" in largest_accounts and largest_accounts["result"]["value"]:
        top_holder_amount = float(largest_accounts["result"]["value"][0]["uiAmount"])
        total_supply = token.total_supply  # assume this is the full supply in actual tokens (not raw lamports)
        if total_supply <= 0:
            logging.warning(f"{token.symbol} total supply is zero or undefined.")
            return False
        top_holder_percent = (top_holder_amount / total_supply) * 100.0
    else:
        # If we cannot get holder data, treat as fail
        logging.error(f"Could not retrieve largest holders for token {token.symbol}.")
        return False
    # Apply the concentration threshold check
    if top_holder_percent > allowed_percent:
        # Determine reason message (lenient or normal)
        if token_age_sec < 5 * 60:
            # Token is new, using lenient threshold
            logging.info(f"[FILTER] REJECTED: {token.symbol} - Holder concentration {top_holder_percent:.2f}% > allowed {allowed_percent:.2f}% (lenient for new token)")
        else:
            logging.info(f"[FILTER] REJECTED: {token.symbol} - Holder concentration {top_holder_percent:.2f}% > allowed {allowed_percent:.2f}%")
        return False

    # All checks passed
    return True
