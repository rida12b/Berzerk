#!/usr/bin/env python3
"""
🧹 BERZERK RESET & ANALYZE - Nettoyage et Relance des Analyses
==============================================================

Ce script nettoie les anciennes analyses et relance les 20 dernières
news avec les nouveaux agents augmentés (Phase 5).
"""

import json
import sqlite3
from datetime import datetime

from orchestrator import run_berzerk_pipeline


def reset_analyses():
    """
    Nettoie les anciennes analyses de la base de données
    """
    print("🧹 Nettoyage des anciennes analyses...")

    conn = sqlite3.connect("berzerk.db")
    cursor = conn.cursor()

    # Remettre à zéro les analyses
    cursor.execute(
        """
        UPDATE articles
        SET decision_json = NULL,
            status = "pending",
            analyzed_at = NULL
        WHERE decision_json IS NOT NULL
    """
    )

    updated = cursor.rowcount
    conn.commit()

    # Compter les articles en attente
    cursor.execute('SELECT COUNT(*) FROM articles WHERE status = "pending"')
    pending = cursor.fetchone()[0]

    conn.close()

    print(f"✅ {updated} anciennes analyses supprimées")
    print(f"📝 {pending} articles en attente d'analyse")

    return pending


def get_latest_articles(limit=10):
    """
    Récupère les derniers articles en attente
    """
    print(f"🔍 Récupération des {limit} derniers articles...")

    conn = sqlite3.connect("berzerk.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, title, link, published_date
        FROM articles
        WHERE status = "pending"
        ORDER BY published_date DESC
        LIMIT ?
    """,
        (limit,),
    )

    articles = cursor.fetchall()
    conn.close()

    print(f"✅ {len(articles)} articles récupérés")
    return articles


def save_decision_to_db(article_id: int, decision_result: dict) -> bool:
    """
    Sauvegarde une décision d'investissement dans la base de données.
    """
    try:
        conn = sqlite3.connect("berzerk.db")
        cursor = conn.cursor()

        # On récupère l'objet de décision final, qui contient déjà tout (y compris le prix)
        final_decision = decision_result.get("final_decision", {})

        if not final_decision:
            print("❌ Aucune décision finale trouvée à sauvegarder.")
            return False

        # On sauvegarde directement l'objet complet sans le reconstruire
        cursor.execute(
            """
            UPDATE articles
            SET decision_json = ?,
                status = "analyzed",
                analyzed_at = ?
            WHERE id = ?
            """,
            (json.dumps(final_decision), datetime.now().isoformat(), article_id),
        )

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        return False


def analyze_articles(articles):
    """
    Lance l'analyse des articles avec les nouveaux agents augmentés
    """
    print("🚀 Lancement des analyses avec les agents augmentés...")
    print("-" * 60)

    successful_analyses = 0
    failed_analyses = 0
    saved_decisions = 0

    for i, (article_id, title, link, _published_date) in enumerate(articles, 1):
        print(f"\n🔬 [{i}/{len(articles)}] Analyse: {title[:50]}...")

        try:
            # Simuler un capital de test
            capital = 10000

            # Lancer le pipeline BERZERK complet
            result = run_berzerk_pipeline(link, capital)

            if result and not result.get("error"):
                successful_analyses += 1
                print("✅ Analyse terminée avec succès")

                # Sauvegarder la décision dans la base de données
                if save_decision_to_db(article_id, result):
                    saved_decisions += 1
                    print("💾 Décision sauvegardée dans la base de données")

                    # Afficher la décision si disponible
                    if result.get("final_decision"):
                        decision = result["final_decision"]
                        action = decision.get("decision", "N/A")
                        ticker = decision.get("ticker", "N/A")
                        allocation = decision.get("allocation_capital_pourcentage", 0)
                        print(f"🎯 Décision: {action} {ticker} ({allocation}%)")
                else:
                    print("❌ Échec de la sauvegarde")
            else:
                failed_analyses += 1
                print(
                    f"❌ Échec de l'analyse: {result.get('error', 'Erreur inconnue')}"
                )

        except Exception as e:
            failed_analyses += 1
            print(f"❌ Erreur lors de l'analyse: {e}")

    print("\n📊 RÉSULTATS DES ANALYSES")
    print("-" * 30)
    print(f"✅ Analyses réussies: {successful_analyses}")
    print(f"💾 Décisions sauvegardées: {saved_decisions}")
    print(f"❌ Analyses échouées: {failed_analyses}")
    print(f"📈 Taux de réussite: {(successful_analyses / len(articles)) * 100:.1f}%")

    return successful_analyses


def main():
    """
    Fonction principale
    """
    print("🎯 BERZERK RESET & ANALYZE")
    print("=" * 50)

    # Étape 1: Nettoyer les anciennes analyses
    pending_count = reset_analyses()

    if pending_count == 0:
        print("⚠️  Aucun article en attente d'analyse")
        return

    # Étape 2: Récupérer les derniers articles
    articles = get_latest_articles(20)

    if not articles:
        print("❌ Aucun article trouvé")
        return

    # Étape 3: Analyser les articles
    successful = analyze_articles(articles)

    print("\n🏁 TERMINÉ !")
    print(f"📊 {successful} nouvelles analyses avec agents augmentés")
    print("💡 Vous pouvez maintenant relancer: python backtester.py")


if __name__ == "__main__":
    main()
