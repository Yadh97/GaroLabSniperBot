"""
Module d'analyse de momentum pour GaroLabSniperBot
Implémente un système avancé de scoring pour identifier les tokens à fort potentiel
"""

import time
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import asyncio
import logging
from datetime import datetime, timedelta

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("momentum_analyzer")

@dataclass
class MomentumScore:
    token_address: str
    symbol: str
    total_score: float
    price_momentum: float
    volume_momentum: float
    social_momentum: float
    holder_score: float
    liquidity_score: float
    timestamp: float
    components: Dict[str, float]
    
    def __str__(self) -> str:
        return (f"{self.symbol}: {self.total_score:.2f} "
                f"[P:{self.price_momentum:.2f}, V:{self.volume_momentum:.2f}, "
                f"S:{self.social_momentum:.2f}, H:{self.holder_score:.2f}, "
                f"L:{self.liquidity_score:.2f}]")

class MomentumAnalyzer:
    """
    Analyse le momentum des tokens pour identifier ceux à fort potentiel
    Utilise une combinaison de facteurs: prix, volume, activité sociale, distribution des détenteurs
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.token_data = {}  # Historique des données par token
        self.momentum_scores = {}  # Scores de momentum par token
        self.social_signals = {}  # Signaux sociaux par token
        
        # Paramètres configurables
        self.price_weight = config.get("PRICE_MOMENTUM_WEIGHT", 0.3)
        self.volume_weight = config.get("VOLUME_MOMENTUM_WEIGHT", 0.25)
        self.social_weight = config.get("SOCIAL_MOMENTUM_WEIGHT", 0.2)
        self.holder_weight = config.get("HOLDER_DISTRIBUTION_WEIGHT", 0.15)
        self.liquidity_weight = config.get("LIQUIDITY_WEIGHT", 0.1)
        
        self.data_points_required = config.get("MIN_DATA_POINTS", 3)
        self.max_data_points = config.get("MAX_DATA_POINTS", 20)
        self.score_threshold = config.get("MOMENTUM_SCORE_THRESHOLD", 0.7)
        
        # Périodes d'analyse
        self.short_period = config.get("SHORT_PERIOD_MINUTES", 5)
        self.medium_period = config.get("MEDIUM_PERIOD_MINUTES", 30)
        self.long_period = config.get("LONG_PERIOD_MINUTES", 120)
        
        logger.info(f"Initialized MomentumAnalyzer with weights: "
                   f"Price={self.price_weight}, Volume={self.volume_weight}, "
                   f"Social={self.social_weight}, Holder={self.holder_weight}, "
                   f"Liquidity={self.liquidity_weight}")
    
    async def update_token_data(self, token_address: str, data: Dict[str, Any]) -> None:
        """
        Met à jour les données d'un token avec de nouvelles informations
        
        Args:
            token_address: Adresse du token
            data: Dictionnaire contenant les données du token (prix, volume, etc.)
        """
        if token_address not in self.token_data:
            self.token_data[token_address] = []
        
        # Ajouter un timestamp si non fourni
        if "timestamp" not in data:
            data["timestamp"] = time.time()
        
        # Ajouter les données
        self.token_data[token_address].append(data)
        
        # Limiter l'historique
        if len(self.token_data[token_address]) > self.max_data_points:
            self.token_data[token_address] = self.token_data[token_address][-self.max_data_points:]
        
        # Calculer le score de momentum
        await self.calculate_momentum_score(token_address)
    
    async def update_social_signal(self, token_address: str, platform: str, signal_strength: float) -> None:
        """
        Met à jour les signaux sociaux pour un token
        
        Args:
            token_address: Adresse du token
            platform: Plateforme sociale (twitter, discord, telegram, etc.)
            signal_strength: Force du signal (0.0 à 1.0)
        """
        if token_address not in self.social_signals:
            self.social_signals[token_address] = {}
        
        self.social_signals[token_address][platform] = {
            "strength": signal_strength,
            "timestamp": time.time()
        }
    
    async def calculate_momentum_score(self, token_address: str) -> Optional[MomentumScore]:
        """
        Calcule le score de momentum pour un token
        
        Args:
            token_address: Adresse du token
            
        Returns:
            MomentumScore ou None si pas assez de données
        """
        if token_address not in self.token_data:
            return None
        
        data = self.token_data[token_address]
        
        # Vérifier s'il y a assez de données
        if len(data) < self.data_points_required:
            return None
        
        # Convertir en DataFrame pour faciliter l'analyse
        df = pd.DataFrame(data)
        
        # Extraire les informations de base du token
        latest = df.iloc[-1]
        symbol = latest.get("symbol", "???")
        
        # Calculer les composantes du score
        price_momentum = await self._calculate_price_momentum(df)
        volume_momentum = await self._calculate_volume_momentum(df)
        social_momentum = await self._calculate_social_momentum(token_address)
        holder_score = await self._calculate_holder_distribution_score(df)
        liquidity_score = await self._calculate_liquidity_score(df)
        
        # Calculer le score total pondéré
        total_score = (
            price_momentum * self.price_weight +
            volume_momentum * self.volume_weight +
            social_momentum * self.social_weight +
            holder_score * self.holder_weight +
            liquidity_score * self.liquidity_weight
        )
        
        # Normaliser le score entre 0 et 1
        total_score = max(0.0, min(1.0, total_score))
        
        # Créer l'objet de score
        score = MomentumScore(
            token_address=token_address,
            symbol=symbol,
            total_score=total_score,
            price_momentum=price_momentum,
            volume_momentum=volume_momentum,
            social_momentum=social_momentum,
            holder_score=holder_score,
            liquidity_score=liquidity_score,
            timestamp=time.time(),
            components={
                "price_momentum": price_momentum,
                "volume_momentum": volume_momentum,
                "social_momentum": social_momentum,
                "holder_score": holder_score,
                "liquidity_score": liquidity_score
            }
        )
        
        # Stocker le score
        self.momentum_scores[token_address] = score
        
        # Journaliser si le score est élevé
        if total_score >= self.score_threshold:
            logger.info(f"High momentum detected: {score}")
        
        return score
    
    async def _calculate_price_momentum(self, df: pd.DataFrame) -> float:
        """
        Calcule le momentum du prix basé sur plusieurs facteurs:
        - Tendance récente du prix
        - Accélération du prix
        - Volatilité
        - Franchissement de moyennes mobiles
        
        Returns:
            Score de momentum du prix (0.0 à 1.0)
        """
        try:
            # Vérifier que les colonnes nécessaires existent
            if "price_usd" not in df.columns:
                return 0.0
            
            # Calculer les rendements
            df["returns"] = df["price_usd"].pct_change()
            
            # Calculer les moyennes mobiles
            df["sma_short"] = df["price_usd"].rolling(window=min(3, len(df))).mean()
            df["sma_medium"] = df["price_usd"].rolling(window=min(5, len(df))).mean()
            
            # Calculer la tendance récente (dernières périodes)
            recent_trend = 0.0
            if len(df) >= 2:
                recent_return = (df["price_usd"].iloc[-1] / df["price_usd"].iloc[-2]) - 1
                recent_trend = self._sigmoid(recent_return * 10)  # Normaliser avec sigmoid
            
            # Calculer l'accélération du prix
            acceleration = 0.0
            if len(df) >= 3:
                returns = df["returns"].dropna().tail(3).values
                if len(returns) >= 2:
                    acceleration = returns[-1] - returns[-2]
                    acceleration = self._sigmoid(acceleration * 20)  # Normaliser
            
            # Calculer la volatilité (écart-type des rendements)
            volatility = 0.0
            if len(df) >= 3:
                volatility = df["returns"].dropna().tail(5).std()
                # Une volatilité modérée est positive, trop élevée est négative
                volatility_score = 1.0 - abs(volatility - 0.05) / 0.05
                volatility_score = max(0.0, min(1.0, volatility_score))
            
            # Vérifier le franchissement de moyennes mobiles
            ma_crossover = 0.0
            if len(df) >= 5 and "sma_short" in df and "sma_medium" in df:
                # Croisement haussier récent
                if (df["sma_short"].iloc[-1] > df["sma_medium"].iloc[-1] and 
                    df["sma_short"].iloc[-2] <= df["sma_medium"].iloc[-2]):
                    ma_crossover = 1.0
                # Tendance haussière confirmée
                elif df["sma_short"].iloc[-1] > df["sma_medium"].iloc[-1]:
                    ma_crossover = 0.7
            
            # Combiner les facteurs
            price_score = (
                recent_trend * 0.4 +
                acceleration * 0.3 +
                volatility_score * 0.1 +
                ma_crossover * 0.2
            )
            
            return max(0.0, min(1.0, price_score))
            
        except Exception as e:
            logger.error(f"Error calculating price momentum: {e}")
            return 0.0
    
    async def _calculate_volume_momentum(self, df: pd.DataFrame) -> float:
        """
        Calcule le momentum du volume basé sur:
        - Croissance récente du volume
        - Ratio volume/liquidité
        - Constance du volume
        
        Returns:
            Score de momentum du volume (0.0 à 1.0)
        """
        try:
            # Vérifier que les colonnes nécessaires existent
            if "volume_24h" not in df.columns:
                return 0.0
            
            # Calculer la croissance du volume
            volume_growth = 0.0
            if len(df) >= 2:
                last_volumes = df["volume_24h"].tail(3).values
                if len(last_volumes) >= 2 and last_volumes[-2] > 0:
                    volume_growth = (last_volumes[-1] / last_volumes[-2]) - 1
                    volume_growth = self._sigmoid(volume_growth * 5)  # Normaliser
            
            # Calculer le ratio volume/liquidité
            volume_liquidity_ratio = 0.0
            if "liquidity_usd" in df.columns and df["liquidity_usd"].iloc[-1] > 0:
                ratio = df["volume_24h"].iloc[-1] / df["liquidity_usd"].iloc[-1]
                # Un ratio élevé est positif, mais pas trop élevé (pourrait indiquer une manipulation)
                if ratio > 3.0:
                    volume_liquidity_ratio = 0.5  # Suspicieux
                else:
                    volume_liquidity_ratio = min(1.0, ratio / 3.0)
            
            # Vérifier la constance du volume (pas de chute brutale)
            volume_consistency = 1.0
            if len(df) >= 3:
                volumes = df["volume_24h"].tail(3).values
                for i in range(1, len(volumes)):
                    if volumes[i-1] > 0 and volumes[i] / volumes[i-1] < 0.5:
                        volume_consistency = 0.5  # Pénalité pour chute de volume
            
            # Combiner les facteurs
            volume_score = (
                volume_growth * 0.5 +
                volume_liquidity_ratio * 0.3 +
                volume_consistency * 0.2
            )
            
            return max(0.0, min(1.0, volume_score))
            
        except Exception as e:
            logger.error(f"Error calculating volume momentum: {e}")
            return 0.0
    
    async def _calculate_social_momentum(self, token_address: str) -> float:
        """
        Calcule le momentum social basé sur:
        - Mentions sur les réseaux sociaux
        - Sentiment des mentions
        - Récence des mentions
        
        Returns:
            Score de momentum social (0.0 à 1.0)
        """
        try:
            if token_address not in self.social_signals:
                return 0.0
            
            signals = self.social_signals[token_address]
            if not signals:
                return 0.0
            
            # Calculer le score moyen pondéré par la récence
            total_weight = 0.0
            weighted_sum = 0.0
            
            current_time = time.time()
            for platform, data in signals.items():
                signal_strength = data["strength"]
                timestamp = data["timestamp"]
                
                # Facteur de décroissance basé sur l'âge (24 heures max)
                age_hours = (current_time - timestamp) / 3600
                if age_hours > 24:
                    continue
                
                recency_factor = max(0.0, 1.0 - (age_hours / 24))
                
                # Pondération par plateforme
                platform_weight = {
                    "twitter": 1.0,
                    "discord": 0.8,
                    "telegram": 0.7,
                    "reddit": 0.6
                }.get(platform.lower(), 0.5)
                
                weight = recency_factor * platform_weight
                weighted_sum += signal_strength * weight
                total_weight += weight
            
            if total_weight > 0:
                return min(1.0, weighted_sum / total_weight)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating social momentum: {e}")
            return 0.0
    
    async def _calculate_holder_distribution_score(self, df: pd.DataFrame) -> float:
        """
        Calcule un score basé sur la distribution des détenteurs:
        - Nombre de détenteurs
        - Concentration des détenteurs principaux
        - Évolution du nombre de détenteurs
        
        Returns:
            Score de distribution des détenteurs (0.0 à 1.0)
        """
        try:
            # Vérifier que les colonnes nécessaires existent
            if "holders_count" not in df.columns and "top_holder_percentage" not in df.columns:
                return 0.5  # Score neutre si pas de données
            
            latest = df.iloc[-1]
            
            # Score basé sur le nombre de détenteurs
            holders_count = latest.get("holders_count", 0)
            holders_score = 0.0
            if holders_count > 0:
                # Échelle logarithmique: 10 détenteurs -> 0.3, 100 -> 0.6, 1000 -> 0.9
                holders_score = min(1.0, max(0.0, 0.3 * np.log10(holders_count)))
            
            # Score basé sur la concentration (plus c'est distribué, mieux c'est)
            concentration_score = 0.5  # Valeur par défaut
            if "top_holder_percentage" in df.columns:
                top_holder_pct = latest["top_holder_percentage"]
                # Pénaliser les tokens très concentrés
                if top_holder_pct > 80:
                    concentration_score = 0.1
                elif top_holder_pct > 50:
                    concentration_score = 0.3
                elif top_holder_pct > 30:
                    concentration_score = 0.5
                elif top_holder_pct > 10:
                    concentration_score = 0.7
                else:
           
(Content truncated due to size limit. Use line ranges to read in chunks)
