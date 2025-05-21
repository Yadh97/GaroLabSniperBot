# Filename: performance_reporter.py

import time
import threading
import logging
from simulated_trader import SimulatedTrader
from telegram_alert import TelegramNotifier
from config import load_config

logger = logging.getLogger("PerformanceReporter")

class PerformanceReporter:
    def __init__(self, config, notifier: TelegramNotifier = None):
        self.config = config
        self.interval = 1800  # 30 minutes
        self.trader = SimulatedTrader(config_data=config, notifier=notifier)
        self.notifier = notifier

    def format_report(self, summary: dict) -> str:
        report = f"""
📊 *Performance Report (last 30 min)*

*Total Trades:* {summary['total_trades']}
*Winning Trades:* {summary['winning_trades']}
*Avg Profit:* {summary['avg_profit']:.2f}%
*Avg Loss:* {summary['avg_loss']:.2f}%
*Net PnL:* {summary['total_profit_loss']:.4f} SOL
        """

        best = summary.get("best_trade")
        if best:
            report += f"""
🏅 *Best Trade:* {best['symbol']}
    Buy @ ${best['buy_price']:.6f}
    Sell @ ${best['sell_price']:.6f}
    PnL: {best['pnl_percent']:.2f}% | Profit: {best['profit_sol']:.4f} SOL
            """

        return report.strip()

    def send_report(self):
        try:
            summary = self.trader.get_position_performance_summary()
            message = self.format_report(summary)

            if self.notifier:
                self.notifier.send_markdown(message)  # Changed here
                logger.info("[PERF REPORT] Report sent to Telegram.")
            else:
                logger.info("[PERF REPORT] \n" + message)
        except Exception as e:
            logger.error(f"[Reporter Error] Failed to send report: {e}")

    def run_loop(self):
        while True:
            self.send_report()
            time.sleep(self.interval)

def start_reporter_background_thread(config, notifier):
    reporter = PerformanceReporter(config, notifier)
    t = threading.Thread(target=reporter.run_loop, daemon=True)
    t.start()
    logger.info("✅ Performance reporter started.")
