"""
Module de sources de données amélioré pour GaroLabSniperBot
Intègre plusieurs sources de données pour une détection précoce des tokens
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import asyncio
import time
import requests
import json
import logging
from datetime import datetime

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("data_sources")

@dataclass
class TokenInfo:
    address: str
    name: str
    symbol: str
    price_usd: float
    liquidity_usd: float
    fdv: float
    pair_id: str
    source: str
    decimals: int = None
    buzz_score: float = 0.0
    creation_time: float = None
    holders_count: int = None
    top_holder_percentage: float = None
    volume_24h: float = None
    price_change_24h: float = None

class DataSourceManager:
    """Gestionnaire centralisé des sources de données"""
    
    def __init__(self, config):
        self.config = config
        self.sources = []
        self.token_cache = {}
        self.last_fetch_time = {}
        
        # Initialiser les sources de données activées
        if config.get("ENABLE_PUMPFUN", True):
            self.sources.append(PumpFunDataSource(config))
        
        if config.get("ENABLE_BIRDEYE", False):
            self.sources.append(BirdeyeDataSource(config))
        
        if config.get("ENABLE_DEXSCREENER", False):
            self.sources.append(DexScreenerDataSource(config))
        
        if config.get("ENABLE_SOLSCAN", False):
            self.sources.append(SolscanDataSource(config))
        
        if config.get("ENABLE_JUPITER", False):
            self.sources.append(JupiterDataSource(config))
        
        logger.info(f"Initialized {len(self.sources)} data sources")
    
    async def get_new_tokens(self) -> List[TokenInfo]:
        """Récupère les nouveaux tokens de toutes les sources configurées"""
        all_tokens = []
        tasks = []
        
        for source in self.sources:
            # Vérifier si la source doit être interrogée (basé sur la fréquence)
            current_time = time.time()
            last_time = self.last_fetch_time.get(source.name, 0)
            if current_time - last_time >= source.refresh_interval:
                self.last_fetch_time[source.name] = current_time
                tasks.append(source.fetch_tokens())
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error fetching tokens: {result}")
                elif isinstance(result, list):
                    all_tokens.extend(result)
        
        # Dédupliquer les tokens par adresse
        unique_tokens = {}
        for token in all_tokens:
            if token.address not in unique_tokens:
                unique_tokens[token.address] = token
            else:
                # Si le token existe déjà, mettre à jour avec la source la plus récente
                existing = unique_tokens[token.address]
                if token.creation_time and (not existing.creation_time or token.creation_time > existing.creation_time):
                    unique_tokens[token.address] = token
        
        # Mettre à jour le cache
        self.token_cache.update(unique_tokens)
        
        # Retourner uniquement les nouveaux tokens
        return list(unique_tokens.values())
    
    async def get_token_details(self, token_address: str) -> Optional[TokenInfo]:
        """Récupère les détails complets d'un token spécifique"""
        # Vérifier d'abord dans le cache
        if token_address in self.token_cache:
            return self.token_cache[token_address]
        
        # Sinon, interroger toutes les sources
        for source in self.sources:
            try:
                token_info = await source.get_token_details(token_address)
                if token_info:
                    self.token_cache[token_address] = token_info
                    return token_info
            except Exception as e:
                logger.error(f"Error getting token details from {source.name}: {e}")
        
        return None
    
    async def get_token_price_history(self, token_address: str, timeframe: str = "1h") -> List[Dict[str, Any]]:
        """Récupère l'historique des prix d'un token"""
        for source in self.sources:
            if hasattr(source, "get_price_history"):
                try:
                    history = await source.get_price_history(token_address, timeframe)
                    if history:
                        return history
                except Exception as e:
                    logger.error(f"Error getting price history from {source.name}: {e}")
        
        return []

class BaseDataSource:
    """Classe de base pour toutes les sources de données"""
    
    def __init__(self, config):
        self.config = config
        self.name = "base"
        self.refresh_interval = 60  # Secondes entre les requêtes
    
    async def fetch_tokens(self) -> List[TokenInfo]:
        """Méthode à implémenter par les sous-classes"""
        raise NotImplementedError
    
    async def get_token_details(self, token_address: str) -> Optional[TokenInfo]:
        """Méthode à implémenter par les sous-classes"""
        raise NotImplementedError
    
    def _handle_request_error(self, e, source_name):
        """Gestion standardisée des erreurs de requête"""
        if isinstance(e, requests.exceptions.RequestException):
            logger.error(f"{source_name} API request failed: {e}")
        else:
            logger.error(f"{source_name} processing error: {e}")
        return []

class PumpFunDataSource(BaseDataSource):
    """Source de données pour Pump.fun"""
    
    def __init__(self, config):
        super().__init__(config)
        self.name = "pumpfun"
        self.refresh_interval = 30  # Vérifier toutes les 30 secondes
        self.api_url = "https://pump.fun/api/tokens"
    
    async def fetch_tokens(self) -> List[TokenInfo]:
        tokens = []
        try:
            response = await self._async_get(self.api_url)
            data = response.json()
            
            for entry in data:
                try:
                    token_addr = entry.get("id") or entry.get("mint")
                    if not token_addr:
                        continue
                    
                    name = entry.get("name") or "Unknown"
                    symbol = entry.get("symbol") or "???"
                    decimals = int(entry.get("decimals", 0))
                    price = float(entry.get("priceUsdc") or 0)
                    liquidity = float(entry.get("liquidity") or 0)
                    fdv = float(entry.get("fdv") or 0)
                    volume_24h = float(entry.get("volume24h") or 0)
                    price_change_24h = float(entry.get("priceChange24h") or 0)
                    
                    # Calculer un score de buzz basé sur le volume et le changement de prix
                    buzz_score = 0.0
                    if liquidity > 0:
                        volume_ratio = volume_24h / liquidity
                        buzz_score = (volume_ratio * 0.7) + (abs(price_change_24h) * 0.3)
                    
                    tokens.append(TokenInfo(
                        address=token_addr,
                        name=name,
                        symbol=symbol,
                        price_usd=price,
                        liquidity_usd=liquidity,
                        fdv=fdv,
                        pair_id="",
                        source=self.name,
                        decimals=decimals,
                        buzz_score=buzz_score,
                        creation_time=time.time(),
                        volume_24h=volume_24h,
                        price_change_24h=price_change_24h
                    ))
                except Exception as e:
                    logger.warning(f"Error processing Pump.fun token: {e}")
                    continue
            
            logger.info(f"Fetched {len(tokens)} tokens from Pump.fun")
            return tokens
            
        except Exception as e:
            return self._handle_request_error(e, "Pump.fun")
    
    async def get_token_details(self, token_address: str) -> Optional[TokenInfo]:
        try:
            # Pump.fun n'a pas d'API de détails par token, on utilise l'API générale
            response = await self._async_get(self.api_url)
            data = response.json()
            
            for entry in data:
                addr = entry.get("id") or entry.get("mint")
                if addr and addr.lower() == token_address.lower():
                    name = entry.get("name") or "Unknown"
                    symbol = entry.get("symbol") or "???"
                    decimals = int(entry.get("decimals", 0))
                    price = float(entry.get("priceUsdc") or 0)
                    liquidity = float(entry.get("liquidity") or 0)
                    fdv = float(entry.get("fdv") or 0)
                    volume_24h = float(entry.get("volume24h") or 0)
                    price_change_24h = float(entry.get("priceChange24h") or 0)
                    
                    return TokenInfo(
                        address=addr,
                        name=name,
                        symbol=symbol,
                        price_usd=price,
                        liquidity_usd=liquidity,
                        fdv=fdv,
                        pair_id="",
                        source=self.name,
                        decimals=decimals,
                        buzz_score=0.0,
                        creation_time=time.time(),
                        volume_24h=volume_24h,
                        price_change_24h=price_change_24h
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting token details from Pump.fun: {e}")
            return None
    
    async def _async_get(self, url, params=None, timeout=10):
        """Wrapper pour les requêtes HTTP asynchrones"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            lambda: requests.get(url, params=params, timeout=timeout)
        )

class BirdeyeDataSource(BaseDataSource):
    """Source de données pour Birdeye"""
    
    def __init__(self, config):
        super().__init__(config)
        self.name = "birdeye"
        self.refresh_interval = 60  # Vérifier toutes les 60 secondes
        self.api_key = config.get("BIRDEYE_API_KEY", "")
        self.api_url = "https://public-api.birdeye.so/defi/new_tokens"
        self.token_url = "https://public-api.birdeye.so/public/token"
        self.headers = {"X-API-KEY": self.api_key}
    
    async def fetch_tokens(self) -> List[TokenInfo]:
        if not self.api_key:
            logger.warning("Birdeye API key not configured")
            return []
        
        tokens = []
        try:
            params = {"chain": "solana", "limit": 50}
            response = await self._async_get(self.api_url, params=params, headers=self.headers)
            data = response.json()
            
            if data.get("success") and "data" in data:
                token_list = data["data"].get("items", [])
                
                for entry in token_list:
                    try:
                        token_addr = entry.get("address")
                        if not token_addr:
                            continue
                        
                        name = entry.get("name") or "Unknown"
                        symbol = entry.get("symbol") or "???"
                        decimals = int(entry.get("decimals", 0))
                        price = float(entry.get("price") or 0)
                        liquidity = float(entry.get("liquidity") or 0)
                        fdv = float(entry.get("fdv") or 0)
                        
                        # Calculer un score de buzz basé sur l'âge et la liquidité
                        creation_time = entry.get("created_at", 0)
                        age_hours = (time.time() - creation_time) / 3600 if creation_time else 24
                        buzz_score = 0.0
                        if age_hours < 24 and liquidity > 5000:
                            buzz_score = (1 - (age_hours / 24)) * (liquidity / 10000)
                        
                        tokens.append(TokenInfo(
                            address=token_addr,
                            name=name,
                            symbol=symbol,
                            price_usd=price,
                            liquidity_usd=liquidity,
                            fdv=fdv,
                            pair_id=entry.get("pool_address", ""),
                            source=self.name,
                            decimals=decimals,
                            buzz_score=buzz_score,
                            creation_time=creation_time
                        ))
                    except Exception as e:
                        logger.warning(f"Error processing Birdeye token: {e}")
                        continue
            
            logger.info(f"Fetched {len(tokens)} tokens from Birdeye")
            return tokens
            
        except Exception as e:
            return self._handle_request_error(e, "Birdeye")
    
    async def get_token_details(self, token_address: str) -> Optional[TokenInfo]:
        if not self.api_key:
            return None
        
        try:
            params = {"address": token_address, "chain": "solana"}
            response = await self._async_get(self.token_url, params=params, headers=self.headers)
            data = response.json()
            
            if data.get("success") and "data" in data:
                entry = data["data"]
                
                name = entry.get("name") or "Unknown"
                symbol = entry.get("symbol") or "???"
                decimals = int(entry.get("decimals", 0))
                price = float(entry.get("price") or 0)
                liquidity = float(entry.get("liquidity") or 0)
                fdv = float(entry.get("fdv") or 0)
                holders_count = entry.get("holders", 0)
                
                return TokenInfo(
                    address=token_address,
                    name=name,
                    symbol=symbol,
                    price_usd=price,
                    liquidity_usd=liquidity,
                    fdv=fdv,
                    pair_id=entry.get("pool_address", ""),
                    source=self.name,
                    decimals=decimals,
                    buzz_score=0.0,
                    creation_time=entry.get("created_at", 0),
                    holders_count=holders_count
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting token details from Birdeye: {e}")
            return None
    
    async def get_price_history(self, token_address: str, timeframe: str = "1h") -> List[Dict[str, Any]]:
        """Récupère l'historique des prix d'un token depuis Birdeye"""
        if not self.api_key:
            return []
        
        try:
            url = f"https://public-api.birdeye.so/defi/price_history"
            params = {
                "address": token_address,
                "chain": "solana",
                "type": timeframe,
                "limit": 100
            }
            
            response = await self._async_get(url, params=params, headers=self.headers)
            data = response.json()
            
            if data.get("success") and "data" in data:
                history = data["data"].get("items", [])
    
(Content truncated due to size limit. Use line ranges to read in chunks)
