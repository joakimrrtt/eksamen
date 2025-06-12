import pandas as pd
import numpy as np
from datetime import datetime
from alpaca_trade_api import REST
import time
from queue import Queue

log_queue = Queue()

def main():
    class TradingBot:
        def __init__(self, api_key, api_secret, base_url, symbols):
            self.api = REST(api_key, api_secret, base_url)
            self.entry_prices = {symbol: None for symbol in symbols}
            self.positions = {symbol: 0 for symbol in symbols}
            self.symbols = symbols

        def log_message(self, message):
            timestamped = f"[{datetime.now()}] {message}"
            print(timestamped)
            log_queue.put(timestamped)

        def get_historical_prices(self, symbol, timeframe, limit):
            try:
                formatted_symbol = symbol if '/' in symbol else symbol.replace("USD", "/USD")
                bars = self.api.get_crypto_bars(formatted_symbol, timeframe, limit=limit).df
                self.log_message(f"Fetched {len(bars)} bars for {formatted_symbol}.")
                return bars
            except Exception as e:
                self.log_message(f"Error fetching historical prices for {symbol}: {e}")
                return pd.DataFrame()

        def calculate_ema(self, data, span):
            return data['close'].ewm(span=span, adjust=False).mean()

        def resample_data(self, data, timeframe):
            try:
                if 'timestamp' in data.columns:
                    data['timestamp'] = pd.to_datetime(data['timestamp'])
                    data.set_index('timestamp', inplace=True)
                elif data.index.name == 'timestamp':
                    data.index = pd.to_datetime(data.index)
                else:
                    self.log_message("Error: Timestamp not found in historical data.")
                    return pd.DataFrame()

                resampled = data.resample('5min').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()

                self.log_message(f"Resampled data to {timeframe}. Total rows: {len(resampled)}.")
                return resampled
            except Exception as e:
                self.log_message(f"Error during resampling: {e}")
                return pd.DataFrame()

        def ema_no_cross_last_bars(self, ema_short, ema_long, num_bars):
            for i in range(1, num_bars + 1):
                if ema_short.iloc[-i] > ema_long.iloc[-i] and ema_short.iloc[-i - 1] <= ema_long.iloc[-i - 1]:
                    return False
                if ema_short.iloc[-i] < ema_long.iloc[-i] and ema_short.iloc[-i - 1] >= ema_long.iloc[-i - 1]:
                    return False
            return True

        def graph_no_touch_last_bars(self, data, emas, num_bars):
            try:
                for i in range(1, num_bars + 1):
                    for ema in emas:
                        if data['close'].iloc[-i] <= ema.iloc[-i] <= data['high'].iloc[-i]:
                            self.log_message(f"Graph touched EMA at bar -{i}.")
                            return False
                return True
            except Exception as e:
                self.log_message(f"Error in graph_no_touch_last_bars: {e}")
                return False

        def check_trading_conditions(self, data_5min):
            try:
                ema_5min_9 = self.calculate_ema(data_5min, span=9)
                ema_5min_13 = self.calculate_ema(data_5min, span=13)
                ema_5min_21 = self.calculate_ema(data_5min, span=21)
                ema_1h_9 = self.calculate_ema(data_5min, span=108)
                ema_1h_13 = self.calculate_ema(data_5min, span=156)
                ema_1h_21 = self.calculate_ema(data_5min, span=252)

                correct_order_5min_long = ema_5min_9.iloc[-1] > ema_5min_13.iloc[-1] > ema_5min_21.iloc[-1] and ema_1h_9.iloc[-1] > ema_1h_13.iloc[-1] > ema_1h_21.iloc[-1]
                price_above_5min_emas_long = all(data_5min['close'].iloc[-1] > ema.iloc[-1] for ema in [ema_5min_9, ema_5min_13, ema_5min_21, ema_1h_9, ema_1h_13, ema_1h_21])
                no_cross_last_5_long = self.ema_no_cross_last_bars(ema_5min_9, ema_5min_13, 5)
                no_touch_last_5_long = self.graph_no_touch_last_bars(data_5min, [ema_5min_9, ema_5min_13, ema_5min_21], 5)

                correct_order_5min_short = ema_5min_9.iloc[-1] < ema_5min_13.iloc[-1] < ema_5min_21.iloc[-1] and ema_1h_9.iloc[-1] < ema_1h_13.iloc[-1] < ema_1h_21.iloc[-1]
                price_below_5min_emas_short = all(data_5min['close'].iloc[-1] < ema.iloc[-1] for ema in [ema_5min_9, ema_5min_13, ema_5min_21, ema_1h_9, ema_1h_13, ema_1h_21])
                no_cross_last_5_short = self.ema_no_cross_last_bars(ema_5min_9, ema_5min_21, 5)
                no_touch_last_5_short = self.graph_no_touch_last_bars(data_5min, [ema_5min_9, ema_5min_13, ema_5min_21], 5)

                self.log_message(f"EMA 5min: {ema_5min_9.iloc[-1]:.2f} (9-ema), {ema_5min_13.iloc[-1]:.2f} (13-ema), {ema_5min_21.iloc[-1]:.2f} (21-ema)")
                self.log_message(f"Long cond: {correct_order_5min_long}, {price_above_5min_emas_long}, {no_cross_last_5_long}, {no_touch_last_5_long}")
                self.log_message(f"Short cond: {correct_order_5min_short}, {price_below_5min_emas_short}, {no_cross_last_5_short}, {no_touch_last_5_short}")

                return (
                    correct_order_5min_long and price_above_5min_emas_long and no_cross_last_5_long and no_touch_last_5_long,
                    correct_order_5min_short and price_below_5min_emas_short and no_cross_last_5_short and no_touch_last_5_short
                )
            except Exception as e:
                self.log_message(f"Error checking trading conditions: {e}")
                return False, False

        def place_order(self, symbol, side, qty=None):
            try:
                bars = self.get_historical_prices(symbol, '1Min', 1)
                if bars.empty:
                    self.log_message(f"No data for {symbol}.")
                    return

                price = bars['close'].iloc[-1]
                self.log_message(f"{symbol} latest price: {price:.2f}")
                account = self.api.get_account()
                buying_power = float(account.cash)

                trade_value = 5000
                qty = qty or np.floor(trade_value / price)
                if side == 'buy' and qty * price > buying_power:
                    qty = np.floor(buying_power / price)

                if qty <= 0:
                    self.log_message(f"Invalid quantity for {symbol}. Skipping.")
                    return

                self.api.submit_order(
                    symbol=symbol,
                    qty=int(qty),
                    side=side,
                    type='market',
                    time_in_force='gtc'
                )
                self.log_message(f"Placed {side} order for {symbol}: {qty} units.")
            except Exception as e:
                self.log_message(f"Error placing {side} order for {symbol}: {e}")

        def exit_positions(self):
            for symbol in self.symbols:
                try:
                    position = self.api.get_position(symbol)
                    qty = float(position.qty)
                except Exception as e:
                    if "position does not exist" in str(e):
                        continue
                    self.log_message(f"Position check error for {symbol}: {e}")
                    continue

                data = self.get_historical_prices(symbol, '1Min', 1320)
                if data.empty:
                    continue
                data_5min = self.resample_data(data, '5T')
                if len(data_5min) < 21:
                    continue
                ema = self.calculate_ema(data_5min, 21)

                if qty > 0 and data_5min['low'].iloc[-1] <= ema.iloc[-1]:
                    self.place_order(symbol, 'sell', qty=qty)
                elif qty < 0 and data_5min['high'].iloc[-1] >= ema.iloc[-1]:
                    self.place_order(symbol, 'buy', qty=abs(qty))

        def run(self):
            self.log_message("Bot starting...")
            while True:
                self.exit_positions()
                for symbol in self.symbols:
                    try:
                        pos = self.api.get_position(symbol)
                        if float(pos.qty) != 0:
                            continue
                    except Exception as e:
                        if "position does not exist" not in str(e):
                            continue

                    data = self.get_historical_prices(symbol, '1Min', 1320)
                    if data.empty:
                        continue

                    data_5min = self.resample_data(data, '5T')
                    if len(data_5min) < 21:
                        continue

                    buy, short = self.check_trading_conditions(data_5min)
                    price = data['close'].iloc[-1]
                    qty = np.floor(5000 / price)

                    if buy:
                        self.place_order(symbol, 'buy', qty)
                    elif short:
                        self.place_order(symbol, 'sell', qty)

                time.sleep(300)

    if __name__ == "__main__":
        API_KEY = "PKIHY44X4MJ30IK5OHFN"
        API_SECRET = "B08Jm0Vh7vsSUNHx6aLWKXEtugcLgk0gdCfuuEiJ"
        BASE_URL = "https://paper-api.alpaca.markets"
        SYMBOLS = [
            "BTCUSD", "ETHUSD", "SOLUSD", "DOGEUSD",
            "AVAXUSD", "DOTUSD", "LINKUSD", "UNIUSD", "LTCUSD"
        ]

        bot = TradingBot(API_KEY, API_SECRET, BASE_URL, SYMBOLS)
        bot.run()
