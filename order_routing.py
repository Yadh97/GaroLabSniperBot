"""
Module de routage intelligent des ordres pour GaroLabSniperBot
Optimise l'exécution des transactions pour obtenir le meilleur prix et minimiser les coûts
"""

import asyncio
import time
import json
import logging
import requests
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
import os
import base64
from decimal import Decimal
import math
import random

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("order_routing")

@dataclass
class RouteInfo:
    """Information sur un itinéraire d'exécution"""
    provider: str
    out_amount: int
    price_impact: float
    fee: float
    tx_data: Dict[str, Any]
    gas_estimate: int
    priority_fee: int
    total_cost_usd: float
    score: float = 0.0

@dataclass
class ExecutionResult:
    """Résultat d'une exécution de transaction"""
    success: bool
    transaction_id: str = ""
    error: str = ""
    price: float = 0.0
    amount_in: float = 0.0
    amount_out: float = 0.0
    fee_paid: float = 0.0
    execution_time: float = 0.0
    provider: str = ""
    route_score: float = 0.0

class OrderRouter:
    """
    Routeur intelligent d'ordres
    Trouve le meilleur itinéraire d'exécution pour les transactions
    """
    
    def __init__(self, config: Dict[str, Any], rpc_client=None):
        self.config = config
        self.rpc_client = rpc_client
        
        # Paramètres configurables
        self.max_routes_to_check = config.get("MAX_ROUTES_TO_CHECK", 3)
        self.max_slippage = config.get("MAX_SLIPPAGE", 0.03)  # 3%
        self.default_priority_fee = config.get("DEFAULT_PRIORITY_FEE", 10000)  # 0.00001 SOL
        self.execution_timeout = config.get("EXECUTION_TIMEOUT", 60)  # 60 secondes
        self.cache_ttl = config.get("ROUTE_CACHE_TTL", 30)  # 30 secondes
        
        # Cache des routes
        self.route_cache = {}  # {cache_key: {timestamp, routes}}
        
        # Statistiques d'exécution
        self.execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_saved_usd": 0.0,
            "provider_stats": {}
        }
        
        # Initialiser les fournisseurs de liquidité
        self._init_providers()
        
        logger.info(f"Initialized OrderRouter with {len(self.providers)} providers")
    
    def _init_providers(self):
        """Initialise les fournisseurs de liquidité"""
        self.providers = {
            "jupiter": {
                "enabled": self.config.get("ENABLE_JUPITER", True),
                "weight": self.config.get("JUPITER_WEIGHT", 1.0),
                "api_url": "https://quote-api.jup.ag/v6",
                "api_key": self.config.get("JUPITER_API_KEY", ""),
                "success_rate": 0.95,
                "executions": 0
            },
            "raydium": {
                "enabled": self.config.get("ENABLE_RAYDIUM", True),
                "weight": self.config.get("RAYDIUM_WEIGHT", 0.9),
                "api_url": "https://api.raydium.io/v2",
                "api_key": self.config.get("RAYDIUM_API_KEY", ""),
                "success_rate": 0.9,
                "executions": 0
            },
            "orca": {
                "enabled": self.config.get("ENABLE_ORCA", True),
                "weight": self.config.get("ORCA_WEIGHT", 0.85),
                "api_url": "https://api.orca.so",
                "api_key": self.config.get("ORCA_API_KEY", ""),
                "success_rate": 0.85,
                "executions": 0
            },
            "openbook": {
                "enabled": self.config.get("ENABLE_OPENBOOK", False),
                "weight": self.config.get("OPENBOOK_WEIGHT", 0.8),
                "api_url": "https://api.openbook-solana.com/v1",
                "api_key": self.config.get("OPENBOOK_API_KEY", ""),
                "success_rate": 0.8,
                "executions": 0
            }
        }
    
    async def get_best_swap_route(self, input_mint: str, output_mint: str, 
                                 amount_in: int, slippage: float = None) -> Optional[RouteInfo]:
        """
        Trouve le meilleur itinéraire pour un swap
        
        Args:
            input_mint: Adresse du token d'entrée
            output_mint: Adresse du token de sortie
            amount_in: Montant d'entrée en unités natives (lamports pour SOL)
            slippage: Tolérance de slippage (utilise la valeur par défaut si None)
            
        Returns:
            Meilleur itinéraire ou None si aucun itinéraire trouvé
        """
        if slippage is None:
            slippage = self.max_slippage
        
        # Vérifier le cache
        cache_key = f"{input_mint}:{output_mint}:{amount_in}:{slippage}"
        cached_routes = self._get_from_cache(cache_key)
        
        if cached_routes:
            logger.debug(f"Using cached routes for {cache_key}")
            return cached_routes[0]  # Retourner le meilleur itinéraire
        
        # Récupérer les itinéraires de tous les fournisseurs
        routes = []
        tasks = []
        
        for provider_name, provider_info in self.providers.items():
            if provider_info["enabled"]:
                task = self._get_route_from_provider(
                    provider_name, input_mint, output_mint, amount_in, slippage
                )
                tasks.append(task)
        
        if not tasks:
            logger.error("No enabled providers available")
            return None
        
        # Exécuter toutes les requêtes en parallèle
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error getting route: {result}")
            elif result:
                routes.append(result)
        
        if not routes:
            logger.error(f"No valid routes found for {input_mint} -> {output_mint}")
            return None
        
        # Calculer un score pour chaque itinéraire
        for route in routes:
            route.score = self._calculate_route_score(route)
        
        # Trier par score décroissant
        routes.sort(key=lambda x: x.score, reverse=True)
        
        # Mettre en cache
        self._add_to_cache(cache_key, routes)
        
        best_route = routes[0]
        logger.info(f"Best route: {best_route.provider} (Score: {best_route.score:.2f}, "
                   f"Out: {best_route.out_amount}, Impact: {best_route.price_impact*100:.2f}%)")
        
        return best_route
    
    async def execute_swap(self, route: RouteInfo, wallet_keypair: Any = None) -> ExecutionResult:
        """
        Exécute un swap en utilisant l'itinéraire spécifié
        
        Args:
            route: Itinéraire à utiliser
            wallet_keypair: Keypair du wallet (si None, utilise le wallet par défaut)
            
        Returns:
            Résultat de l'exécution
        """
        if not self.rpc_client:
            return ExecutionResult(
                success=False,
                error="No RPC client available"
            )
        
        start_time = time.time()
        
        try:
            # Optimiser le timing d'exécution
            optimized_tx = await self._optimize_transaction_timing(route.tx_data)
            
            # Exécuter la transaction
            tx_result = await self._execute_transaction(optimized_tx, wallet_keypair)
            
            execution_time = time.time() - start_time
            
            if tx_result.get("success"):
                # Mettre à jour les statistiques
                self._update_execution_stats(route, True, execution_time)
                
                return ExecutionResult(
                    success=True,
                    transaction_id=tx_result.get("transaction_id", ""),
                    price=tx_result.get("price", 0.0),
                    amount_in=tx_result.get("amount_in", 0.0),
                    amount_out=tx_result.get("amount_out", 0.0),
                    fee_paid=tx_result.get("fee_paid", 0.0),
                    execution_time=execution_time,
                    provider=route.provider,
                    route_score=route.score
                )
            else:
                # Mettre à jour les statistiques
                self._update_execution_stats(route, False, execution_time)
                
                return ExecutionResult(
                    success=False,
                    error=tx_result.get("error", "Unknown error"),
                    execution_time=execution_time,
                    provider=route.provider
                )
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            # Mettre à jour les statistiques
            self._update_execution_stats(route, False, execution_time)
            
            logger.error(f"Error executing swap: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
                provider=route.provider
            )
    
    async def execute_swap_with_retry(self, input_mint: str, output_mint: str, 
                                     amount_in: int, slippage: float = None, 
                                     max_retries: int = 2) -> ExecutionResult:
        """
        Exécute un swap avec retry automatique en cas d'échec
        
        Args:
            input_mint: Adresse du token d'entrée
            output_mint: Adresse du token de sortie
            amount_in: Montant d'entrée en unités natives
            slippage: Tolérance de slippage
            max_retries: Nombre maximum de tentatives
            
        Returns:
            Résultat de l'exécution
        """
        retries = 0
        
        while retries <= max_retries:
            # Trouver le meilleur itinéraire
            route = await self.get_best_swap_route(input_mint, output_mint, amount_in, slippage)
            
            if not route:
                return ExecutionResult(
                    success=False,
                    error="No valid route found"
                )
            
            # Exécuter le swap
            result = await self.execute_swap(route)
            
            if result.success:
                return result
            
            # En cas d'échec, réessayer avec un autre itinéraire
            retries += 1
            
            if retries <= max_retries:
                logger.warning(f"Swap failed, retrying ({retries}/{max_retries}): {result.error}")
                
                # Attendre un peu avant de réessayer
                await asyncio.sleep(1)
                
                # Augmenter légèrement le slippage pour la prochaine tentative
                if slippage:
                    slippage = min(slippage * 1.2, self.max_slippage * 1.5)
        
        return result  # Retourner le dernier résultat (échec)
    
    async def _get_route_from_provider(self, provider_name: str, input_mint: str, 
                                      output_mint: str, amount_in: int, 
                                      slippage: float) -> Optional[RouteInfo]:
        """
        Récupère un itinéraire depuis un fournisseur spécifique
        
        Args:
            provider_name: Nom du fournisseur
            input_mint: Adresse du token d'entrée
            output_mint: Adresse du token de sortie
            amount_in: Montant d'entrée en unités natives
            slippage: Tolérance de slippage
            
        Returns:
            Informations sur l'itinéraire ou None en cas d'erreur
        """
        provider = self.providers.get(provider_name)
        if not provider:
            return None
        
        try:
            if provider_name == "jupiter":
                return await self._get_jupiter_route(input_mint, output_mint, amount_in, slippage)
            elif provider_name == "raydium":
                return await self._get_raydium_route(input_mint, output_mint, amount_in, slippage)
            elif provider_name == "orca":
                return await self._get_orca_route(input_mint, output_mint, amount_in, slippage)
            elif provider_name == "openbook":
                return await self._get_openbook_route(input_mint, output_mint, amount_in, slippage)
            else:
                logger.warning(f"Unknown provider: {provider_name}")
                return None
        
        except Exception as e:
            logger.error(f"Error getting route from {provider_name}: {e}")
            return None
    
    async def _get_jupiter_route(self, input_mint: str, output_mint: str, 
                               amount_in: int, slippage: float) -> Optional[RouteInfo]:
        """
        Récupère un itinéraire depuis Jupiter
        
        Args:
            input_mint: Adresse du token d'entrée
            output_mint: Adresse du token de sortie
            amount_in: Montant d'entrée en unités natives
            slippage: Tolérance de slippage
            
        Returns:
            Informations sur l'itinéraire ou None en cas d'erreur
        """
        provider = self.providers["jupiter"]
        api_url = f"{provider['api_url']}/quote"
        
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_in),
            "slippageBps": int(slippage * 10000)
        }
        
        headers = {}
        if provider["api_key"]:
            headers["Authorization"] = f"Bearer {provider['api_key']}"
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.get(api_url, params=params, headers=headers, timeout=5)
            )
            
            if response.status_code != 200:
                logger.error(f"Jupiter API error: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            
            # Extraire les informations de l'itinéraire
            out_amount = int(data.get("outAmount", 0))
            price_impact = float(data.get("priceImpactPct", 0)) / 100
            
            # Récupérer les données de transaction
            swap_url = f"{provider['api_url']}/swap"
            swap_params = {
                "quoteResponse": data
            }
            
            swap_response = await loop.run_in_executor(
                None, 
                lambda: requests.post(swap_url, json=swap_params, headers=headers, timeout=5)
            )
            
            if swap_response.status_code != 200:
                logger.error(f"Jupiter swap API error: {swap_response.status_code} - {swap_response.text}")
                return None
            
            swap_data = swap_response.json()
            
            # Estimer les frais de gaz
            gas_estimate = 5000  # Valeur par défaut
            if "priorityFee" in swap_data:
                priority_fee = int(swap_data["priorityFee"])
            else:
                priority_fee = self.default_priority_fee
            
            # Estimer le coût total en USD
            sol_price_usd = await self._get_sol_price_usd()
            fee_lamports = gas_estimate + priority_fee
            fee_sol = fee_lamports / 1_000_000_000
            total_cost_usd = fee_sol * sol_price_usd
            
            return RouteInfo(
                provider="jupiter",
                out_amount=out_amount,
                price_impact=price_impact,
                fee=fee_sol,
                tx_data=swap_data,
                gas_estimate=gas_estimate,
                priority_fee=pr
(Content truncated due to size limit. Use line ranges to read in chunks)
