#!/usr/bin/env python3
"""
🎯 BERZERK BACKTESTER - Module de Validation de Performance
=====================================================

Ce module analyse les décisions d'ACHAT stockées dans la base de données
et simule leur rentabilité pour valider la performance du système BERZERK.

Stratégie de test :
- Période de détention : 7 jours calendaires
- Prix d'achat : Ouverture du jour de bourse suivant la décision
- Prix de vente : Ouverture du jour de bourse après 7 jours
- Métriques calculées : ROI, taux de réussite, performance cumulée

Auteur : BERZERK System
Date : 2024-01-XX
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta

import yfinance as yf

# Configuration
HOLDING_PERIOD_DAYS = 7
DATABASE_PATH = "berzerk.db"


class BerzerkBacktester:
    """
    Classe principale pour le backtesting des décisions BERZERK
    """

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.results = []

    def get_buy_decisions(self) -> list[dict]:
        """
        Récupère toutes les décisions d'ACHAT de la base de données
        """
        print("🔍 Recherche des décisions d'ACHAT dans la base de données...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Récupérer tous les articles avec décisions
        cursor.execute(
            """
            SELECT id, title, link, published_date, decision_json
            FROM articles
            WHERE decision_json IS NOT NULL
            AND status = "analyzed"
            ORDER BY published_date DESC
        """
        )

        rows = cursor.fetchall()
        conn.close()

        buy_decisions = []

        for row in rows:
            article_id, title, link, published_date, decision_json = row

            try:
                decision = json.loads(decision_json)

                # Nouveau format : chercher dans 'action'
                action = decision.get("action", "").upper()

                # Vérifier si c'est une décision d'ACHAT
                if action in ["ACHETER", "ACHAT", "BUY"]:
                    ticker = decision.get("ticker")

                    if ticker:  # Seulement si on a un ticker valide
                        buy_decisions.append(
                            {
                                "article_id": article_id,
                                "title": title,
                                "link": link,
                                "ticker": ticker,
                                "decision_date": datetime.fromisoformat(published_date),
                                "action": action,
                                "justification": decision.get(
                                    "justification", "Aucune justification"
                                ),
                                "allocation": decision.get(
                                    "allocation_pourcentage", 0.0
                                ),
                                "confiance": decision.get("confiance", "INCONNUE"),
                            }
                        )
                        print(
                            f"✅ Décision d'ACHAT trouvée: {ticker} ({title[:30]}...)"
                        )
                    else:
                        print(f"⚠️  Décision d'ACHAT sans ticker: {title[:30]}...")
                else:
                    print(f"📊 Décision {action}: {title[:30]}...")

            except json.JSONDecodeError as e:
                print(f"❌ Erreur JSON pour l'article {article_id}: {e}")
            except Exception as e:
                print(f"❌ Erreur lors du traitement de l'article {article_id}: {e}")

        print(f"\n📈 {len(buy_decisions)} décision(s) d'ACHAT trouvée(s)")
        return buy_decisions

    def get_next_trading_day(self, date: datetime) -> datetime:
        """
        Trouve le prochain jour de bourse après une date donnée

        Args:
            date: Date de départ

        Returns:
            datetime: Prochain jour de bourse
        """
        # Commencer par le jour suivant
        next_day = date + timedelta(days=1)

        # Éviter les weekends (lundi = 0, dimanche = 6)
        while next_day.weekday() >= 5:  # 5 = samedi, 6 = dimanche
            next_day += timedelta(days=1)

        return next_day

    def simulate_trade(self, trade: dict) -> dict | None:
        """
        Simule un trade individuel avec la stratégie de détention de 7 jours

        Args:
            trade: Dictionnaire contenant les infos du trade

        Returns:
            Dict: Résultat de la simulation ou None si erreur
        """
        ticker = trade["ticker"]
        decision_date = trade["decision_date"]

        print(
            f"📊 Simulation du trade {ticker} (décision du {decision_date.strftime('%Y-%m-%d')})"
        )

        try:
            # Dates de trading avec ajustement pour les dates très récentes
            buy_date = self.get_next_trading_day(decision_date)
            sell_date = self.get_next_trading_day(
                buy_date + timedelta(days=HOLDING_PERIOD_DAYS)
            )

            # Période de téléchargement des données avec marge étendue
            start_date = buy_date - timedelta(
                days=10
            )  # Plus de marge pour les dates récentes
            end_date = datetime.now() + timedelta(
                days=2
            )  # Utiliser date actuelle + marge

            print(
                f"   📅 Période de données: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}"
            )

            # Télécharger les données historiques
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)

            if hist.empty:
                print(f"❌ Pas de données historiques pour {ticker}")
                return None

            print(f"   📊 {len(hist)} jours de données récupérés")

            # Trouver les prix d'achat et de vente
            buy_price = None
            sell_price = None
            actual_buy_date = None
            actual_sell_date = None

            # Prix d'achat : premier prix d'ouverture disponible >= buy_date
            for date, row in hist.iterrows():
                if date.date() >= buy_date.date():
                    buy_price = row["Open"]
                    actual_buy_date = date
                    print(
                        f"   💰 Prix d'achat trouvé: {buy_price:.2f} USD le {date.strftime('%Y-%m-%d')}"
                    )
                    break

            # Si pas de prix d'achat exact, prendre le dernier prix disponible
            if buy_price is None:
                if not hist.empty:
                    last_row = hist.iloc[-1]
                    buy_price = last_row["Close"]  # Utiliser le prix de clôture
                    actual_buy_date = hist.index[-1]
                    print(
                        f"   💰 Prix d'achat (dernier disponible): {buy_price:.2f} USD le {actual_buy_date.strftime('%Y-%m-%d')}"
                    )
                else:
                    print(f"❌ Impossible de trouver un prix d'achat pour {ticker}")
                    return None

            # Prix de vente : chercher le prix après la période de détention
            if datetime.now().date() < sell_date.date():
                # Si la date de vente est dans le futur, utiliser le prix actuel
                try:
                    current_info = stock.info
                    sell_price = current_info.get("regularMarketPrice", buy_price)
                    actual_sell_date = datetime.now()
                    print(
                        f"   📈 Prix de vente (actuel): {sell_price:.2f} USD le {actual_sell_date.strftime('%Y-%m-%d')}"
                    )
                except Exception:
                    # Si pas d'info actuelle, utiliser le dernier prix historique
                    sell_price = hist.iloc[-1]["Close"]
                    actual_sell_date = hist.index[-1]
                    print(
                        f"   📈 Prix de vente (dernier historique): {sell_price:.2f} USD le {actual_sell_date.strftime('%Y-%m-%d')}"
                    )
            else:
                # Prix de vente normal : chercher dans l'historique
                for date, row in hist.iterrows():
                    if date.date() >= sell_date.date():
                        sell_price = row["Open"]
                        actual_sell_date = date
                        print(
                            f"   📈 Prix de vente trouvé: {sell_price:.2f} USD le {date.strftime('%Y-%m-%d')}"
                        )
                        break

                # Si pas trouvé, utiliser le dernier prix disponible
                if sell_price is None:
                    sell_price = hist.iloc[-1]["Close"]
                    actual_sell_date = hist.index[-1]
                    print(
                        f"   📈 Prix de vente (dernier disponible): {sell_price:.2f} USD le {actual_sell_date.strftime('%Y-%m-%d')}"
                    )

            if buy_price is None or sell_price is None:
                print(f"❌ Impossible de trouver les prix pour {ticker}")
                return None

            # Calculer la performance
            roi_percent = ((sell_price - buy_price) / buy_price) * 100

            result = {
                "ticker": ticker,
                "title": (
                    trade["title"][:50] + "..."
                    if len(trade["title"]) > 50
                    else trade["title"]
                ),
                "decision_date": decision_date,
                "buy_date": actual_buy_date,
                "sell_date": actual_sell_date,
                "buy_price": round(buy_price, 2),
                "sell_price": round(sell_price, 2),
                "roi_percent": round(roi_percent, 2),
                "allocation": trade["allocation"],
                "is_profitable": roi_percent > 0,
                "is_partial_simulation": datetime.now().date()
                < sell_date.date(),  # Indicateur si simulation partielle
            }

            status = "✅ PROFIT" if roi_percent > 0 else "❌ PERTE"
            partial_note = (
                " (⚠️ Simulation partielle)" if result["is_partial_simulation"] else ""
            )
            print(f"💹 {ticker}: {roi_percent:+.2f}% {status}{partial_note}")

            return result

        except Exception as e:
            print(f"❌ Erreur simulation {ticker}: {e}")
            return None

    def run_backtest(self) -> dict:
        """
        Exécute le backtest complet et génère le rapport de performance

        Returns:
            Dict: Résultats complets du backtest
        """
        print("🚀 DÉMARRAGE DU BACKTEST BERZERK")
        print("=" * 60)

        # Étape 1 : Extraire les décisions d'ACHAT
        buy_decisions = self.get_buy_decisions()

        if not buy_decisions:
            print("❌ Aucune décision d'ACHAT trouvée dans la base de données")
            return {"error": "No buy decisions found"}

        # Étape 2 : Simuler chaque trade
        print(f"\n🎯 Simulation de {len(buy_decisions)} trades...")
        print("-" * 60)

        successful_trades = []
        failed_trades = []

        for trade in buy_decisions:
            result = self.simulate_trade(trade)
            if result:
                successful_trades.append(result)
            else:
                failed_trades.append(trade)

        # Étape 3 : Calculer les métriques
        if not successful_trades:
            print("❌ Aucun trade n'a pu être simulé")
            return {"error": "No successful simulations"}

        # Métriques de performance
        total_trades = len(successful_trades)
        winning_trades = [t for t in successful_trades if t["is_profitable"]]
        losing_trades = [t for t in successful_trades if not t["is_profitable"]]

        win_rate = (len(winning_trades) / total_trades) * 100
        avg_roi = sum(t["roi_percent"] for t in successful_trades) / total_trades
        total_roi = sum(t["roi_percent"] for t in successful_trades)

        best_trade = max(successful_trades, key=lambda x: x["roi_percent"])
        worst_trade = min(successful_trades, key=lambda x: x["roi_percent"])

        # Stocker les résultats
        self.results = successful_trades

        return {
            "total_trades": total_trades,
            "successful_simulations": len(successful_trades),
            "failed_simulations": len(failed_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(win_rate, 2),
            "avg_roi": round(avg_roi, 2),
            "total_roi": round(total_roi, 2),
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "trades": successful_trades,
        }

    def display_results(self, results: dict):
        """
        Affiche le rapport de performance formaté

        Args:
            results: Résultats du backtest
        """
        if "error" in results:
            print(f"❌ Erreur : {results['error']}")
            return

        print("\n" + "=" * 60)
        print("📈 RAPPORT DE PERFORMANCE BERZERK")
        print("=" * 60)

        # Statistiques globales
        print("\n📊 STATISTIQUES GLOBALES")
        print("-" * 30)
        print(f"Total des trades simulés    : {results['total_trades']}")
        print(f"Simulations réussies       : {results['successful_simulations']}")
        print(f"Simulations échouées       : {results['failed_simulations']}")
        print(f"Trades gagnants            : {results['winning_trades']}")
        print(f"Trades perdants            : {results['losing_trades']}")
        print(f"Taux de réussite           : {results['win_rate']:.2f}%")
        print(f"ROI moyen par trade        : {results['avg_roi']:+.2f}%")
        print(f"ROI total cumulé           : {results['total_roi']:+.2f}%")

        # Meilleurs et pires trades
        print("\n🏆 MEILLEUR TRADE")
        print("-" * 20)
        best = results["best_trade"]
        print(f"Ticker  : {best['ticker']}")
        print(f"ROI     : {best['roi_percent']:+.2f}%")
        print(
            f"Achat   : {best['buy_price']:.2f} USD le {best['buy_date'].strftime('%Y-%m-%d')}"
        )
        print(
            f"Vente   : {best['sell_price']:.2f} USD le {best['sell_date'].strftime('%Y-%m-%d')}"
        )

        print("\n📉 PIRE TRADE")
        print("-" * 15)
        worst = results["worst_trade"]
        print(f"Ticker  : {worst['ticker']}")
        print(f"ROI     : {worst['roi_percent']:+.2f}%")
        print(
            f"Achat   : {worst['buy_price']:.2f} USD le {worst['buy_date'].strftime('%Y-%m-%d')}"
        )
        print(
            f"Vente   : {worst['sell_price']:.2f} USD le {worst['sell_date'].strftime('%Y-%m-%d')}"
        )

        # Détail de tous les trades
        print("\n📋 DÉTAIL DE TOUS LES TRADES")
        print("-" * 40)
        for trade in results["trades"]:
            status = "✅" if trade["is_profitable"] else "❌"
            print(
                f"{status} {trade['ticker']:<6} | {trade['roi_percent']:+6.2f}% | "
                f"{trade['buy_date'].strftime('%Y-%m-%d')} → {trade['sell_date'].strftime('%Y-%m-%d')} | "
                f"{trade['title']}"
            )

        # Conclusions
        print("\n🎯 CONCLUSIONS")
        print("-" * 15)
        if results["win_rate"] > 60:
            print(
                "🔥 Performance EXCELLENTE ! Le système montre une très bonne capacité prédictive."
            )
        elif results["win_rate"] > 50:
            print("👍 Performance POSITIVE. Le système bat le hasard.")
        else:
            print("⚠️  Performance À AMÉLIORER. Revoir les stratégies d'analyse.")

        if results["avg_roi"] > 2:
            print("💰 ROI moyen très attractif pour une stratégie à 7 jours.")
        elif results["avg_roi"] > 0:
            print("📈 ROI moyen positif, stratégie rentable.")
        else:
            print("📉 ROI moyen négatif, nécessite des ajustements.")


def main():
    """
    Fonction principale du backtester
    """
    print("🎯 BERZERK BACKTESTER - Validation de Performance")
    print("=" * 60)

    # Vérifier les prérequis
    import importlib.util

    missing_modules = []
    for module in ["pandas", "yfinance"]:
        if importlib.util.find_spec(module) is None:
            missing_modules.append(module)

    if missing_modules:
        print(f"❌ Erreur : Modules manquants {missing_modules}")
        print("💡 Installez les dépendances : pip install yfinance pandas")
        sys.exit(1)

    # Lancer le backtester
    backtester = BerzerkBacktester()
    results = backtester.run_backtest()
    backtester.display_results(results)

    print(f"\n🔄 Backtest terminé ! Période testée : {HOLDING_PERIOD_DAYS} jours")
    print("📊 Utilisez ces résultats pour améliorer les stratégies BERZERK.")


if __name__ == "__main__":
    main()
