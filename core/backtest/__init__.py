"""Core Backtest Package - Động cơ Backtest, Strategy Optimizer và Generator."""
from core.backtest.runner import BacktestRunner
from core.backtest.report_adapter import BacktestReportAdapter
from core.backtest.strategy_template import BaseFundStrategy, indicator_sma, indicator_volume_sma
from core.backtest.strategy_generator import StrategySkillPackage
from core.backtest.strategy_optimizer import StrategyOptimizerEngine

__all__ = [
    "BacktestRunner",
    "BacktestReportAdapter",
    "BaseFundStrategy",
    "indicator_sma",
    "indicator_volume_sma",
    "StrategySkillPackage",
    "StrategyOptimizerEngine"
]
