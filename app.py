from flask import Flask, jsonify, request, render_template
import yfinance as yf
import json, os, time

app = Flask(__name__)
DATA_FILE = "portfolio_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"holdings": {}, "trades": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# Cache prices for 5 minutes to avoid hammering Yahoo Finance
price_cache = {}
CACHE_TTL = 300

def get_price(symbol):
    now = time.time()
    if symbol in price_cache and now - price_cache[symbol]["ts"] < CACHE_TTL:
        return price_cache[symbol]["price"]
    try:
        ticker = yf.Ticker(symbol + ".NS")
        info = ticker.fast_info
        price = round(float(info.last_price), 2)
        price_cache[symbol] = {"price": price, "ts": now}
        return price
    except Exception:
        try:
            ticker = yf.Ticker(symbol + ".BO")
            info = ticker.fast_info
            price = round(float(info.last_price), 2)
            price_cache[symbol] = {"price": price, "ts": now}
            return price
        except Exception:
            return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    return jsonify(load_data())

@app.route("/api/portfolio", methods=["POST"])
def save_portfolio():
    data = request.get_json()
    save_data(data)
    return jsonify({"status": "ok"})

@app.route("/api/prices", methods=["POST"])
def get_prices():
    symbols = request.get_json().get("symbols", [])
    prices = {}
    for sym in symbols:
        p = get_price(sym)
        if p:
            prices[sym] = p
    return jsonify(prices)

@app.route("/api/price/<symbol>", methods=["GET"])
def get_single_price(symbol):
    price = get_price(symbol.upper())
    if price:
        return jsonify({"symbol": symbol.upper(), "price": price})
    return jsonify({"error": "Price not found"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
