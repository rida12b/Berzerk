#!/usr/bin/env python3
"""
🔍 DIAGNOSTIC BASE DE DONNÉES BERZERK
====================================
Script simple pour analyser les décisions stockées
"""

import json
import sqlite3


def diagnostic_db():
    """Analyse le contenu de la base de données"""
    conn = sqlite3.connect("berzerk.db")
    cursor = conn.cursor()

    # Compter les articles avec décisions
    cursor.execute("SELECT COUNT(*) FROM articles WHERE decision_json IS NOT NULL")
    total_analyzed = cursor.fetchone()[0]

    # Compter les articles avec statut "analyzed"
    cursor.execute('SELECT COUNT(*) FROM articles WHERE status = "analyzed"')
    status_analyzed = cursor.fetchone()[0]

    print(f"📊 Total articles avec décisions: {total_analyzed}")
    print(f"📊 Articles avec statut 'analyzed': {status_analyzed}")

    # Examiner les décisions
    cursor.execute(
        "SELECT id, title, decision_json FROM articles WHERE decision_json IS NOT NULL LIMIT 5"
    )
    decisions = cursor.fetchall()

    print(f"\n🔍 Échantillon de {len(decisions)} décisions:")
    print("-" * 60)

    long_count = 0
    for article_id, title, decision_json in decisions:
        print(f"\n📰 Article {article_id}: {title[:50]}...")
        try:
            decision = json.loads(decision_json)

            # Vérifier le format de la décision
            if isinstance(decision, dict):
                action = decision.get("action", "N/A")
                ticker = decision.get("ticker", "N/A")

                print(f"   🎯 Action: {action}")
                print(f"   📈 Ticker: {ticker}")

                if action and action.upper() in ["LONG", "ACHETER"]:  # Compatibilité avec anciennes données
                    long_count += 1
                    print("   ✅ DÉCISION LONG/ACHAT TROUVÉE!")

            else:
                print(f"   ⚠️  Format inattendu: {type(decision)}")

        except json.JSONDecodeError as e:
            print(f"   ❌ Erreur JSON: {e}")

    print(f"\n📈 Résumé: {long_count} décision(s) LONG/ACHAT trouvée(s)")

    conn.close()


if __name__ == "__main__":
    diagnostic_db()
