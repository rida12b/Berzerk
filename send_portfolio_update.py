from dotenv import load_dotenv
import sqlite3
import json
import os
from datetime import datetime
import yfinance as yf

load_dotenv()

# --- Fonction utilitaire : prix actuel ---
def get_current_price(ticker: str) -> float:
    ticker = ticker.strip().replace("$", "")
    if not ticker:
        return 0.0
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d", interval="1m")
        if not data.empty:
            return float(data["Close"].iloc[-1])
        info = stock.info
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        if price:
            return float(price)
        hist = stock.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        return 0.0
    except Exception:
        return 0.0

# --- Fonction utilitaire : notification Telegram ---
def send_telegram_notification(message: str):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        print("[WARN] Variables Telegram manquantes : TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID non définies. Notification ignorée.")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        import requests
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code != 200:
            print(f"[ERROR] Notification Telegram échouée : {response.status_code} - {response.text}")
        else:
            print("[INFO] Notification Telegram envoyée avec succès.")
    except Exception as e:
        print(f"[ERROR] Exception lors de l'envoi Telegram : {e}")

# --- Extraction des positions actives ---
def fetch_active_positions():
    conn = sqlite3.connect("berzerk.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT decision_json FROM articles
        WHERE decision_json IS NOT NULL
        AND (json_extract(decision_json, '$.decision') = 'LONG' OR json_extract(decision_json, '$.decision') = 'SHORT'
             OR json_extract(decision_json, '$.action') = 'LONG' OR json_extract(decision_json, '$.action') = 'SHORT')
    """)
    rows = cursor.fetchall()
    conn.close()
    positions = []
    for (decision_json,) in rows:
        try:
            data = json.loads(decision_json)
            action = data.get("decision", data.get("action", "")).upper()
            if action not in ["LONG", "SHORT"]:
                continue
            ticker = data.get("ticker", None)
            if not ticker:
                continue
            prix_decision = float(data.get("prix_a_la_decision", 0.0))
            positions.append({
                "ticker": ticker,
                "action": action,
                "prix_decision": prix_decision,
                "justification": data.get("justification_synthetique", data.get("justification", "")),
                "analyzed_at": data.get("analyzed_at", ""),
            })
        except Exception as e:
            print(f"[WARN] Erreur parsing JSON: {e}")
    return positions

# --- Génération du résumé Telegram ---
def generate_portfolio_summary(positions):
    if not positions:
        return "⚪️ *Rapport de Portefeuille BERZERK* ⚪️\n\nAucune position active pour le moment."
    header = "📊 *Rapport de Portefeuille BERZERK*\n\n"
    table_header = "`Ticker   | Dir.  | Entrée | Actuel | P&L`\n"
    table_rows = []
    total_trades = len(positions)
    win_trades = 0
    total_pnl = 0
    for pos in positions:
        ticker = pos["ticker"]
        action = pos["action"]
        prix_decision = pos["prix_decision"]
        prix_actuel = get_current_price(ticker)
        pnl_pct = 0
        if prix_decision > 0 and prix_actuel > 0:
            if action == "LONG":
                pnl_pct = ((prix_actuel - prix_decision) / prix_decision) * 100
            elif action == "SHORT":
                pnl_pct = ((prix_decision - prix_actuel) / prix_decision) * 100
        total_pnl += pnl_pct
        if pnl_pct >= 0:
            win_trades += 1
        pnl_emoji = "✅" if pnl_pct >= 0 else "🔻"
        row = f"`{ticker:<8} | {action:<5} | {prix_decision:<6.2f} | {prix_actuel:<6.2f} | {pnl_pct:+.2f}% {pnl_emoji}`"
        table_rows.append(row)
    win_rate = (win_trades / total_trades) * 100 if total_trades else 0
    avg_pnl = total_pnl / total_trades if total_trades else 0
    summary = f"\n*Positions: {total_trades} | Taux de réussite: {win_rate:.1f}% | Perf. moyenne: {avg_pnl:+.2f}%*"
    message = header + table_header + "\n".join(table_rows) + summary
    return message

if __name__ == "__main__":
    positions = fetch_active_positions()
    message = generate_portfolio_summary(positions)
    print(message)
    send_telegram_notification(message) 