"""
Module de stratégies d'achat et de vente optimisées pour GaroLabSniperBot
Implémente des stratégies avancées pour maximiser les profits et minimiser les risques
"""

import asyncio
import time
import json
import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
import os
from decimal import Decimal
import math

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("trading_strategies")

@dataclass
class TradePosition:
    token_address: str
    token_symbol: str
    entry_price: float
    entry_time: float
    amount_sol: float
    token_amount: float
    status: str  # 'active', 'closed', 'pending'
    exit_price: Optional[float] = None
    exit_time: Optional[float] = None
    profit_loss_usd: Optional[float] = None
    profit_loss_percentage: Optional[float] = None
    strategy_name: str = "default"
    trade_id: str = ""
    take_profit_targets: List[Dict[str, Any]] = None
    stop_loss_price: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    highest_price_seen: Optional[float] = None
    notes: str = ""

class TradingStrategyManager:
    """
    Gestionnaire central des stratégies de trading
    Coordonne les différentes stratégies et exécute les ordres
    """
    
    def __init__(self, config: Dict[str, Any], trader=None):
        self.config = config
        self.trader = trader
        self.active_positions = {}  # {token_address: TradePosition}
        self.closed_positions = []  # Liste de TradePosition
        self.pending_orders = {}  # {order_id: {token_address, amount, etc.}}
        self.strategies = {}  # {strategy_name: StrategyClass}
        self.position_monitors = {}  # {token_address: asyncio.Task}
        
        # Charger les positions sauvegardées
        self.positions_file = config.get("POSITIONS_FILE", "trading_positions.json")
        self._load_positions()
        
        # Paramètres configurables
        self.max_concurrent_positions = config.get("MAX_CONCURRENT_POSITIONS", 5)
        self.max_position_size_sol = config.get("MAX_POSITION_SIZE_SOL", 1.0)
        self.default_slippage_tolerance = config.get("DEFAULT_SLIPPAGE_TOLERANCE", 0.03)  # 3%
        
        # Enregistrer les stratégies disponibles
        self._register_strategies()
        
        logger.info(f"Initialized TradingStrategyManager with {len(self.strategies)} strategies")
    
    def _register_strategies(self):
        """Enregistre les stratégies de trading disponibles"""
        self.strategies = {
            "tranche_dca": TrancheStrategy(self.config, self),
            "take_profit_ladder": TakeProfitLadderStrategy(self.config, self),
            "trailing_stop": TrailingStopStrategy(self.config, self),
            "momentum_based": MomentumBasedStrategy(self.config, self),
            "smart_entry": SmartEntryStrategy(self.config, self),
            "quick_scalp": QuickScalpStrategy(self.config, self)
        }
    
    def _load_positions(self):
        """Charge les positions de trading depuis le fichier"""
        try:
            if os.path.exists(self.positions_file):
                with open(self.positions_file, 'r') as f:
                    data = json.load(f)
                
                # Charger les positions actives
                if "active_positions" in data:
                    for addr, pos_data in data["active_positions"].items():
                        self.active_positions[addr] = TradePosition(
                            token_address=pos_data["token_address"],
                            token_symbol=pos_data["token_symbol"],
                            entry_price=pos_data["entry_price"],
                            entry_time=pos_data["entry_time"],
                            amount_sol=pos_data["amount_sol"],
                            token_amount=pos_data["token_amount"],
                            status=pos_data["status"],
                            strategy_name=pos_data.get("strategy_name", "default"),
                            trade_id=pos_data.get("trade_id", ""),
                            take_profit_targets=pos_data.get("take_profit_targets"),
                            stop_loss_price=pos_data.get("stop_loss_price"),
                            trailing_stop_price=pos_data.get("trailing_stop_price"),
                            highest_price_seen=pos_data.get("highest_price_seen"),
                            notes=pos_data.get("notes", "")
                        )
                
                # Charger les positions fermées
                if "closed_positions" in data:
                    for pos_data in data["closed_positions"]:
                        self.closed_positions.append(TradePosition(
                            token_address=pos_data["token_address"],
                            token_symbol=pos_data["token_symbol"],
                            entry_price=pos_data["entry_price"],
                            entry_time=pos_data["entry_time"],
                            amount_sol=pos_data["amount_sol"],
                            token_amount=pos_data["token_amount"],
                            status=pos_data["status"],
                            exit_price=pos_data.get("exit_price"),
                            exit_time=pos_data.get("exit_time"),
                            profit_loss_usd=pos_data.get("profit_loss_usd"),
                            profit_loss_percentage=pos_data.get("profit_loss_percentage"),
                            strategy_name=pos_data.get("strategy_name", "default"),
                            trade_id=pos_data.get("trade_id", ""),
                            notes=pos_data.get("notes", "")
                        ))
                
                logger.info(f"Loaded {len(self.active_positions)} active positions and "
                           f"{len(self.closed_positions)} closed positions")
        
        except Exception as e:
            logger.error(f"Error loading positions: {e}")
    
    def _save_positions(self):
        """Sauvegarde les positions de trading dans le fichier"""
        try:
            # Convertir les positions actives en dictionnaires
            active_positions_dict = {}
            for addr, pos in self.active_positions.items():
                active_positions_dict[addr] = {
                    "token_address": pos.token_address,
                    "token_symbol": pos.token_symbol,
                    "entry_price": pos.entry_price,
                    "entry_time": pos.entry_time,
                    "amount_sol": pos.amount_sol,
                    "token_amount": pos.token_amount,
                    "status": pos.status,
                    "strategy_name": pos.strategy_name,
                    "trade_id": pos.trade_id,
                    "take_profit_targets": pos.take_profit_targets,
                    "stop_loss_price": pos.stop_loss_price,
                    "trailing_stop_price": pos.trailing_stop_price,
                    "highest_price_seen": pos.highest_price_seen,
                    "notes": pos.notes
                }
            
            # Convertir les positions fermées en dictionnaires
            closed_positions_list = []
            for pos in self.closed_positions:
                closed_positions_list.append({
                    "token_address": pos.token_address,
                    "token_symbol": pos.token_symbol,
                    "entry_price": pos.entry_price,
                    "entry_time": pos.entry_time,
                    "amount_sol": pos.amount_sol,
                    "token_amount": pos.token_amount,
                    "status": pos.status,
                    "exit_price": pos.exit_price,
                    "exit_time": pos.exit_time,
                    "profit_loss_usd": pos.profit_loss_usd,
                    "profit_loss_percentage": pos.profit_loss_percentage,
                    "strategy_name": pos.strategy_name,
                    "trade_id": pos.trade_id,
                    "notes": pos.notes
                })
            
            # Sauvegarder dans le fichier
            data = {
                "active_positions": active_positions_dict,
                "closed_positions": closed_positions_list,
                "last_update": time.time()
            }
            
            with open(self.positions_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Saved {len(self.active_positions)} active positions and "
                        f"{len(self.closed_positions)} closed positions")
        
        except Exception as e:
            logger.error(f"Error saving positions: {e}")
    
    async def execute_strategy(self, strategy_name: str, token_info: Any, amount_sol: float, 
                              params: Dict[str, Any] = None) -> Optional[str]:
        """
        Exécute une stratégie de trading pour un token donné
        
        Args:
            strategy_name: Nom de la stratégie à exécuter
            token_info: Informations sur le token
            amount_sol: Montant à investir en SOL
            params: Paramètres spécifiques à la stratégie
            
        Returns:
            ID de la transaction ou None en cas d'échec
        """
        # Vérifier si la stratégie existe
        if strategy_name not in self.strategies:
            logger.error(f"Strategy '{strategy_name}' not found")
            return None
        
        # Vérifier si on peut ouvrir une nouvelle position
        if len(self.active_positions) >= self.max_concurrent_positions:
            logger.warning(f"Maximum number of concurrent positions reached ({self.max_concurrent_positions})")
            return None
        
        # Vérifier si le token est déjà dans une position active
        if token_info.address in self.active_positions:
            logger.warning(f"Already have an active position for {token_info.symbol}")
            return None
        
        # Limiter le montant de la position
        amount_sol = min(amount_sol, self.max_position_size_sol)
        
        # Exécuter la stratégie
        strategy = self.strategies[strategy_name]
        trade_id = await strategy.execute(token_info, amount_sol, params or {})
        
        if trade_id:
            logger.info(f"Successfully executed {strategy_name} for {token_info.symbol} "
                       f"with {amount_sol} SOL (Trade ID: {trade_id})")
        else:
            logger.error(f"Failed to execute {strategy_name} for {token_info.symbol}")
        
        return trade_id
    
    async def execute_buy(self, token_info: Any, amount_sol: float, slippage: float = None) -> Optional[Dict[str, Any]]:
        """
        Exécute un achat de token
        
        Args:
            token_info: Informations sur le token
            amount_sol: Montant à investir en SOL
            slippage: Tolérance de slippage (utilise la valeur par défaut si None)
            
        Returns:
            Détails de la transaction ou None en cas d'échec
        """
        if not self.trader:
            logger.error("No trader available to execute buy")
            return None
        
        if slippage is None:
            slippage = self.default_slippage_tolerance
        
        try:
            # Exécuter l'achat via le trader
            result = await self.trader.buy_token(
                token_address=token_info.address,
                amount_sol=amount_sol,
                slippage_percent=slippage * 100
            )
            
            if not result or not result.get("success"):
                logger.error(f"Buy failed for {token_info.symbol}: {result.get('error', 'Unknown error')}")
                return None
            
            # Créer une position
            token_amount = result.get("token_amount", 0)
            entry_price = result.get("price", token_info.price_usd)
            
            position = TradePosition(
                token_address=token_info.address,
                token_symbol=token_info.symbol,
                entry_price=entry_price,
                entry_time=time.time(),
                amount_sol=amount_sol,
                token_amount=token_amount,
                status="active",
                trade_id=result.get("transaction_id", "")
            )
            
            # Enregistrer la position
            self.active_positions[token_info.address] = position
            self._save_positions()
            
            logger.info(f"Bought {token_amount} {token_info.symbol} for {amount_sol} SOL "
                       f"at ${entry_price:.6f}")
            
            return {
                "success": True,
                "position": position,
                "transaction_id": result.get("transaction_id", ""),
                "token_amount": token_amount,
                "price": entry_price
            }
        
        except Exception as e:
            logger.error(f"Error executing buy for {token_info.symbol}: {e}")
            return None
    
    async def execute_sell(self, token_address: str, percentage: float = 1.0, slippage: float = None) -> Optional[Dict[str, Any]]:

        if not self.trader:
            logger.error("No trader available to execute sell")
            return None
        
        if token_address not in self.active_positions:
            logger.error(f"No active position found for token {token_address}")
            return None
        
        position = self.active_positions[token_address]
        
        if slippage is None:
            slippage = self.default_slippage_tolerance
        
        try:
            # Calculer la quantité à vendre
            token_amount_to_sell = position.token_amount * percentage
            
            # Exécuter la vente via le trader
            result = await self.trader.sell_token(
                token_address=token_address,
                token_amount=token_amount_to_sell,
                slippage_percent=slippage * 100
            )
            
            if not result or not result.get("success"):
                logger.error(f"Sell failed for {position.token_symbol}: {result.get('error', 'Unknown error')}")
                return None
            
            # Mettre à jour ou fermer la position
            exit_price = result.get("price", 0)
            exit_time = time.time()
            
            if percentage >= 0.999:  # Vente complète (avec marge d'erreur)
                # Calculer le P&L
                profit_loss_usd = (exit_price - position.entry_price) * position.token_amount
                profit_loss_percentage = ((exit_price / position.entry_price) - 1) * 100
                
                # Mettre à jour la position
                position.exit_price = exit_price
                position.exit_time = exit_time
                position.profit_loss_usd = profit_loss_usd
                position.profit_loss_percentage = profit_loss_percentage
                position.status = "closed"
                
                # Déplacer vers les positions fermées
                self.closed_positions.append(position)
                del self.active_positions[token_address]
                
                # Arrêter le moniteur de position s'il existe
                if token_address in self.position_monitors:
                    self.position_monitors[token_address].cancel()
                    del self.position_monitors[token_address]
                
                logger.info(f"Sold all {position.token_symbol} for ${exit_price:.6f} "
                           f"(P&L: {profit_loss_percentage:.2f}%)")
            else:
                # Vente partielle
                sold_amount = position.token_amount * percentage
                remaining_amount = position.token_amount - sold_amount
                
                # Calculer le P&L partiel
                profit_loss_usd = (exit_price - position.entry_price) * sold_amount
                profit_loss_percentage = ((exit_price / position.entry_price) - 1) * 100
                
                # Créer une position fermée pour la partie vendue
                closed_position = TradePosition(
                    token_address=position.token_address,
                    token_symbol=position.token_symbol,
                    entry_price=position.entry_price,
                    entry_time=position.entry_time,
                    amount_sol=position.amount_sol * percentage,
                    token_amount=sold_amount,
                    status="closed",
                    exit_price=exit_price,
                    exit_time=exit_time,
                    profit_loss_usd=profit_loss_usd,
                    profit_loss_percentage=profit_loss_percentage,
                    strategy_name=position.strategy_name,
                    trade_id=position.trade_id,
                    notes=f"Partial sell ({percentage*100:.0f}%)"
                )
                
                self.closed_positions.append(closed_position)
                
                # Mettre à jour la position active
                position.amount_sol = position.amount_sol * (1 - percentage)
                position.token_amount = remaining_amount
                
                logger.info(f"Sold {percentage*100:.0f}% of {position.token_symbol} "
                           f"for ${exit_price:.6f} (P&L: {profit_loss_percentage:.2f}%)")
            
            # Sauvegarder les positions
            self._save_positions()
            
            return {
                "success": True,
                "transaction_id": result.get("transaction_id", ""),
                "price": exit_price,
                "profit_loss_percentage": profit_loss_percentage,
                "profit_loss_usd": profit_loss_usd
            }
        
        except Exception as e:
            logger.error(f"Error executing sell for {position.token_symbol}: {e}")
            return None
