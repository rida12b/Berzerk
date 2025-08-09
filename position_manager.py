#!/usr/bin/env python3
"""
BERZERK Position Manager
=======================

Gestion automatique des positions ouvertes basées sur la table `trades`.
Ferme les trades dont l'âge dépasse le seuil configuré et enregistre la P&L.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import List, Dict
import time

from send_portfolio_update import get_current_price
from dotenv import load_dotenv


# Charger les variables d'environnement (pour Telegram)
load_dotenv()


# Constantes
HOLDING_PERIOD_DAYS: int = 7


def _parse_iso_datetime(value: str) -> datetime | None:
    """Parse une datetime ISO 8601 robuste, retourne None en cas d'échec."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _fetch_open_trades(cursor: sqlite3.Cursor) -> List[Dict]:
    """Retourne les trades ouverts sous forme de dictionnaires."""
    cursor.execute(
        """
        SELECT *
        FROM trades
        WHERE status = 'OPEN'
        ORDER BY datetime(entry_at) ASC
        """
    )
    rows = cursor.fetchall()
    # Utiliser row_factory=sqlite3.Row côté connexion pour obtenir des dicts
    return [dict(row) for row in rows]


def _close_trade(cursor: sqlite3.Cursor, trade: Dict) -> None:
    """Calcule la P&L, met à jour le trade en status CLOSED et log l'opération."""
    trade_id = trade.get("id")
    ticker = trade.get("ticker", "").strip()
    decision_type = str(trade.get("decision_type", "")).upper()
    entry_price = float(trade.get("entry_price") or 0.0)
    entry_at = trade.get("entry_at", "")

    exit_price = get_current_price(ticker)
    if entry_price <= 0 or exit_price <= 0:
        # En cas d'impossibilité de calculer une P&L fiable, on ferme quand même à 0.0
        pnl_percent = 0.0
    else:
        if decision_type == "LONG":
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100.0
        elif decision_type == "SHORT":
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100.0
        else:
            pnl_percent = 0.0

    exit_at = datetime.now().isoformat()

    cursor.execute(
        """
        UPDATE trades
        SET status = 'CLOSED',
            exit_at = ?,
            exit_price = ?,
            pnl_percent = ?
        WHERE id = ?
        """,
        (exit_at, float(exit_price or 0.0), float(pnl_percent), trade_id),
    )

    # Logging console
    age_days = 0.0
    parsed_entry = _parse_iso_datetime(entry_at)
    if parsed_entry is not None:
        age_days = (datetime.now() - parsed_entry).total_seconds() / 86400.0
    print(
        f"[INFO] Trade {ticker} [{trade_id}] CLOSED after {age_days:.2f} days with P&L: {pnl_percent:+.2f}%"
    )

    # Notification Telegram
    pnl_emoji = "✅" if pnl_percent >= 0 else "🔻"
    message = (
        f"{pnl_emoji} *TRADE CLÔTURÉ* {pnl_emoji}\n\n"
        f"`{decision_type}` sur `{ticker}`\n"
        f"-----------------------------------\n"
        f"*Entrée :* `{entry_price:.2f} $`\n"
        f"*Sortie :* `{float(exit_price or 0.0):.2f} $`\n"
        f"*Résultat :* **{pnl_percent:+.2f}%**\n\n"
        f"_Position clôturée automatiquement après {HOLDING_PERIOD_DAYS} jours._"
    )
    send_telegram_notification(message)


def send_telegram_notification(message: str):
    """Envoie une notification Telegram via le bot configuré."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        print("[WARN] Variables Telegram manquantes : TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID non définies. Notification ignorée.")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
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


def get_unprocessed_news_for_ticker(ticker: str) -> List[Dict]:
    """Récupère et marque comme traitées les news non traitées pour un ticker.

    Returns:
        Liste de dicts: {id, news_title, news_link}
    """
    if not ticker:
        return []

    conn = sqlite3.connect("berzerk.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, news_title, news_link
            FROM news_events
            WHERE ticker = ? AND is_processed = 0
            """,
            (ticker,),
        )
        rows = cursor.fetchall()
        if not rows:
            return []

        ids = [row["id"] for row in rows]
        placeholders = ",".join(["?"] * len(ids))
        cursor.execute(
            f"UPDATE news_events SET is_processed = 1 WHERE id IN ({placeholders})",
            ids,
        )
        conn.commit()
        return [dict(row) for row in rows]
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main_loop() -> None:
    """Boucle principale: ferme les trades dépassant la période de détention."""
    while True:
        try:
            conn = sqlite3.connect("berzerk.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            open_trades = _fetch_open_trades(cursor)

            now = datetime.now()
            for trade in open_trades:
                entry_at = trade.get("entry_at", "")
                decision_type = str(trade.get("decision_type", "")).upper()
                ticker = trade.get("ticker", "").strip()
                if decision_type not in ("LONG", "SHORT"):
                    continue

                parsed_entry = _parse_iso_datetime(entry_at)
                if parsed_entry is None:
                    # Si la date d'entrée est invalide, fermer prudemment le trade
                    _close_trade(cursor, trade)
                    continue

                age_days = (now - parsed_entry).total_seconds() / 86400.0
                if age_days > HOLDING_PERIOD_DAYS:
                    _close_trade(cursor, trade)
                    # Après clôture, plus besoin de traiter les news pour ce trade
                    continue

                # Event-driven: traiter les news récentes non encore traitées
                unprocessed_news = get_unprocessed_news_for_ticker(ticker)
                if unprocessed_news:
                    news_titles = [n.get("news_title", "") for n in unprocessed_news]
                    news_summary = "\n".join([f"• {t}" for t in news_titles if t])
                    try:
                        # Import optionnel de l'agent de sortie
                        from agents import run_exit_strategist  # type: ignore

                        try:
                            run_exit_strategist(ticker=ticker, news_summary=news_summary)
                            print(
                                f"[INFO] Exit strategist déclenché pour {ticker} avec {len(unprocessed_news)} news."
                            )
                        except TypeError:
                            # Signature alternative si nécessaire
                            run_exit_strategist(ticker, news_summary)  # type: ignore
                    except Exception as e:
                        print(
                            f"[WARN] Impossible d'appeler run_exit_strategist pour {ticker}: {e}"
                        )

            conn.commit()
        except Exception as e:
            print(f"[ERROR] Position Manager failure: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

        # Pause de 60 secondes pour réactivité accrue
        time.sleep(60)


if __name__ == "__main__":
    main_loop()


