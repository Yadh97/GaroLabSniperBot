# Filename: trader.py

import asyncio
import logging
import time
import json
from typing import Dict, Any
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from config import load_config

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trader")

class Trader:
    """
    Classe de trading réel
    Exécute les opérations d'achat et de vente sur la blockchain
    """
    
    def __init__(self, config_data=None):
        if config_data is None:
            self.config = load_config()
        else:
            self.config = config_data
        
        self.rpc_url = self.config.get("RPC_HTTP_ENDPOINT", "https://api.mainnet-beta.solana.com")
        self.client = AsyncClient(self.rpc_url)

        self.wallet_private_key = self.config.get("WALLET_PRIVATE_KEY", "")
        self.wallet_address = self.config.get("WALLET_ADDRESS", "")

        self.default_slippage = self.config.get("DEFAULT_SLIPPAGE_TOLERANCE", 0.03)
        self.order_router = None

        logger.info("Trader réel initialisé")

    def set_order_router(self, router):
        self.order_router = router

    async def buy_token(self, token_address: str, amount_sol: float, 
                        slippage_percent: float = None) -> Dict[str, Any]:
        logger.info(f"Achat de token {token_address} pour {amount_sol} SOL")

        if not self.wallet_private_key:
            return {"success": False, "error": "Wallet private key not configured"}

        if slippage_percent is None:
            slippage_percent = self.default_slippage * 100

        try:
            amount_lamports = int(amount_sol * 1_000_000_000)
            if self.order_router:
                sol_mint = "So11111111111111111111111111111111111111112"

                route = await self.order_router.get_best_route(
                    input_mint=sol_mint,
                    output_mint=token_address,
                    amount_in=amount_lamports,
                    slippage=slippage_percent / 100
                )

                if not route:
                    return {"success": False, "error": "No route found"}

                tx_result = await self._execute_transaction(route.tx_data)

                if not tx_result["success"]:
                    return tx_result

                token_amount = route.out_amount
                price_per_token = amount_sol / token_amount if token_amount > 0 else 0

                return {
                    "success": True,
                    "transaction_id": tx_result["transaction_id"],
                    "token_amount": token_amount,
                    "price": price_per_token,
                    "amount_sol": amount_sol,
                    "route": route.provider
                }

            else:
                logger.warning("No order router available, using default Jupiter route")
                return {"success": False, "error": "Order router not configured"}

        except Exception as e:
            logger.error(f"Error buying token: {e}")
            return {"success": False, "error": str(e)}

    async def sell_token(self, token_address: str, token_amount: float, 
                         slippage_percent: float = None) -> Dict[str, Any]:
        logger.info(f"Vente de {token_amount} tokens {token_address}")

        if not self.wallet_private_key:
            return {"success": False, "error": "Wallet private key not configured"}

        if slippage_percent is None:
            slippage_percent = self.default_slippage * 100

        try:
            if self.order_router:
                sol_mint = "So11111111111111111111111111111111111111112"

                route = await self.order_router.get_best_route(
                    input_mint=token_address,
                    output_mint=sol_mint,
                    amount_in=int(token_amount),
                    slippage=slippage_percent / 100
                )

                if not route:
                    return {"success": False, "error": "No route found"}

                tx_result = await self._execute_transaction(route.tx_data)

                if not tx_result["success"]:
                    return tx_result

                sol_amount = route.out_amount / 1_000_000_000
                price_per_token = sol_amount / token_amount if token_amount > 0 else 0

                return {
                    "success": True,
                    "transaction_id": tx_result["transaction_id"],
