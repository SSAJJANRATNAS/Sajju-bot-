import os
import time
import logging
from binance.um_futures import UMFutures
from binance.error import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Load environment variables
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_SECRET_KEY")
SYMBOL = os.getenv("TRADING_SYMBOL", "ETHUSDT")
LEVERAGE = int(os.getenv("LEVERAGE", 10))
TRADE_SIZE_USDT = float(os.getenv("TRADE_SIZE_USDT", 10))
SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", 60))
BREAKOUT_BUFFER = float(os.getenv("BREAKOUT_BUFFER", 0.05))  # % buffer above/below high/low

def get_um_futures_client():
    return UMFutures(api_key=API_KEY, api_secret=API_SECRET)

def print_wallet_balance(client):
    try:
        res = client.balance()
        usdt_balance = next((b for b in res if b["asset"] == "USDT"), None)
        wallet_balance = usdt_balance["balance"] if usdt_balance else "N/A"
        logging.info(f"USDT Wallet balance: {wallet_balance}")
    except Exception as e:
        logging.error(f"Failed to fetch wallet balance: {e}")

def set_leverage(client, symbol, leverage):
    try:
        client.change_leverage(symbol=symbol, leverage=leverage)
        logging.info(f"Leverage for {symbol} set to {leverage}x")
    except ClientError as e:
        logging.error(f"Failed to set leverage: {e}")

def fetch_candles(client, symbol, limit=15):
    try:
        klines = client.klines(symbol=symbol, interval="1m", limit=limit)
        closes = [float(k[4]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        return closes, highs, lows
    except Exception as e:
        logging.error(f"Error fetching candles: {e}")
        return [], [], []

def get_position(client, symbol):
    try:
        positions = client.position_information(symbol=symbol)
        for pos in positions:
            pos_amt = float(pos["positionAmt"])
            if pos_amt != 0:
                side = "LONG" if pos_amt > 0 else "SHORT"
                return side, pos_amt
        return None, 0
    except Exception as e:
        logging.error(f"Error fetching position: {e}")
        return None, 0

def calculate_qty(price, usdt_amount):
    return round(usdt_amount / price, 4)  # 4 decimals for most symbols

def place_order(client, symbol, side, qty):
    try:
        order = client.new_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=qty
        )
        logging.info(f"Placed {side} order: qty={qty} {symbol}")
        return order
    except ClientError as e:
        logging.error(f"Order failed: {e}")
        return None

def main():
    assert API_KEY and API_SECRET, "Set BINANCE_API_KEY and BINANCE_SECRET_KEY in environment!"
    client = get_um_futures_client()
    logging.info(f"Starting bot for {SYMBOL}")
    print_wallet_balance(client)
    set_leverage(client, SYMBOL, LEVERAGE)

    while True:
        try:
            closes, highs, lows = fetch_candles(client, SYMBOL)
            if not closes or not highs or not lows:
                logging.warning("Failed to fetch candles, retrying...")
                time.sleep(SLEEP_SECONDS)
                continue

            highest_high = max(highs)
            lowest_low = min(lows)
            current_price = closes[-1]
            long_breakout = highest_high * (1 + BREAKOUT_BUFFER / 100)
            short_breakout = lowest_low * (1 - BREAKOUT_BUFFER / 100)

            logging.info(f"{SYMBOL} | Price: {current_price} | High: {highest_high} | Low: {lowest_low}")
            logging.info(f"Breakout thresholds: LONG > {long_breakout}, SHORT < {short_breakout}")

            position_side, position_amt = get_position(client, SYMBOL)
            if position_side:
                logging.info(f"Open position: {position_side}, Amount: {position_amt}. No new trade.")
            else:
                if current_price > long_breakout:
                    qty = calculate_qty(current_price, TRADE_SIZE_USDT)
                    place_order(client, SYMBOL, "BUY", qty)
                elif current_price < short_breakout:
                    qty = calculate_qty(current_price, TRADE_SIZE_USDT)
                    place_order(client, SYMBOL, "SELL", qty)
                else:
                    logging.info("No breakout detected. Waiting for next cycle.")

        except Exception as e:
            logging.error(f"Unhandled Exception: {e}")
        time.sleep(SLEEP_SECONDS)

if __name__ == "__main__":
    main()