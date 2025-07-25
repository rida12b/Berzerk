import sqlite3
import json
import csv
from pathlib import Path

DB_PATH = "berzerk.db"
EXPORT_CSV = True  # Passe à False si tu ne veux pas de CSV
CSV_PATH = "audit_decisions.csv"


def extract_decisions(limit=50):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT analyzed_at, decision_json
        FROM articles
        WHERE decision_json IS NOT NULL
        ORDER BY analyzed_at DESC
        LIMIT ?
        """,
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    results = []
    for analyzed_at, decision_json in rows:
        try:
            data = json.loads(decision_json)
            prix = data.get("prix_a_la_decision", None)
            ticker = data.get("ticker", None)
            decision = data.get("decision", None)
            results.append({
                "analyzed_at": analyzed_at,
                "ticker": ticker,
                "prix_a_la_decision": prix,
                "decision": decision,
            })
        except Exception as e:
            print(f"[WARN] Erreur parsing JSON: {e}")
    return results


def print_decisions(decisions):
    print(f"{'Date/Heure':<22} | {'Ticker':<8} | {'Prix à la décision':<18} | {'Décision':<10}")
    print("-" * 65)
    for d in decisions:
        print(f"{d['analyzed_at']:<22} | {d['ticker'] or 'N/A':<8} | {d['prix_a_la_decision'] or 'N/A':<18} | {d['decision'] or 'N/A':<10}")


def export_csv(decisions, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["analyzed_at", "ticker", "prix_a_la_decision", "decision"])
        writer.writeheader()
        for d in decisions:
            writer.writerow(d)
    print(f"Export CSV terminé : {path}")


if __name__ == "__main__":
    decisions = extract_decisions()
    print_decisions(decisions)
    if EXPORT_CSV:
        export_csv(decisions, CSV_PATH) 