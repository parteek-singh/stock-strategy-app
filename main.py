from fastapi import FastAPI, HTTPException
from backtester import fetch_data, apply_conditions, run_backtest
from models import StrategyRequest, BacktestResponse
import pandas as pd
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or replace * with ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INTERVAL_MAP = {
    "1h": "60m",
    "30m": "30m",
    "15m": "15m",
    "1d": "1d"
}

@app.post("/backtest", response_model=BacktestResponse)
def run_strategy(strategy: StrategyRequest):
    interval = INTERVAL_MAP.get(strategy.timeframe, "1d")
    
    # Validate intraday timeframe limits
    from_dt = datetime.strptime(strategy.from_, "%Y-%m-%d")
    to_dt = datetime.strptime(strategy.to, "%Y-%m-%d")

    if interval in ["15m", "30m", "60m"]:
            max_range = to_dt - timedelta(days=60)
            if from_dt < max_range:
                raise HTTPException(
                    status_code=400,
                    detail=f"{interval} data is only available for the last 60 days. Please use a more recent 'from' date."
                )


    df = fetch_data(strategy.symbol, strategy.from_, strategy.to, interval=interval)

    df.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in df.columns]
    open_col = next(col for col in df.columns if col.startswith('Open'))
    close_col = next(col for col in df.columns if col.startswith('Close'))

    entry_col = "entry_"
    exit_col = "exit_"

    df = apply_conditions(df, strategy.entry, entry_col, close_col)
    df = apply_conditions(df, strategy.exit, exit_col, close_col)

    df[entry_col] = df[entry_col].fillna(False).astype(bool)
    df[exit_col] = df[exit_col].fillna(False).astype(bool)

    trades = run_backtest(df, entry_col, exit_col, strategy.stopLoss, open_col)
    total_pnl = sum([t['pnl_pct'] for t in trades])

    return {
        "total_trades": len(trades),
        "total_pnl_pct": round(total_pnl, 2),
        "trades": trades
    }
