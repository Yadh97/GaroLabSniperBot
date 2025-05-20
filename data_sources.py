"""
Module de sources de données pour GaroLabSniperBot
Fournit des interfaces pour récupérer des informations sur les tokens depuis diverses sources
"""

import asyncio
import aiohttp
import json
import logging
import time
import random
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass
import os
import re
from datetime import datetime, timedelta

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime )s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("data_sources")

@dataclass
class TokenInfo:
    """Informations sur un token"""
    address: str
    symbol: str
    name: str
    price_usd: float
    liquidity_usd: float
    fdv: float
    holder_count: int = 0
    top_holders: List[Dict[str, Any]] = None
    creation_time: float = 0
    volume_24h: float = 0
    price_change_24h: float = 0
    social_mentions: int = 0
    source: str = ""
    extra_data: Dict[str, Any] = None

class DataSource:
    """
    Source de données pour les tokens
    Fournit des méthodes pour récupérer des informations sur les tokens
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Paramètres configurables
        self.max_tokens_per_scan = config.get("MAX_TOKENS_PER_SCAN", 50)
        self.cache_ttl = config.get("TOKEN_CACHE_TTL", 300)  # 5 minutes
        self.min_liquidity = config.get("MIN_LIQUIDITY_USD", 10000)
        
        # Cache des tokens
        self.token_cache = {}  # {token_address: {timestamp, data}}
        
        # Clés API
        self.birdeye_api_key = config.get("BIRDEYE_API_KEY", "")
        self.solscan_api_key = config.get("SOLSCAN_API_KEY", "")
        
        # Dernière mise à jour
        self.last_update_time = 0
        self.last_processed_tokens = set()
        
        # Sources de données
        self.sources = {
            "pump_fun": {
                "enabled": config.get("ENABLE_PUMP_FUN", True),
                "weight": config.get("PUMP_FUN_WEIGHT", 1.0),
                "url": "https://pump.fun/api/tokens/new",
                "last_update": 0
            },
            "birdeye": {
                "enabled": config.get("ENABLE_BIRDEYE", True ),
                "weight": config.get("BIRDEYE_WEIGHT", 0.9),
                "url": "https://public-api.birdeye.so/defi/new_tokens",
                "last_update": 0
            },
            "dexscreener": {
                "enabled": config.get("ENABLE_DEXSCREENER", True ),
                "weight": config.get("DEXSCREENER_WEIGHT", 0.8),
                "url": "https://api.dexscreener.com/latest/dex/tokens/solana",
                "last_update": 0
            },
            "solscan": {
                "enabled": config.get("ENABLE_SOLSCAN", True ),
                "weight": config.get("SOLSCAN_WEIGHT", 0.7),
                "url": "https://public-api.solscan.io/token/list",
                "last_update": 0
            },
            "jupiter": {
                "enabled": config.get("ENABLE_JUPITER", True ),
                "weight": config.get("JUPITER_WEIGHT", 0.6),
                "url": "https://price.jup.ag/v4/price",
                "last_update": 0
            }
        }
        
        logger.info(f"Initialized DataSource with {sum(1 for s in self.sources.values( ) if s['enabled'])} enabled sources")
    
    async def get_new_tokens(self) -> List[TokenInfo]:
        """
        Récupère les nouveaux tokens depuis Pump.fun
        
        Returns:
            Liste des nouveaux tokens
        """
        url = "https://pump.fun/api/tokens/new"
        
        try:
            async with aiohttp.ClientSession( ) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Error fetching new tokens: {response.status}")
                        return []
                    
                    data = await response.json()
                    
                    if not data or "data" not in data:
                        logger.error("Invalid response format")
                        return []
                    
                    tokens = []
                    for token_data in data["data"]:
                        # Extraire les informations du token
                        address = token_data.get("address", "")
                        symbol = token_data.get("symbol", "")
                        name = token_data.get("name", "")
                        price_usd = float(token_data.get("price", 0))
                        liquidity_usd = float(token_data.get("liquidity", 0))
                        fdv = float(token_data.get("fdv", 0))
                        
                        # Vérifier les critères minimaux
                        if not address or not symbol or liquidity_usd < self.min_liquidity:
                            continue
                        
                        # Créer l'objet TokenInfo
                        token_info = TokenInfo(
                            address=address,
                            symbol=symbol,
                            name=name,
                            price_usd=price_usd,
                            liquidity_usd=liquidity_usd,
                            fdv=fdv,
                            source="pump_fun"
                        )
                        
                        tokens.append(token_info)
                    
                    logger.info(f"Found {len(tokens)} new tokens from Pump.fun")
                    return tokens
        
        except Exception as e:
            logger.error(f"Error in get_new_tokens: {e}")
            return []
    
    async def get_new_tokens_multi_source(self) -> List[TokenInfo]:
        """
        Récupère les nouveaux tokens depuis plusieurs sources
        
        Returns:
            Liste des nouveaux tokens
        """
        # Vérifier si une mise à jour est nécessaire
        current_time = time.time()
        if current_time - self.last_update_time < 10:  # Limiter à une mise à jour toutes les 10 secondes
            return []
        
        self.last_update_time = current_time
        
        # Récupérer les tokens depuis toutes les sources activées
        tasks = []
        for source_name, source_info in self.sources.items():
            if source_info["enabled"]:
                if source_name == "pump_fun":
                    task = self._get_tokens_from_pump_fun()
                elif source_name == "birdeye":
                    task = self._get_tokens_from_birdeye()
                elif source_name == "dexscreener":
                    task = self._get_tokens_from_dexscreener()
                elif source_name == "solscan":
                    task = self._get_tokens_from_solscan()
                elif source_name == "jupiter":
                    task = self._get_tokens_from_jupiter()
                else:
                    continue
                
                tasks.append(task)
        
        # Exécuter toutes les tâches en parallèle
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Fusionner les résultats
        all_tokens = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error fetching tokens: {result}")
            elif isinstance(result, list):
                all_tokens.extend(result)
        
        # Filtrer les tokens déjà traités
        new_tokens = []
        new_token_addresses = set()
        
        for token in all_tokens:
            if token.address not in self.last_processed_tokens and token.address not in new_token_addresses:
                new_tokens.append(token)
                new_token_addresses.add(token.address)
        
        # Mettre à jour la liste des tokens traités
        self.last_processed_tokens.update(new_token_addresses)
        
        # Limiter le nombre de tokens
        if len(new_tokens) > self.max_tokens_per_scan:
            # Trier par liquidité décroissante
            new_tokens.sort(key=lambda x: x.liquidity_usd, reverse=True)
            new_tokens = new_tokens[:self.max_tokens_per_scan]
        
        logger.info(f"Found {len(new_tokens)} new tokens from multiple sources")
        return new_tokens
    
    async def _get_tokens_from_pump_fun(self) -> List[TokenInfo]:
        """
        Récupère les tokens depuis Pump.fun
        
        Returns:
            Liste des tokens
        """
        source_info = self.sources["pump_fun"]
        url = source_info["url"]
        
        try:
            async with aiohttp.ClientSession( ) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Error fetching tokens from Pump.fun: {response.status}")
                        return []
                    
                    data = await response.json()
                    
                    if not data or "data" not in data:
                        logger.error("Invalid response format from Pump.fun")
                        return []
                    
                    tokens = []
                    for token_data in data["data"]:
                        # Extraire les informations du token
                        address = token_data.get("address", "")
                        symbol = token_data.get("symbol", "")
                        name = token_data.get("name", "")
                        price_usd = float(token_data.get("price", 0))
                        liquidity_usd = float(token_data.get("liquidity", 0))
                        fdv = float(token_data.get("fdv", 0))
                        
                        # Vérifier les critères minimaux
                        if not address or not symbol or liquidity_usd < self.min_liquidity:
                            continue
                        
                        # Créer l'objet TokenInfo
                        token_info = TokenInfo(
                            address=address,
                            symbol=symbol,
                            name=name,
                            price_usd=price_usd,
                            liquidity_usd=liquidity_usd,
                            fdv=fdv,
                            source="pump_fun",
                            extra_data=token_data
                        )
                        
                        tokens.append(token_info)
                    
                    # Mettre à jour la dernière mise à jour
                    source_info["last_update"] = time.time()
                    
                    logger.info(f"Found {len(tokens)} tokens from Pump.fun")
                    return tokens
        
        except Exception as e:
            logger.error(f"Error in _get_tokens_from_pump_fun: {e}")
            return []
    
    async def _get_tokens_from_birdeye(self) -> List[TokenInfo]:
        """
        Récupère les tokens depuis Birdeye
        
        Returns:
            Liste des tokens
        """
        source_info = self.sources["birdeye"]
        url = source_info["url"]
        
        headers = {}
        if self.birdeye_api_key:
            headers["X-API-KEY"] = self.birdeye_api_key
        
        try:
            async with aiohttp.ClientSession( ) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Error fetching tokens from Birdeye: {response.status}")
                        return []
                    
                    data = await response.json()
                    
                    if not data or "data" not in data:
                        logger.error("Invalid response format from Birdeye")
                        return []
                    
                    tokens = []
                    for token_data in data["data"]:
                        # Extraire les informations du token
                        address = token_data.get("address", "")
                        symbol = token_data.get("symbol", "")
                        name = token_data.get("name", "")
                        price_usd = float(token_data.get("price", 0))
                        liquidity_usd = float(token_data.get("liquidity", 0))
                        fdv = float(token_data.get("fdv", 0))
                        volume_24h = float(token_data.get("volume24h", 0))
                        price_change_24h = float(token_data.get("priceChange24h", 0))
                        
                        # Vérifier les critères minimaux
                        if not address or not symbol or liquidity_usd < self.min_liquidity:
                            continue
                        
                        # Créer l'objet TokenInfo
                        token_info = TokenInfo(
                            address=address,
                            symbol=symbol,
                            name=name,
                            price_usd=price_usd,
                            liquidity_usd=liquidity_usd,
                            fdv=fdv,
                            volume_24h=volume_24h,
                            price_change_24h=price_change_24h,
                            source="birdeye",
                            extra_data=token_data
                        )
                        
                        tokens.append(token_info)
                    
                    # Mettre à jour la dernière mise à jour
                    source_info["last_update"] = time.time()
                    
                    logger.info(f"Found {len(tokens)} tokens from Birdeye")
                    return tokens
        
        except Exception as e:
            logger.error(f"Error in _get_tokens_from_birdeye: {e}")
            return []
    
    async def _get_tokens_from_dexscreener(self) -> List[TokenInfo]:
        """
        Récupère les tokens depuis DexScreener
        
        Returns:
            Liste des tokens
        """
        source_info = self.sources["dexscreener"]
        url = source_info["url"]
        
        try:
            async with aiohttp.ClientSession( ) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Error fetching tokens from DexScreener: {response.status}")
                        return []
                    
                    data = await response.json()
                    
                    if not data or "pairs" not in data:
                        logger.error("Invalid response format from DexScreener")
                        return []
                    
                    tokens = []
                    processed_addresses = set()
                    
                    for pair in data["pairs"]:
                        # Extraire les informations du token
                        base_token = pair.get("baseToken", {})
                        address = base_token.get("address", "")
                        
                        # Éviter les doublons
                        if not address or address in processed_addresses:
                            continue
                        
                        processed_addresses.add(address)
                        
                        symbol = base_token.get("symbol", "")
                        name = base_token.get("name", "")
                        price_usd = float(pair.get("priceUsd", 0))
                        liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0))
                        volume_24h = float(pair.get("volume", {}).get("h24", 0))
                        price_change_24h = float(pair.get("priceChange", {}).get("h24", 0))
                        
                        # Vérifier les critères minimaux
                        if not symbol or liquidity_usd < self.min_liquidity:
                            continue
                        
                        # Créer l'objet TokenInfo
                        token_info = TokenInfo(
                            address=address,
                            symbol=symbol,
                            name=name,
                            price_usd=price_usd,
                            liquidity_usd=liquidity_usd,
                            fdv=0,  # Non disponible dans DexScreener
                            volume_24h=volume_24h,
                            price_change_24h=price_change_24h,
                            source="dexscreener",
                            extra_data=pair
                        )
                        
                        tokens.append(token_info)
                    
                    # Mettre à jour la dernière mise à jour
                    source_info["last_update"] = time.time()
                    
                    logger.info(f"Found {len(tokens)} tokens from DexScreener")
                    return tokens
        
        except Exception as e:
            logger.error(f"Error in _get_tokens_from_dexscreener: {e}")
            return []
    
    async def _get_tokens_from_solscan(self) -> List[TokenInfo]:
        """
        Récupère les tokens depuis Solscan
        
        Returns:
            Liste des tokens
        """
        source_info = self.sources["solscan"]
        url = source_info["url"]
        
        headers = {}
        if self.solscan_api_key:
            headers["Authorization"] = f"Bearer {self.solscan_api_key}"
        
        params = {
            "sortBy": "created",
            "direction": "desc",
            "limit": "50"
        }
        
        try:
            async with aiohttp.ClientSession( ) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Error fetching tokens from Solscan: {response.status}")
                        return []
                    
                    data = await response.json()
                    
                    if not isinstance(data, list):
                        logger.error("Invalid response format from Solscan")
                        return []
                    
                    tokens = []
                    for token_data in data:
                        # Extraire les informations du token
                        address = token_data.get("address", "")
                        symbol = token_data.get("symbol", "")
                        name = token_data.get("name", "")
                        
                        # Vérifier les critères minimaux
                        if not address or not symbol:
                            continue
                        
                        # Récupérer les informations détaillées du token
                        token_info = await self._get_token_details_from_solscan(address)
                        
                        if token_info:
                            tokens.append(token_info)
                    
                    # Mettre à jour la dernière mise à jour
                    source_info["last_update"] = time.time()
                    
                    logger.info(f"Found {len(tokens)} tokens from Solscan")
                    return tokens
        
        except Exception as e:
            logger.error(f"Error in _get_tokens_from_solscan: {e}")
            return []
    
    async def _get_token_details_from_solscan(self, token_address: str) -> Optional[TokenInfo]:
        """
        Récupère les détails d'un token depuis Solscan
        
        Args:
            token_address: Adresse du token
            
        Returns:
            Informations sur le token ou None en cas d'erreur
        """
        url = f"https://public-api.solscan.io/token/meta?tokenAddress={token_address}"
        
        headers = {}
        if self.solscan_api_key:
            headers["Authorization"] = f"Bearer {self.solscan_api_key}"
        
        try:
            async with aiohttp.ClientSession( ) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    
                    if not data:
                        return None
                    
                    # Extraire les informations du token
                    symbol = data.get("symbol", "")
                    name = data.get("name", "")
                    
                    # Récupérer les informations de marché
                    market_info = await self._get_token_market_from_solscan(token_address)
                    
                    if not market_info:
                        return None
                    
                    price_usd = market_info.get("price_usd", 0)
                    liquidity_usd = market_info.get("liquidity_usd", 0)
                    fdv = market_info.get("fdv", 0)
                    volume_24h = market_info.get("volume_24h", 0)
                    
                    # Vérifier les critères minimaux
                    if liquidity_usd < self.min_liquidity:
                        return None
                    
                    # Créer l'objet TokenInfo
                    token_info = TokenInfo(
                        address=token_address,
                        symbol=symbol,
                        name=name,
                        price_usd=price_usd,
                        liquidity_usd=liquidity_usd,
                        fdv=fdv,
                        volume_24h=volume_24h,
                        source="solscan",
                        extra_data=data
                    )
                    
                    return token_info
        
        except Exception as e:
            logger.error(f"Error in _get_token_details_from_solscan: {e}")
            return None
    
    async def _get_token_market_from_solscan(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations de marché d'un token depuis Solscan
        
        Args:
            token_address: Adresse du token
            
        Returns:
            Informations de marché ou None en cas d'erreur
        """
        url = f"https://public-api.solscan.io/market/token/{token_address}"
        
        headers = {}
        if self.solscan_api_key:
            headers["Authorization"] = f"Bearer {self.solscan_api_key}"
        
        try:
            async with aiohttp.ClientSession( ) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    
                    if not data:
                        return None
                    
                    # Extraire les informations de marché
                    price_usd = float(data.get("priceUsdt", 0))
                    volume_24h = float(data.get("volume24h", 0))
                    fdv = float(data.get("marketCapFD", 0))
                    liquidity_usd = float(data.get("liquidity", 0))
                    
                    return {
                        "price_usd": price_usd,
                        "volume_24h": volume_24h,
                        "fdv": fdv,
                        "liquidity_usd": liquidity_usd
                    }
        
        except Exception as e:
            logger.error(f"Error in _get_token_market_from_solscan: {e}")
            return None
    
    async def _get_tokens_from_jupiter(self) -> List[TokenInfo]:
        """
        Récupère les tokens depuis Jupiter
        
        Returns:
            Liste des tokens
        """
        source_info = self.sources["jupiter"]
        
        # Jupiter n'a pas d'API pour les nouveaux tokens, mais on peut utiliser l'API de prix
        # pour récupérer les informations sur les tokens populaires
        
        # Liste des tokens populaires sur Solana
        popular_tokens = [
            "So11111111111111111111111111111111111111112",  # SOL
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
            "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj",  # stSOL
            "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",  # mSOL
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
            "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",  # SAMO
            "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",  # RAY
            "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",  # ORCA
            "MangoCzJ36AjZyKwVj3VnYU4GTonjfVEnJmvvWaxLac"   # MNGO
        ]
        
        # Récupérer les informations sur les tokens populaires
        tokens = []
        
        for token_address in popular_tokens:
            token_info = await self._get_token_info_from_jupiter(token_address)
            
            if token_info:
                tokens.append(token_info)
        
        # Mettre à jour la dernière mise à jour
        source_info["last_update"] = time.time()
        
        logger.info(f"Found {len(tokens)} tokens from Jupiter")
        return tokens
    
    async def _get_token_info_from_jupiter(self, token_address: str) -> Optional[TokenInfo]:
        """
        Récupère les informations d'un token depuis Jupiter
        
        Args:
            token_address: Adresse du token
            
        Returns:
            Informations sur le token ou None en cas d'erreur
        """
        url = f"https://price.jup.ag/v4/price?ids={token_address}"
        
        try:
            async with aiohttp.ClientSession( ) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    
                    if not data or "data" not in data or token_address not in data["data"]:
                        return None
                    
                    token_data = data["data"][token_address]
                    
                    # Extraire les informations du token
                    price_usd = float(token_data.get("price", 0))
                    
                    # Récupérer les informations supplémentaires
                    token_info = await self._get_token_details_from_jupiter(token_address)
                    
                    if not token_info:
                        return None
                    
                    symbol = token_info.get("symbol", "")
                    name = token_info.get("name", "")
                    liquidity_usd = token_info.get("liquidity_usd", 0)
                    fdv = token_info.get("fdv", 0)
                    
                    # Vérifier les critères minimaux
                    if not symbol or liquidity_usd < self.min_liquidity:
                        return None
                    
                    # Créer l'objet TokenInfo
                    token_info = TokenInfo(
                        address=token_address,
                        symbol=symbol,
                        name=name,
                        price_usd=price_usd,
                        liquidity_usd=liquidity_usd,
                        fdv=fdv,
                        source="jupiter",
                        extra_data=token_data
                    )
                    
                    return token_info
        
        except Exception as e:
            logger.error(f"Error in _get_token_info_from_jupiter: {e}")
            return None
    
    async def _get_token_details_from_jupiter(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les détails d'un token depuis Jupiter
        
        Args:
            token_address: Adresse du token
            
        Returns:
            Détails du token ou None en cas d'erreur
        """
        # Jupiter n'a pas d'API publique pour les détails des tokens
        # On simule des données pour l'exemple
        
        # Dans une implémentation réelle, il faudrait utiliser une autre source
        # comme Birdeye ou Solscan pour récupérer ces informations
        
        token_details = {
            "So11111111111111111111111111111111111111112": {
                "symbol": "SOL",
                "name": "Wrapped SOL",
                "liquidity_usd": 100000000,
                "fdv": 20000000000
            },
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {
                "symbol": "USDC",
                "name": "USD Coin",
                "liquidity_usd": 500000000,
                "fdv": 50000000000
            },
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": {
                "symbol": "USDT",
                "name": "Tether USD",
                "liquidity_usd": 300000000,
                "fdv": 30000000000
            },
            "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj": {
                "symbol": "stSOL",
                "name": "Lido Staked SOL",
                "liquidity_usd": 50000000,
                "fdv": 5000000000
            },
            "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": {
                "symbol": "mSOL",
                "name": "Marinade Staked SOL",
                "liquidity_usd": 40000000,
                "fdv": 4000000000
            },
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": {
                "symbol": "BONK",
                "name": "Bonk",
                "liquidity_usd": 20000000,
                "fdv": 2000000000
            },
            "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU": {
                "symbol": "SAMO",
                "name": "Samoyedcoin",
                "liquidity_usd": 15000000,
                "fdv": 1500000000
            },
            "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R": {
                "symbol": "RAY",
                "name": "Raydium",
                "liquidity_usd": 10000000,
                "fdv": 1000000000
            },
            "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE": {
                "symbol": "ORCA",
                "name": "Orca",
                "liquidity_usd": 8000000,
                "fdv": 800000000
            },
            "MangoCzJ36AjZyKwVj3VnYU4GTonjfVEnJmvvWaxLac": {
                "symbol": "MNGO",
                "name": "Mango",
                "liquidity_usd": 5000000,
                "fdv": 500000000
            }
        }
        
        return token_details.get(token_address)
    
    async def get_token_holders(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations sur les détenteurs d'un token
        
        Args:
            token_address: Adresse du token
            
        Returns:
            Informations sur les détenteurs ou None en cas d'erreur
        """
        # Vérifier le cache
        cache_key = f"holders_{token_address}"
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        # Récupérer les informations depuis Solscan
        url = f"https://public-api.solscan.io/token/holders?tokenAddress={token_address}&limit=20"
        
        headers = {}
        if self.solscan_api_key:
            headers["Authorization"] = f"Bearer {self.solscan_api_key}"
        
        try:
            async with aiohttp.ClientSession( ) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Error fetching token holders: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    if not data or not isinstance(data, list):
                        logger.error("Invalid response format for token holders")
                        return None
                    
                    # Calculer le nombre total de détenteurs et la distribution
                    total_holders = len(data)
                    top_holders = []
                    
                    for holder in data[:10]:  # Top 10 détenteurs
                        holder_info = {
                            "address": holder.get("owner", ""),
                            "amount": float(holder.get("amount", 0)),
                            "percentage": float(holder.get("percentage", 0)) / 100
                        }
                        
                        top_holders.append(holder_info)
                    
                    result = {
                        "total_holders": total_holders,
                        "top_holders": top_holders
                    }
                    
                    # Mettre en cache
                    self._add_to_cache(cache_key, result)
                    
                    return result
        
        except Exception as e:
            logger.error(f"Error in get_token_holders: {e}")
            return None
    
    async def get_token_social_mentions(self, token_symbol: str) -> int:
        """
        Récupère le nombre de mentions sociales d'un token
        
        Args:
            token_symbol: Symbole du token
            
        Returns:
            Nombre de mentions sociales
        """
        # Vérifier le cache
        cache_key = f"social_{token_symbol}"
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data is not None:
            return cached_data
        
        # Dans une implémentation réelle, il faudrait interroger une API de médias sociaux
        # comme Twitter ou Discord pour récupérer le nombre de mentions
        
        # Pour l'exemple, on génère un nombre aléatoire
        mentions = random.randint(0, 100)
        
        # Mettre en cache
        self._add_to_cache(cache_key, mentions)
        
        return mentions
    
    async def get_token_creation_time(self, token_address: str) -> float:
        """
        Récupère la date de création d'un token
        
        Args:
            token_address: Adresse du token
            
        Returns:
            Timestamp de création ou 0 en cas d'erreur
        """
        # Vérifier le cache
        cache_key = f"creation_{token_address}"
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data is not None:
            return cached_data
        
        # Récupérer les informations depuis Solscan
        url = f"https://public-api.solscan.io/token/meta?tokenAddress={token_address}"
        
        headers = {}
        if self.solscan_api_key:
            headers["Authorization"] = f"Bearer {self.solscan_api_key}"
        
        try:
            async with aiohttp.ClientSession( ) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        return 0
                    
                    data = await response.json()
                    
                    if not data:
                        return 0
                    
                    # Extraire la date de création
                    creation_time = 0
                    
                    if "mintAuthority" in data:
                        # Récupérer la transaction de création
                        mint_tx = await self._get_first_transaction(token_address)
                        
                        if mint_tx:
                            creation_time = mint_tx
                    
                    # Mettre en cache
                    self._add_to_cache(cache_key, creation_time)
                    
                    return creation_time
        
        except Exception as e:
            logger.error(f"Error in get_token_creation_time: {e}")
            return 0
    
    async def _get_first_transaction(self, token_address: str) -> float:
        """
        Récupère la première transaction d'un token
        
        Args:
            token_address: Adresse du token
            
        Returns:
            Timestamp de la première transaction ou 0 en cas d'erreur
        """
        url = f"https://public-api.solscan.io/account/transactions?account={token_address}&limit=1"
        
        headers = {}
        if self.solscan_api_key:
            headers["Authorization"] = f"Bearer {self.solscan_api_key}"
        
        try:
            async with aiohttp.ClientSession( ) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        return 0
                    
                    data = await response.json()
                    
                    if not data or not isinstance(data, list) or not data:
                        return 0
                    
                    # Extraire le timestamp de la première transaction
                    tx = data[0]
                    timestamp = tx.get("blockTime", 0)
                    
                    return timestamp
        
        except Exception as e:
            logger.error(f"Error in _get_first_transaction: {e}")
            return 0
    
    async def get_token_price_history(self, token_address: str, 
                                     interval: str = "1h") -> Optional[List[Dict[str, Any]]]:
        """
        Récupère l'historique des prix d'un token
        
        Args:
            token_address: Adresse du token
            interval: Intervalle de temps (1h, 4h, 1d)
            
        Returns:
            Liste des prix historiques ou None en cas d'erreur
        """
        # Vérifier le cache
        cache_key = f"price_history_{token_address}_{interval}"
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        # Récupérer les informations depuis Birdeye
        url = f"https://public-api.birdeye.so/defi/price_history"
        
        params = {
            "address": token_address,
            "type": interval,
            "time_from": int(time.time( ) - 86400 * 7)  # 7 jours
        }
        
        headers = {}
        if self.birdeye_api_key:
            headers["X-API-KEY"] = self.birdeye_api_key
        
        try:
            async with aiohttp.ClientSession( ) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Error fetching price history: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    if not data or "data" not in data or "items" not in data["data"]:
                        logger.error("Invalid response format for price history")
                        return None
                    
                    price_history = []
                    
                    for item in data["data"]["items"]:
                        price_point = {
                            "timestamp": item.get("unixTime", 0),
                            "price": float(item.get("value", 0)),
                            "volume": float(item.get("volume", 0))
                        }
                        
                        price_history.append(price_point)
                    
                    # Mettre en cache
                    self._add_to_cache(cache_key, price_history)
                    
                    return price_history
        
        except Exception as e:
            logger.error(f"Error in get_token_price_history: {e}")
            return None
    
    async def get_token_liquidity_history(self, token_address: str, 
                                         interval: str = "1h") -> Optional[List[Dict[str, Any]]]:
        """
        Récupère l'historique de liquidité d'un token
        
        Args:
            token_address: Adresse du token
            interval: Intervalle de temps (1h, 4h, 1d)
            
        Returns:
            Liste des liquidités historiques ou None en cas d'erreur
        """
        # Vérifier le cache
        cache_key = f"liquidity_history_{token_address}_{interval}"
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        # Récupérer les informations depuis Birdeye
        url = f"https://public-api.birdeye.so/defi/liquidity_history"
        
        params = {
            "address": token_address,
            "type": interval,
            "time_from": int(time.time( ) - 86400 * 7)  # 7 jours
        }
        
        headers = {}
        if self.birdeye_api_key:
            headers["X-API-KEY"] = self.birdeye_api_key
        
        try:
            async with aiohttp.ClientSession( ) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Error fetching liquidity history: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    if not data or "data" not in data or "items" not in data["data"]:
                        logger.error("Invalid response format for liquidity history")
                        return None
                    
                    liquidity_history = []
                    
                    for item in data["data"]["items"]:
                        liquidity_point = {
                            "timestamp": item.get("unixTime", 0),
                            "liquidity": float(item.get("value", 0))
                        }
                        
                        liquidity_history.append(liquidity_point)
                    
                    # Mettre en cache
                    self._add_to_cache(cache_key, liquidity_history)
                    
                    return liquidity_history
        
        except Exception as e:
            logger.error(f"Error in get_token_liquidity_history: {e}")
            return None
    
    async def get_mempool_transactions(self) -> List[Dict[str, Any]]:
        """
        Récupère les transactions en attente dans le mempool
        
        Returns:
            Liste des transactions en attente
        """
        # Dans une implémentation réelle, il faudrait interroger un nœud RPC
        # pour récupérer les transactions en attente
        
        # Pour l'exemple, on retourne une liste vide
        return []
    
    async def detect_liquidity_additions(self) -> List[Dict[str, Any]]:
        """
        Détecte les ajouts de liquidité récents
        
        Returns:
            Liste des ajouts de liquidité
        """
        # Dans une implémentation réelle, il faudrait surveiller les transactions
        # d'ajout de liquidité sur les DEX comme Raydium ou Orca
        
        # Pour l'exemple, on retourne une liste vide
        return []
    
    def _get_from_cache(self, key: str) -> Any:
        """
        Récupère une valeur depuis le cache
        
        Args:
            key: Clé de cache
            
        Returns:
            Valeur ou None si non trouvée ou expirée
        """
        if key not in self.token_cache:
            return None
        
        cache_entry = self.token_cache[key]
        if time.time() - cache_entry["timestamp"] > self.cache_ttl:
            # Cache expiré
            del self.token_cache[key]
            return None
        
        return cache_entry["data"]
    
    def _add_to_cache(self, key: str, data: Any) -> None:
        """
        Ajoute une valeur au cache
        
        Args:
            key: Clé de cache
            data: Valeur à mettre en cache
        """
        self.token_cache[key] = {
            "timestamp": time.time(),
            "data": data
        }

# Exemple d'utilisation
async def main():
    config = {
        "MAX_TOKENS_PER_SCAN": 50,
        "MIN_LIQUIDITY_USD": 10000,
        "BIRDEYE_API_KEY": "",
        "SOLSCAN_API_KEY": ""
    }
    
    data_source = DataSource(config)
    
    # Récupérer les nouveaux tokens
    tokens = await data_source.get_new_tokens_multi_source()
    
    for token in tokens:
        print(f"Token: {token.symbol} ({token.address})")
        print(f"  Price: ${token.price_usd:.6f}")
        print(f"  Liquidity: ${token.liquidity_usd:.2f}")
        print(f"  Source: {token.source}")
        print()
