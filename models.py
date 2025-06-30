from pydantic import BaseModel
from typing import List, Optional, Union, Literal

class Condition(BaseModel):
    indicator: str
    operator: str
    value: Optional[Union[int, float]] = None
    period: Optional[int] = None
    fast: Optional[int] = None
    slow: Optional[int] = None

class StrategyRequest(BaseModel):
    symbol: str
    entry: List[Condition]
    exit: List[Condition]
    stopLoss: float
    # timeframe: str
    timeframe: Literal["1d", "1h", "30m", "15m"]
    from_: str
    to: str

class Trade(BaseModel):
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    exit_type: str
    entry_reason: str

class StrategyResponse(BaseModel):
    total_trades: int
    total_pnl_pct: float
    trades: List[Trade]

class TradeResponse(BaseModel):
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    entry_reason: Optional[str]
    exit_reason: Optional[str]

class BacktestResponse(BaseModel):
    total_trades: int
    total_pnl_pct: float
    trades: List[TradeResponse]
