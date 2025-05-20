import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Any
from solana.rpc.async_api import AsyncClient
from solana.publickey import PublicKey

# Importer la configuration
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
        """
        Initialise le trader
        
        Args:
            config_data: Configuration du trader (optionnel)
        """
        # Charger la configuration si non fournie
        if config_data is None:
            self.config = load_config()
        else:
            self.config = config_data
        
        # Initialiser le client RPC
        self.rpc_url = self.config.get("RPC_HTTP_ENDPOINT", "https://api.mainnet-beta.solana.com")
        self.client = AsyncClient(self.rpc_url)
        
        # Charger la clé privée du wallet
        self.wallet_private_key = self.config.get("WALLET_PRIVATE_KEY", "")
        self.wallet_address = self.config.get("WALLET_ADDRESS", "")
        
        # Paramètres de trading
        self.default_slippage = self.config.get("DEFAULT_SLIPPAGE_TOLERANCE", 0.03)
        
        # Routeur d'ordres
        self.order_router = None
        
        logger.info("Trader réel initialisé")
    
    def set_order_router(self, router):
        """
        Définit le routeur d'ordres
        
        Args:
            router: Routeur d'ordres
        """
        self.order_router = router
    
    async def buy_token(self, token_address: str, amount_sol: float, 
                       slippage_percent: float = None) -> Dict[str, Any]:
        """
        Achète un token
        
        Args:
            token_address: Adresse du token à acheter
            amount_sol: Montant en SOL à utiliser
            slippage_percent: Pourcentage de slippage toléré
            
        Returns:
            Résultat de la transaction
        """
        logger.info(f"Achat de token {token_address} pour {amount_sol} SOL")
        
        if not self.wallet_private_key:
            return {
                "success": False,
                "error": "Wallet private key not configured"
            }
        
        if slippage_percent is None:
            slippage_percent = self.default_slippage * 100
        
        try:
            # Convertir le montant SOL en lamports
            amount_lamports = int(amount_sol * 1_000_000_000)
            
            # Utiliser le routeur d'ordres si disponible
            if self.order_router:
                # SOL mint address
                sol_mint = "So11111111111111111111111111111111111111112"
                
                # Obtenir le meilleur itinéraire
                route = await self.order_router.get_best_route(
                    input_mint=sol_mint,
                    output_mint=token_address,
                    amount_in=amount_lamports,
                    slippage=slippage_percent / 100
                )
                
                if not route:
                    return {
                        "success": False,
                        "error": "No route found"
                    }
                
                # Exécuter la transaction
                tx_result = await self._execute_transaction(route.tx_data)
                
                if not tx_result["success"]:
                    return tx_result
                
                # Calculer le prix d'achat
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
                # Pas de routeur d'ordres, utiliser Jupiter directement
                logger.warning("No order router available, using default Jupiter route")
                
                # Implémentation simplifiée pour l'exemple
                # Dans une implémentation réelle, il faudrait utiliser l'API Jupiter
                
                return {
                    "success": False,
                    "error": "Order router not configured"
                }
        
        except Exception as e:
            logger.error(f"Error buying token: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def sell_token(self, token_address: str, token_amount: float, 
                        slippage_percent: float = None) -> Dict[str, Any]:
        """
        Vend un token
        
        Args:
            token_address: Adresse du token à vendre
            token_amount: Montant du token à vendre
            slippage_percent: Pourcentage de slippage toléré
            
        Returns:
            Résultat de la transaction
        """
        logger.info(f"Vente de {token_amount} tokens {token_address}")
        
        if not self.wallet_private_key:
            return {
                "success": False,
                "error": "Wallet private key not configured"
            }
        
        if slippage_percent is None:
            slippage_percent = self.default_slippage * 100
        
        try:
            # Utiliser le routeur d'ordres si disponible
            if self.order_router:
                # SOL mint address
                sol_mint = "So11111111111111111111111111111111111111112"
                
                # Obtenir le meilleur itinéraire
                route = await self.order_router.get_best_route(
                    input_mint=token_address,
                    output_mint=sol_mint,
                    amount_in=int(token_amount),
                    slippage=slippage_percent / 100
                )
                
                if not route:
                    return {
                        "success": False,
                        "error": "No route found"
                    }
                
                # Exécuter la transaction
                tx_result = await self._execute_transaction(route.tx_data)
                
                if not tx_result["success"]:
                    return tx_result
                
                # Calculer le prix de vente
                sol_amount = route.out_amount / 1_000_000_000  # Convertir lamports en SOL
                price_per_token = sol_amount / token_amount if token_amount > 0 else 0
                
                return {
                    "success": True,
                    "transaction_id": tx_result["transaction_id"],
                    "sol_amount": sol_amount,
                    "price": price_per_token,
                    "token_amount": token_amount,
                    "route": route.provider
                }
            
            else:
                # Pas de routeur d'ordres, utiliser Jupiter directement
                logger.warning("No order router available, using default Jupiter route")
                
                # Implémentation simplifiée pour l'exemple
                # Dans une implémentation réelle, il faudrait utiliser l'API Jupiter
                
                return {
                    "success": False,
                    "error": "Order router not configured"
                }
        
        except Exception as e:
            logger.error(f"Error selling token: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_token_balance(self, token_address: str) -> float:
        """
        Récupère le solde d'un token
        
        Args:
            token_address: Adresse du token
            
        Returns:
            Solde du token
        """
        if not self.wallet_address:
            return 0
        
        try:
            # Implémentation simplifiée pour l'exemple
            # Dans une implémentation réelle, il faudrait interroger la blockchain
            
            return 0
        
        except Exception as e:
            logger.error(f"Error getting token balance: {e}")
            return 0
    
    async def get_sol_balance(self) -> float:
        """
        Récupère le solde SOL
        
        Returns:
            Solde SOL
        """
        if not self.wallet_address:
            return 0
        
        try:
            response = await self.client.get_balance(self.wallet_address)
            
            if response["result"]["value"] is not None:
                return response["result"]["value"] / 1_000_000_000  # Convertir lamports en SOL
            
            return 0
        
        except Exception as e:
            logger.error(f"Error getting SOL balance: {e}")
            return 0
    
    async def _execute_transaction(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exécute une transaction
        
        Args:
            tx_data: Données de la transaction
            
        Returns:
            Résultat de la transaction
        """
        try:
            # Implémentation simplifiée pour l'exemple
            # Dans une implémentation réelle, il faudrait signer et envoyer la transaction
            
            # Simuler une transaction réussie
            transaction_id = "simulated_transaction_id"
            
            return {
                "success": True,
                "transaction_id": transaction_id
            }
        
        except Exception as e:
            logger.error(f"Error executing transaction: {e}")
            return {
                "success": False,
                "error": str(e)
            }
