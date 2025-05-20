"""
Configuration du GaroLabSniperBot
"""

import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger("config")

# Configuration par défaut
DEFAULT_CONFIG = {
    "SIMULATION_MODE": True,

    # Scan & Timing
    "SCAN_INTERVAL_SECONDS": 10,
    "PERFORMANCE_REPORT_INTERVAL_HOURS": 6,

    # Trading
    "BASE_POSITION_SIZE_SOL": 0.5,
    "MAX_POSITION_SIZE_SOL": 2.0,
    "MAX_CONCURRENT_POSITIONS": 5,
    "DEFAULT_SLIPPAGE_TOLERANCE": 0.03,

    # Filtering
    "MIN_LIQUIDITY_USD": 500,
    "MAX_FDV_USD": 10_000_000,
    "TOP_HOLDER_MAX_PERCENT": 15,

    # Notifier
    "ENABLE_TELEGRAM": False,
    "TELEGRAM_BOT_TOKEN": "",
    "TELEGRAM_CHAT_ID": "",

    # System
    "TOKEN_CACHE_FILE": "token_cache.json",

    # RPC + Wallet
    "RPC_HTTP_ENDPOINT": "https://mainnet.helius-rpc.com/?api-key=d96ee388-2b3f-405c-9865-0221d03c20c1",
    "COMMITMENT": "confirmed",
    "WALLET_PRIVATE_KEY": "",
    "WALLET_ADDRESS": ""
}

def load_config( ) -> Dict[str, Any]:
    """
    Charge la configuration depuis le fichier config.json
    Si le fichier n'existe pas, crée un fichier avec la configuration par défaut
    
    Returns:
        Dictionnaire de configuration
    """
    config_file = "config.json"
    
    # Charger depuis les variables d'environnement ou le fichier
    if os.environ.get("USE_ENV_CONFIG", "").lower() == "true":
        logger.info("Chargement de la configuration depuis les variables d'environnement")
        config = load_config_from_env()
    else:
        # Vérifier si le fichier existe
        if not os.path.exists(config_file):
            # Créer le fichier avec la configuration par défaut
            with open(config_file, "w") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            
            logger.info(f"Fichier de configuration créé: {config_file}")
            return DEFAULT_CONFIG
        
        # Charger la configuration depuis le fichier
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
            
            logger.info(f"Configuration chargée depuis: {config_file}")
        except Exception as e:
            logger.error(f"Erreur lors du chargement de la configuration: {e}")
            logger.info("Utilisation de la configuration par défaut")
            return DEFAULT_CONFIG
    
    # Fusionner avec les valeurs par défaut pour les clés manquantes
    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value
    
    return config

def load_config_from_env() -> Dict[str, Any]:
    """
    Charge la configuration depuis les variables d'environnement
    
    Returns:
        Dictionnaire de configuration
    """
    config = {}
    
    # Parcourir toutes les clés de la configuration par défaut
    for key in DEFAULT_CONFIG.keys():
        # Chercher la variable d'environnement correspondante
        env_value = os.environ.get(key)
        
        if env_value is not None:
            # Convertir la valeur selon le type attendu
            default_value = DEFAULT_CONFIG[key]
            
            if isinstance(default_value, bool):
                config[key] = env_value.lower() == "true"
            elif isinstance(default_value, int):
                config[key] = int(env_value)
            elif isinstance(default_value, float):
                config[key] = float(env_value)
            else:
                config[key] = env_value
        else:
            # Utiliser la valeur par défaut
            config[key] = DEFAULT_CONFIG[key]
    
    return config

def save_config(config: Dict[str, Any]) -> bool:
    """
    Sauvegarde la configuration dans le fichier config.json
    
    Args:
        config: Dictionnaire de configuration
        
    Returns:
        True si la sauvegarde a réussi, False sinon
    """
    config_file = "config.json"
    
    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Configuration sauvegardée dans: {config_file}")
        return True
    
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde de la configuration: {e}")
        return False
