import pandas as pd
import yfinance as yf
import pandas_ta as ta
from typing import List

# Operator map
OPERATORS = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


# 1. Load OHLCV data
def fetch_data(symbol: str, from_date: str, to_date: str, interval: str = "1d") -> pd.DataFrame:
    print(f"📥 Fetching data for {symbol} from {from_date} to {to_date} ({interval})")
    data = yf.download(
        tickers=symbol,
        start=from_date,
        end=to_date,
        interval=interval,
        progress=False
    )
    print(f"📊 Data fetched: {len(data)} rows")
    return data
# def fetch_data(symbol, start, end, interval="1d"):
#     print(f"📥 Fetching data for {symbol} from {start} to {end} ({interval})")
#     df = yf.download(symbol, start=start, end=end, interval=interval, progress=False)
#     if df.empty:
#         raise ValueError("❌ No data returned.")
#     print(f"📊 Data fetched: {len(df)} rows")
#     return df




# . RSI (Relative Strength Index)
# Purpose: Detect overbought/oversold conditions.

# Scale: 0 to 100

# RSI < 30: Oversold → potential buy

# RSI > 70: Overbought → potential sell

# RSI = 50: Neutral

# Calculate MACD using ta.macd(df[close_col]).
# This returns a DataFrame with:
# ['MACD_12_26_9', 'MACDs_12_26_9', 'MACDh_12_26_9']

# MACD_12_26_9 → the main MACD line
# MACDs_12_26_9 → signal line (EMA of MACD)
# MACDh_12_26_9 → histogram (MACD - signal)


# You want to...	Use...	JSON Condition Example
# Check momentum direction	MACD line	        { "indicator": "MACD", "operator": ">", "value": 0 }            MACD
# Check signal crossover    MACD line vs signal	{ "indicator": "MACD_CROSS", "operator": ">", "signal": true }  MACD_CROSS
# Check momentum strength 	MACD histogram	    { "indicator": "MACD_HIST", "operator": ">", "value": 0 }

# MACD > 0 → Trend is bullish
# MACD < 0 → Trend is bearish
# MACD > Signal Line → Buy signal
# MACD < Signal Line → Sell signal
# Histogram rising → Momentum is increasing


# 2. Apply dynamic indicator conditions
def apply_conditions(df, conditions, label, close_col):
    import pandas as pd

    signal = pd.Series([True] * len(df), index=df.index)

    for cond in conditions:
        indicator = cond.indicator
        operator = cond.operator

        # RSI
        if indicator == "RSI":
            period = getattr(cond, "period", 14)
            value = cond.value
            col = f"RSI_{period}"
            df[col] = ta.rsi(df[close_col], length=period)
            cond_series = OPERATORS[operator](df[col], value)

        # EMA
        elif indicator == "EMA":
            period = getattr(cond, "period", 20)
            value = cond.value
            col = f"EMA_{period}"
            df[col] = ta.ema(df[close_col], length=period)
            cond_series = OPERATORS[operator](df[col], value)

        # EMA Crossover
        elif indicator == "EMA_CROSS":
            fast = getattr(cond, "fast", 50)
            slow = getattr(cond, "slow", 200)
            col_fast = f"EMA_{fast}"
            col_slow = f"EMA_{slow}"
            df[col_fast] = ta.ema(df[close_col], length=fast)
            df[col_slow] = ta.ema(df[close_col], length=slow)
            cond_series = OPERATORS[operator](df[col_fast], df[col_slow])

        # MACD
        elif indicator == "MACD":
            value = cond.value
            macd_cols = ta.macd(df[close_col])
            df["MACD_line"] = macd_cols["MACD_12_26_9"]
            cond_series = OPERATORS[operator](df["MACD_line"], value)

        # MACD_CROSS    
        elif indicator == "MACD_CROSS":
            macd = ta.macd(df[close_col])
            df['MACD_line'] = macd['MACD_12_26_9']
            df['MACD_signal'] = macd['MACDs_12_26_9']
            
            if operator == ">":  # MACD line crosses above signal
                cond_series = (df['MACD_line'] > df['MACD_signal']) & (df['MACD_line'].shift(1) <= df['MACD_signal'].shift(1))
            elif operator == "<":  # MACD line crosses below signal
                cond_series = (df['MACD_line'] < df['MACD_signal']) & (df['MACD_line'].shift(1) >= df['MACD_signal'].shift(1))
            else:
                raise ValueError(f"Unsupported operator for MACD_CROSS: {operator}")

        # MACD Histogram        
        elif indicator == "MACD_HIST":
            value = cond.value
            macd = ta.macd(df[close_col])
            df['MACD_hist'] = macd['MACDh_12_26_9']
            cond_series = OPERATORS[operator](df['MACD_hist'], value)

        else:
            raise ValueError(f"❌ Unsupported indicator: {indicator}")

        # Annotate which rows passed this condition
        cond_name = f"{label}__{indicator}_{operator}_{getattr(cond, 'value', '')}".strip("_")
        df[cond_name] = cond_series.fillna(False)

        # Combine signals
        signal &= cond_series.fillna(False)

    df[label] = signal.astype(bool)
    return df


# 3. Backtest logic
def run_backtest(
    df: pd.DataFrame,
    entry_col: str,
    exit_col: str,
    stop_loss_pct: float,
    open_col: str
) -> List[dict]:
    trades = []
    in_position = False
    entry_price = 0.0
    entry_index = None
    entry_reason = ""

    for i in range(1, len(df)):
        current_row = df.iloc[i]
        previous_row = df.iloc[i - 1]

        # Entry condition
        if not in_position and previous_row[entry_col]:
            in_position = True
            entry_price = current_row[open_col]
            entry_index = i
            # Log entry reasons
            entry_reason = ", ".join([
                f"{col}={current_row[col]}"
                for col in df.columns
                if col.startswith("entry_") and current_row.get(col) == True
            ])

        # If in trade, check for exit or stop loss
        elif in_position:
            exit_signal = previous_row[exit_col]
            current_price = current_row[open_col]
            price_change_pct = ((current_price - entry_price) / entry_price) * 100

            should_exit = False
            exit_reason = ""

            if exit_signal:
                should_exit = True
                exit_reason = "Exit Signal"

            elif price_change_pct <= -stop_loss_pct:
                should_exit = True
                exit_reason = "Stop Loss"

            if should_exit:
                trades.append({
                    "entry_date": str(df.index[entry_index]),
                    "exit_date": str(df.index[i]),
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(current_price, 2),
                    "pnl_pct": round(price_change_pct, 2),
                    "entry_reason": entry_reason,
                    "exit_reason": exit_reason
                })
                in_position = False
                entry_price = 0.0
                entry_index = None
                entry_reason = ""

    return trades
# def run_backtest(df, entry_col, exit_col, stop_loss_pct, open_col):
#     in_position = False
#     entry_price = 0
#     entry_index = None
#     trades = []

#     for i in range(1, len(df)):
#         entry_signal = df.iloc[i - 1][entry_col]
#         exit_signal = df.iloc[i - 1][exit_col]
#         price_now = df.iloc[i][open_col]

#         if not in_position and entry_signal:
#             in_position = True
#             entry_price = price_now
#             entry_index = i - 1

#             # Capture entry reasons
#             entry_reason_cols = [col for col in df.columns if col.startswith("entry_") and col not in [entry_col]]
#             entry_reasons = [f"{col}={df.iloc[i - 1][col]}" for col in entry_reason_cols if df.iloc[i - 1][col]]
#             entry_reason_str = ", ".join(entry_reasons)  # for inline list (default)


#         elif in_position:
#             # Stop loss hit
#             if price_now <= entry_price * (1 - stop_loss_pct / 100):
#                 exit_price = price_now
#                 exit_index = i
#                 pnl_pct = ((exit_price - entry_price) / entry_price) * 100
#                 trades.append({
#                     "entry_date": str(df.index[entry_index]),
#                     "exit_date": str(df.index[i]),
#                     "entry_price": round(entry_price, 2),
#                     "exit_price": round(exit_price, 2),
#                     "pnl_pct": round(pnl_pct, 2),
#                     "exit_type": "STOP_LOSS",
#                     "entry_reason": entry_reason_str
#                 })
#                 in_position = False

#             # Exit signal
#             elif exit_signal:
#                 exit_price = price_now
#                 exit_index = i
#                 pnl_pct = ((exit_price - entry_price) / entry_price) * 100
#                 trades.append({
#                     "entry_date": df.index[entry_index],
#                     "exit_date": df.index[exit_index],
#                     "entry_price": entry_price,
#                     "exit_price": exit_price,
#                     "pnl_pct": round(pnl_pct, 2),
#                     "exit_type": "EXIT_SIGNAL",
#                     "entry_reason": entry_reason_str
#                 })
#                 in_position = False

#     return trades