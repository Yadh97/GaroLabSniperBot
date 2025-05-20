"""
GaroLabSniperBot - Bot de trading automatisé pour les meme coins sur Solana
Développé par Yadh97, amélioré pour une rentabilité maximale
"""

import asyncio
import logging
import json
import os
import time
import traceback
from typing import Dict, List, Optional, Any
import sys
from datetime import datetime

# Imports des modules du bot
from config import load_config
from data_sources import DataSource
from momentum_analyzer import MomentumAnalyzer
from trading_strategies import TradingStrategyManager
from order_routing import SmartOrderRouter
from trader import Trader
from simulated_trader import SimulatedTrader
from token_cache import TokenCache
from filters import TokenFilter
from notifier import Notifier
from telegram_alert import TelegramNotifier

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("main")

# Variables globales
config = {}
data_source = None
momentum_analyzer = None
strategy_manager = None
order_router = None
trader = None
token_cache = None
token_filter = None
notifier = None

async def initialize():
    """Initialise tous les composants du bot"""
    global config, data_source, momentum_analyzer, strategy_manager, order_router, trader, token_cache, token_filter, notifier
    
    logger.info("Initialisation du GaroLabSniperBot...")
    
    # Charger la configuration
    config = load_config()
    
    # Initialiser le cache de tokens
    token_cache = TokenCache(config.get("TOKEN_CACHE_FILE", "token_cache.json"))
    
    # Initialiser les sources de données
    data_source = DataSource(config)
    
    # Initialiser l'analyseur de momentum
    momentum_analyzer = MomentumAnalyzer(config)
    
    # Initialiser le client RPC
    rpc_client = None  # À remplacer par votre client RPC réel
    
    # Initialiser le routeur d'ordres
    order_router = SmartOrderRouter(config, rpc_client)
    
    # Initialiser le trader (réel ou simulé)
    if config.get("SIMULATION_MODE", True):
        logger.info("Mode simulation activé")
        trader = SimulatedTrader(config)
    else:
        logger.info("Mode réel activé")
        trader = Trader(config)
    
    # Connecter le routeur d'ordres au trader
    trader.set_order_router(order_router)
    
    # Initialiser le gestionnaire de stratégies
    strategy_manager = TradingStrategyManager(config, trader)
    strategy_manager.momentum_analyzer = momentum_analyzer
    
    # Initialiser le filtre de tokens
    token_filter = TokenFilter(config)
    
    # Initialiser le notificateur
    notifiers = []
    
    if config.get("ENABLE_TELEGRAM", False):
        telegram_token = config.get("TELEGRAM_BOT_TOKEN", "")
        telegram_chat_id = config.get("TELEGRAM_CHAT_ID", "")
        
        if telegram_token and telegram_chat_id:
            telegram_notifier = TelegramNotifier(telegram_token, telegram_chat_id)
            notifiers.append(telegram_notifier)
    
    notifier = Notifier(notifiers)
    
    logger.info("Initialisation terminée")
    
    # Envoyer une notification de démarrage
    await notifier.send_notification("🚀 GaroLabSniperBot démarré")

async def filter_token(token_info: Any) -> bool:
    """
    Filtre un token selon les critères configurés
    
    Args:
        token_info: Informations sur le token
        
    Returns:
        True si le token passe les filtres, False sinon
    """
    # Vérifier si le token est déjà dans le cache
    if token_cache.is_token_processed(token_info.address):
        return False
    
    # Appliquer les filtres
    if not token_filter.apply_filters(token_info):
        token_cache.add_token(token_info.address, "filtered")
        return False
    
    # Vérifier si le token est déjà dans une position active
    if strategy_manager and token_info.address in [p.token_address for p in strategy_manager.get_active_positions()]:
        return False
    
    # Token valide
    return True

def calculate_position_size(token_info: Any, score: Any) -> float:
    """
    Calcule la taille de position optimale en fonction du score et de la liquidité
    
    Args:
        token_info: Informations sur le token
        score: Score de momentum
        
    Returns:
        Taille de position en SOL
    """
    base_amount = config.get("BASE_POSITION_SIZE_SOL", 0.5)
    max_amount = config.get("MAX_POSITION_SIZE_SOL", 2.0)
    
    # Ajuster la taille en fonction du score et de la liquidité
    size_multiplier = min(score.total_score * 1.5, 1.5)
    
    # Facteur de liquidité (1.0 pour 50k+ USD de liquidité)
    liquidity_factor = min(token_info.liquidity_usd / 50000, 1.0)
    
    # Calculer la taille finale
    position_size = base_amount * size_multiplier * liquidity_factor
    
    # Limiter au maximum configuré
    return min(position_size, max_amount)

async def process_token(token_info: Any) -> None:
    """
    Traite un token détecté
    
    Args:
        token_info: Informations sur le token
    """
    try:
        logger.info(f"Traitement du token {token_info.symbol} ({token_info.address})")
        
        # Analyser le momentum
        score = momentum_analyzer.get_token_score(token_info.address)
        
        if not score or score.total_score < config.get("MIN_MOMENTUM_SCORE", 0.7):
            logger.info(f"Score de momentum insuffisant pour {token_info.symbol}: "
                       f"{score.total_score if score else 'N/A'}")
            token_cache.add_token(token_info.address, "low_momentum")
            return
        
        logger.info(f"Momentum élevé détecté pour {token_info.symbol}: {score.total_score:.2f}")
        
        # Choisir la stratégie en fonction du score
        if score.total_score > 0.9:
            strategy = "quick_scalp"  # Pour les tokens à très fort momentum
        elif score.volatility_score > 0.8:
            strategy = "trailing_stop"  # Pour les tokens volatils
        else:
            strategy = "tranche_dca"  # Stratégie par défaut
        
        # Calculer la taille de position
        amount_sol = calculate_position_size(token_info, score)
        
        # Exécuter la stratégie
        trade_id = await strategy_manager.execute_strategy(strategy, token_info, amount_sol)
        
        if trade_id:
            # Ajouter au cache
            token_cache.add_token(token_info.address, "traded")
            
            # Envoyer une notification
            await notifier.send_notification(
                f"🔥 Nouveau trade: {token_info.symbol}\n"
                f"💰 Montant: {amount_sol} SOL\n"
                f"📊 Score: {score.total_score:.2f}\n"
                f"📈 Stratégie: {strategy}\n"
                f"🆔 ID: {trade_id}"
            )
        else:
            logger.warning(f"Échec de l'exécution de la stratégie pour {token_info.symbol}")
            token_cache.add_token(token_info.address, "execution_failed")
    
    except Exception as e:
        logger.error(f"Erreur lors du traitement du token {token_info.symbol}: {e}")
        logger.error(traceback.format_exc())

async def monitor_positions() -> None:
    """Surveille les positions actives"""
    if not strategy_manager:
        return
    
    positions = strategy_manager.get_active_positions()
    
    for position in positions:
        # Vérifier si un moniteur est déjà en cours
        if position.token_address not in strategy_manager.position_monitors:
            await strategy_manager.start_position_monitoring(position.token_address)

async def report_performance() -> None:
    """Génère et envoie un rapport de performance"""
    if not strategy_manager:
        return
    
    # Récupérer les statistiques de performance
    performance = strategy_manager.get_position_performance_summary()
    
    if performance["total_trades"] == 0:
        return
    
    # Générer le rapport
    report = (
        f"📊 Rapport de performance\n\n"
        f"Trades totaux: {performance['total_trades']}\n"
        f"Trades gagnants: {performance['winning_trades']} "
        f"({performance['win_rate']*100:.1f}%)\n"
        f"Profit moyen: {performance['avg_profit']:.1f}%\n"
        f"Perte moyenne: {performance['avg_loss']:.1f}%\n"
        f"P&L total: ${performance['total_profit_loss']:.2f}\n\n"
    )
    
    # Ajouter le meilleur trade
    if performance["best_trade"]:
        best = performance["best_trade"]
        report += (
            f"🏆 Meilleur trade: {best.token_symbol}\n"
            f"Profit: {best.profit_loss_percentage:.1f}%\n"
            f"Montant: {best.amount_sol} SOL\n\n"
        )
    
    # Envoyer le rapport
    await notifier.send_notification(report)

async def main_loop() -> None:
    """Boucle principale du bot"""
    last_report_time = time.time()
    report_interval = config.get("PERFORMANCE_REPORT_INTERVAL_HOURS", 6) * 3600
    
    while True:
        try:
            # Utiliser les sources de données améliorées pour détecter de nouveaux tokens
            new_tokens = await data_source.get_new_tokens_multi_source()
            
            if new_tokens:
                logger.info(f"Détecté {len(new_tokens)} nouveaux tokens")
                
                for token in new_tokens:
                    if await filter_token(token):
                        await process_token(token)
            
            # Surveiller les positions existantes
            await monitor_positions()
            
            # Générer un rapport de performance périodique
            current_time = time.time()
            if current_time - last_report_time > report_interval:
                await report_performance()
                last_report_time = current_time
            
            # Attendre avant la prochaine itération
            await asyncio.sleep(config.get("SCAN_INTERVAL_SECONDS", 10))
        
        except Exception as e:
            logger.error(f"Erreur dans la boucle principale: {e}")
            logger.error(traceback.format_exc())
            await asyncio.sleep(30)

async def main() -> None:
    """Fonction principale"""
    try:
        # Initialiser le bot
        await initialize()
        
        # Démarrer la boucle principale
        await main_loop()
    
    except KeyboardInterrupt:
        logger.info("Arrêt du bot par l'utilisateur")
    
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        logger.error(traceback.format_exc())
    
    finally:
        # Sauvegarder le cache
        if token_cache:
            token_cache.save()
        
        logger.info("Bot arrêté")

if __name__ == "__main__":
    asyncio.run(main())
