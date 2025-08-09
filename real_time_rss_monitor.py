#!/usr/bin/env python3
"""
🚀 BERZERK Real-Time RSS Monitor - Surveillance RSS Quasi-Instantanée
=====================================================================

Ce système avancé surveille les flux RSS en temps quasi-réel avec :
- Polling haute fréquence (30-60 secondes)
- Optimisations HTTP (ETags, Last-Modified, conditional requests)
- Threading asynchrone pour éviter les blocages
- Détection intelligente des changements
- Analyse automatique instantanée

Architecture Temps Réel :
- Pas d'attente bloquante (utilise threading)
- Réactivité événementielle
- Gestion des erreurs robuste
- Intégration avec le pipeline BERZERK existant

Usage: python real_time_rss_monitor.py [poll_interval_seconds]
Arrêt: Ctrl+C
"""

import hashlib
import re
import json
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser
import requests

# Import des modules BERZERK
from berzerk_lab import init_db
import configparser
from orchestrator import run_berzerk_pipeline, send_telegram_notification


@dataclass
class FeedState:
    """État d'un flux RSS avec optimisations HTTP"""

    url: str
    last_modified: str | None = None
    etag: str | None = None
    last_check: datetime | None = None
    last_content_hash: str | None = None
    consecutive_errors: int = 0
    # articles_cache supprimé - causait des doublons après redémarrage

    def should_check(self, min_interval: int) -> bool:
        """Détermine si le flux doit être vérifié maintenant"""
        if self.last_check is None:
            return True

        # Algorithme adaptatif : plus d'erreurs = moins de vérifications
        if self.consecutive_errors > 0:
            penalty = min(self.consecutive_errors * 30, 300)  # Max 5 minutes de penalty
            return (datetime.now() - self.last_check).total_seconds() > (
                min_interval + penalty
            )

        return (datetime.now() - self.last_check).total_seconds() >= min_interval


class RealTimeRSSMonitor:
    """Surveillant RSS temps réel avec optimisations avancées"""

    def __init__(self, poll_interval: int = 30, capital: float = 25000.0):
        # Heure de démarrage du moniteur (filtre temporel)
        self.startup_time = datetime.now()
        self.poll_interval = poll_interval  # En secondes
        self.capital = capital
        self.feeds_state: dict[str, FeedState] = {}
        self.running = False
        self.stats = {
            "total_checks": 0,
            "new_articles_found": 0,
            "analyses_completed": 0,
            "errors": 0,
            "start_time": datetime.now(),
        }

        # Configuration des requêtes HTTP optimisées
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "BERZERK-RSS-Monitor/1.0 (Real-Time News Analysis)",
                "Accept": "application/rss+xml, application/xml, text/xml",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
        )

        # Initialisation
        self.init_feeds_state()

        print("🚀 BERZERK Real-Time RSS Monitor initialisé")
        print(f"   ⚡ Polling: {poll_interval} secondes (haute fréquence)")
        feeds = self.load_feeds_from_config()
        print(f"   📈 Flux RSS: {len(feeds)} source(s)")
        for feed_name, feed_url in feeds.items():
            print(f"   📡 {feed_name}: {feed_url}")
        print(f"   💰 Capital: {capital:,.2f}€")
        print("   🔄 Optimisations: ETags, Last-Modified, Threading")
        self.log(
            f"✅ Moniteur démarré. Seules les news publiées après {self.startup_time.strftime('%Y-%m-%d %H:%M:%S')} seront traitées.",
            "SUCCESS",
        )
        print("-" * 70)

    def init_feeds_state(self):
        """Initialise l'état de chaque flux RSS"""
        feeds = self.load_feeds_from_config()
        for _feed_name, feed_url in feeds.items():
            self.feeds_state[feed_url] = FeedState(url=feed_url)

    def load_feeds_from_config(self) -> dict[str, str]:
        """Charge les flux RSS depuis config.ini (section [RSS_FEEDS])."""
        config = configparser.ConfigParser()
        config.read("config.ini")
        if "RSS_FEEDS" not in config:
            return {}
        return dict(config["RSS_FEEDS"])  # name -> url

    def log(self, message: str, level: str = "INFO"):
        """Logger avec timestamp et niveau"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        level_emoji = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DETECTION": "🔍",
        }.get(level, "📝")
        print(f"⚡ [{timestamp}] {level_emoji} {message}")

    def calculate_content_hash(self, content: str) -> str:
        """Calcule un hash du contenu pour détecter les changements"""
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def check_feed_optimized(self, feed_state: FeedState) -> list[dict]:
        """Vérifie un flux RSS avec optimisations HTTP"""
        try:
            headers = {}

            # Optimisations HTTP conditionnelles
            if feed_state.etag:
                headers["If-None-Match"] = feed_state.etag
            if feed_state.last_modified:
                headers["If-Modified-Since"] = feed_state.last_modified

            # Requête HTTP avec timeout court
            response = self.session.get(feed_state.url, headers=headers, timeout=10)

            feed_state.last_check = datetime.now()
            self.stats["total_checks"] += 1

            # Gestion des codes de statut HTTP
            if response.status_code == 304:
                # Not Modified - aucun changement
                self.log(f"🔄 Pas de changement: {feed_state.url[:50]}...")
                feed_state.consecutive_errors = 0
                return []

            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")

            # Mise à jour des métadonnées de cache
            feed_state.etag = response.headers.get("ETag")
            feed_state.last_modified = response.headers.get("Last-Modified")

            # Vérification du hash du contenu
            content_hash = self.calculate_content_hash(response.text)
            if feed_state.last_content_hash == content_hash:
                self.log(f"🔄 Contenu identique: {feed_state.url[:50]}...")
                feed_state.consecutive_errors = 0
                return []

            feed_state.last_content_hash = content_hash

            # Parsing RSS
            feed = feedparser.parse(response.text)

            if feed.bozo:
                self.log(f"⚠️ Feed mal formé: {feed_state.url[:50]}...")

            # Filtrage des nouveaux articles - LOGIQUE SIMPLIFIÉE
            new_articles = []
            for entry in feed.entries:
                article_link = entry.get("link", "")

                # Extraction des métadonnées
                published_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, "published"):
                    try:
                        published_date = parsedate_to_datetime(entry.published)
                    except Exception:
                        published_date = datetime.now()
                else:
                    published_date = datetime.now()

                # Nouveau filtre temporel: ignorer les articles plus anciens que l'heure de démarrage
                if published_date < self.startup_time:
                    continue

                article = {
                    "title": entry.get("title", "Titre non disponible"),
                    "link": article_link,
                    "published_date": published_date,
                    "summary": entry.get("summary", ""),
                    "source": feed_state.url,
                    "discovered_at": datetime.now(),
                }

                new_articles.append(article)

            # Succès - reset des erreurs
            feed_state.consecutive_errors = 0

            if new_articles:
                self.log(
                    f"🎯 {len(new_articles)} VRAIS nouveaux articles détectés sur {feed_state.url[:50]}...",
                    "DETECTION",
                )
                self.stats["new_articles_found"] += len(new_articles)

                # Publier des événements de news pour chaque ticker identifié
                try:
                    for article in new_articles:
                        title = article.get("title", "")
                        summary = article.get("summary", "")
                        tickers_in_title = identify_tickers_in_text(title)
                        tickers_in_summary = identify_tickers_in_text(summary)
                        for ticker in set(tickers_in_title + tickers_in_summary):
                            try:
                                publish_news_event(ticker, article)
                                self.log(f"🗞️ Event publié: {ticker} ← '{title[:40]}...'", "SUCCESS")
                            except Exception as e:
                                self.log(f"⚠️ Échec publication event {ticker}: {e}")
                except Exception as e:
                    self.log(f"⚠️ Erreur lors de la publication des news_events: {e}")

            return new_articles

        except Exception as e:
            feed_state.consecutive_errors += 1
            self.stats["errors"] += 1
            self.log(f"❌ Erreur sur {feed_state.url[:50]}: {e}")
            return []

    def store_article(self, article: dict):
        """Stocke un article dans la base de données"""
        try:
            conn = sqlite3.connect("berzerk.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO articles
                (title, link, published_date, source, status, published_str)
                VALUES (?, ?, ?, ?, 'pending', ?)
            """,
                (
                    article["title"],
                    article["link"],
                    article["published_date"].isoformat(),
                    article["source"],
                    article.get(
                        "summary", "RSS Feed"
                    ),  # Utilise summary comme published_str
                ),
            )

            conn.commit()
            conn.close()

            if cursor.rowcount > 0:
                self.log(f"💾 Article stocké: {article['title'][:50]}...")

        except Exception as e:
            self.log(f"❌ Erreur stockage: {e}")

    def analyze_article_realtime(self, article: dict) -> dict | None:
        """Analyse un article en temps réel avec le pipeline BERZERK"""
        try:
            self.log(f"🤖 Analyse TEMPS RÉEL: {article['title'][:50]}...")

            # Lancement du pipeline complet
            result = run_berzerk_pipeline(article["link"], self.capital)

            if result and "final_decision" in result:
                # Sauvegarde de la décision
                self.save_decision_to_db(article["link"], result["final_decision"])

                # Statistiques
                self.stats["analyses_completed"] += 1

                # Affichage du résultat
                decision = result["final_decision"]
                action = decision.get("decision", "INCONNU")

                # --- DÉBUT DU TEMPLATE FINAL ---
                if action in ["LONG", "SHORT"]:
                    ticker = decision.get("ticker", "N/A")
                    prix_decision = decision.get("prix_a_la_decision", 0.0)
                    confiance = decision.get("confiance", "INCONNUE")
                    justification = decision.get("justification_synthetique", "N/A")
                    article_link = article["link"]

                    if action == "LONG":
                        signal_color = "🟢"
                        action_label = "ACHAT (LONG)"
                    else:  # SHORT
                        signal_color = "🔴"
                        action_label = "VENTE (SHORT)"

                    message = (
                        f"{signal_color} *NOUVEAU SIGNAL BERZERK*\n\n"
                        f"*{action_label}:* `{ticker}`\n"
                        f"-----------------------------------\n"
                        f"💰 *Prix d'Entrée:* `{prix_decision:.2f} $`\n"
                        f"💪 *Confiance:* **{confiance.upper()}**\n\n"
                        f"> {justification}\n\n"
                        f"📰 [Lire l'article source]({article_link})"
                    )
                    send_telegram_notification(message)
                # --- FIN DU TEMPLATE FINAL ---

                if action in ["LONG", "ACHETER"]:  # Compatibilité avec anciennes données
                    self.log(
                        f"🚀 SIGNAL LONG IDENTIFIÉ: {article['title'][:50]}...", "SUCCESS"
                    )
                    ticker = decision.get("ticker_cible", "N/A")
                    allocation = decision.get("allocation_pourcentage", 0)
                    self.log(f"   💰 Ticker: {ticker}, Allocation: {allocation}%")
                elif action == "SURVEILLER":
                    self.log(f"👀 SURVEILLANCE: {article['title'][:50]}...")
                else:
                    self.log(f"✅ Analyse terminée: {action}")

                return result
            else:
                self.log(f"⚠️ Échec d'analyse: {article['title'][:50]}...")
                return None

        except Exception as e:
            self.log(f"❌ Erreur analyse temps réel: {e}")
            return None

    def save_decision_to_db(self, article_link: str, decision: dict):
        """Sauvegarde la décision dans la base de données"""
        try:
            conn = sqlite3.connect("berzerk.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE articles
                SET decision_json = ?,
                    status = 'analyzed',
                    analyzed_at = ?
                WHERE link = ?
            """,
                (
                    json.dumps(decision, ensure_ascii=False),
                    datetime.now().isoformat(),
                    article_link,
                ),
            )

            # Nouvelle logique: créer un trade si décision LONG/SHORT
            try:
                decision_type = str(decision.get("decision", "")).upper()
                if decision_type in ("LONG", "SHORT"):
                    # Récupérer l'id de l'article concerné
                    cursor.execute(
                        "SELECT id FROM articles WHERE link = ?",
                        (article_link,),
                    )
                    row = cursor.fetchone()
                    if row:
                        article_id = row[0]
                        ticker = decision.get("ticker") or ""
                        entry_price = decision.get("prix_a_la_decision") or 0.0
                        entry_at = datetime.now().isoformat()

                        cursor.execute(
                            """
                            INSERT OR IGNORE INTO trades (
                                article_id, ticker, decision_type, entry_at, entry_price, status
                            ) VALUES (?, ?, ?, ?, ?, 'OPEN')
                            """,
                            (
                                article_id,
                                ticker,
                                decision_type,
                                entry_at,
                                float(entry_price) if entry_price is not None else 0.0,
                            ),
                        )

                        self.log(
                            f"✅ Trade enregistré: {decision_type} {ticker} @ {entry_price}",
                            "SUCCESS",
                        )
                    else:
                        self.log(
                            "⚠️ Impossible de créer le trade: article introuvable après UPDATE",
                            "WARNING",
                        )
            except Exception as e:
                self.log(f"⚠️ Erreur lors de la création du trade: {e}")

            conn.commit()
            conn.close()

        except Exception as e:
            self.log(f"❌ Erreur sauvegarde décision: {e}")

    def monitoring_thread(self):
        """Thread principal de surveillance"""
        self.log("🔄 Thread de surveillance démarré")

        while self.running:
            try:
                # Vérifier chaque flux RSS
                for _feed_url, feed_state in self.feeds_state.items():
                    if not self.running:
                        break

                    # Vérifier si le flux doit être contrôlé
                    if feed_state.should_check(self.poll_interval):
                        new_articles = self.check_feed_optimized(feed_state)

                        # Traiter les nouveaux articles
                        for article in new_articles:
                            if not self.running:
                                break

                            # Stockage en base
                            self.store_article(article)

                            # Analyse immédiate en arrière-plan
                            threading.Thread(
                                target=self.analyze_article_realtime,
                                args=(article,),
                                daemon=True,
                            ).start()

                # Pause courte avant le prochain cycle
                time.sleep(1)

            except Exception as e:
                self.log(f"❌ Erreur dans le thread de surveillance: {e}")
                time.sleep(5)  # Pause plus longue en cas d'erreur

        self.log("🛑 Thread de surveillance arrêté")

    def display_stats(self):
        """Affiche les statistiques en temps réel"""
        uptime = datetime.now() - self.stats["start_time"]

        print("\n" + "=" * 50)
        print("📊 STATISTIQUES TEMPS RÉEL")
        print("=" * 50)
        print(f"⏱️  Uptime: {uptime}")
        print(f"🔄 Vérifications totales: {self.stats['total_checks']}")
        print(f"📈 Nouveaux articles: {self.stats['new_articles_found']}")
        print(f"🤖 Analyses complètes: {self.stats['analyses_completed']}")
        print(f"❌ Erreurs: {self.stats['errors']}")
        # Cache supprimé: on n'utilise plus de cache d'articles en mémoire
        print("=" * 50)

    def start(self):
        """Démarre la surveillance temps réel"""
        self.log("🚀 DÉMARRAGE DE LA SURVEILLANCE TEMPS RÉEL", "SUCCESS")
        self.log(f"⚡ Polling: {self.poll_interval} secondes")
        self.log("⏹️  Arrêt: Ctrl+C")

        # Initialiser la base de données
        init_db()

        # Démarrer le thread de surveillance
        self.running = True
        monitor_thread = threading.Thread(target=self.monitoring_thread, daemon=True)
        monitor_thread.start()

        try:
            # Boucle principale avec affichage des stats
            while True:
                time.sleep(30)  # Afficher les stats toutes les 30 secondes
                self.display_stats()

        except KeyboardInterrupt:
            self.log("🛑 Arrêt demandé par l'utilisateur", "WARNING")
        finally:
            self.running = False
            self.log("👋 Surveillance temps réel arrêtée", "SUCCESS")
            self.display_stats()


def identify_tickers_in_text(text: str) -> list[str]:
    """Identifie des tickers basés sur des mots en MAJUSCULES (2 à 5 lettres)."""
    if not text:
        return []
    try:
        return re.findall(r"\b[A-Z]{2,5}\b", text)
    except Exception:
        return []


def publish_news_event(ticker: str, article: dict) -> None:
    """Publie un événement de news dans la table news_events."""
    conn = sqlite3.connect("berzerk.db")
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO news_events (ticker, news_title, news_link, detected_at, is_processed)
            VALUES (?, ?, ?, ?, 0)
            """,
            (
                ticker.strip(),
                article.get("title", "Titre non disponible"),
                article.get("link", ""),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    def store_article(self, article: dict):
        """Stocke un article dans la base de données"""
        try:
            conn = sqlite3.connect("berzerk.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO articles
                (title, link, published_date, source, status, published_str)
                VALUES (?, ?, ?, ?, 'pending', ?)
            """,
                (
                    article["title"],
                    article["link"],
                    article["published_date"].isoformat(),
                    article["source"],
                    article.get(
                        "summary", "RSS Feed"
                    ),  # Utilise summary comme published_str
                ),
            )

            conn.commit()
            conn.close()

            if cursor.rowcount > 0:
                self.log(f"💾 Article stocké: {article['title'][:50]}...")

        except Exception as e:
            self.log(f"❌ Erreur stockage: {e}")

    def analyze_article_realtime(self, article: dict) -> dict | None:
        """Analyse un article en temps réel avec le pipeline BERZERK"""
        try:
            self.log(f"🤖 Analyse TEMPS RÉEL: {article['title'][:50]}...")

            # Lancement du pipeline complet
            result = run_berzerk_pipeline(article["link"], self.capital)

            if result and "final_decision" in result:
                # Sauvegarde de la décision
                self.save_decision_to_db(article["link"], result["final_decision"])

                # Marquer comme traité
                self.processed_articles.add(article["link"])

                # Statistiques
                self.stats["analyses_completed"] += 1

                # Affichage du résultat
                decision = result["final_decision"]
                action = decision.get("decision", "INCONNU")

                # --- DÉBUT DU TEMPLATE FINAL ---
                if action in ["LONG", "SHORT"]:
                    ticker = decision.get("ticker", "N/A")
                    prix_decision = decision.get("prix_a_la_decision", 0.0)
                    confiance = decision.get("confiance", "INCONNUE")
                    justification = decision.get("justification_synthetique", "N/A")
                    article_link = article["link"]

                    if action == "LONG":
                        signal_color = "🟢"
                        action_label = "ACHAT (LONG)"
                    else: # SHORT
                        signal_color = "🔴"
                        action_label = "VENTE (SHORT)"
                    
                    message = (
                        f"{signal_color} *NOUVEAU SIGNAL BERZERK*\n\n"
                        f"*{action_label}:* `{ticker}`\n"
                        f"-----------------------------------\n"
                        f"💰 *Prix d'Entrée:* `{prix_decision:.2f} $`\n"
                        f"💪 *Confiance:* **{confiance.upper()}**\n\n"
                        f"> {justification}\n\n"
                        f"📰 [Lire l'article source]({article_link})"
                    )
                    send_telegram_notification(message)
                # --- FIN DU TEMPLATE FINAL ---

                if action in ["LONG", "ACHETER"]:  # Compatibilité avec anciennes données
                    self.log(
                        f"🚀 SIGNAL LONG IDENTIFIÉ: {article['title'][:50]}...", "SUCCESS"
                    )
                    ticker = decision.get("ticker_cible", "N/A")
                    allocation = decision.get("allocation_pourcentage", 0)
                    self.log(f"   💰 Ticker: {ticker}, Allocation: {allocation}%")
                elif action == "SURVEILLER":
                    self.log(f"👀 SURVEILLANCE: {article['title'][:50]}...")
                else:
                    self.log(f"✅ Analyse terminée: {action}")

                return result
            else:
                self.log(f"⚠️ Échec d'analyse: {article['title'][:50]}...")
                return None

        except Exception as e:
            self.log(f"❌ Erreur analyse temps réel: {e}")
            return None

    def save_decision_to_db(self, article_link: str, decision: dict):
        """Sauvegarde la décision dans la base de données"""
        try:
            conn = sqlite3.connect("berzerk.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE articles
                SET decision_json = ?,
                    status = 'analyzed',
                    analyzed_at = ?
                WHERE link = ?
            """,
                (
                    json.dumps(decision, ensure_ascii=False),
                    datetime.now().isoformat(),
                    article_link,
                ),
            )

            # Nouvelle logique: créer un trade si décision LONG/SHORT
            try:
                decision_type = str(decision.get("decision", "")).upper()
                if decision_type in ("LONG", "SHORT"):
                    # Récupérer l'id de l'article concerné
                    cursor.execute(
                        "SELECT id FROM articles WHERE link = ?",
                        (article_link,),
                    )
                    row = cursor.fetchone()
                    if row:
                        article_id = row[0]
                        ticker = decision.get("ticker") or ""
                        entry_price = decision.get("prix_a_la_decision") or 0.0
                        entry_at = datetime.now().isoformat()

                        cursor.execute(
                            """
                            INSERT OR IGNORE INTO trades (
                                article_id, ticker, decision_type, entry_at, entry_price, status
                            ) VALUES (?, ?, ?, ?, ?, 'OPEN')
                            """,
                            (
                                article_id,
                                ticker,
                                decision_type,
                                entry_at,
                                float(entry_price) if entry_price is not None else 0.0,
                            ),
                        )

                        self.log(
                            f"✅ Trade enregistré: {decision_type} {ticker} @ {entry_price}",
                            "SUCCESS",
                        )
                    else:
                        self.log(
                            "⚠️ Impossible de créer le trade: article introuvable après UPDATE",
                            "WARNING",
                        )
            except Exception as e:
                self.log(f"⚠️ Erreur lors de la création du trade: {e}")

            conn.commit()
            conn.close()

        except Exception as e:
            self.log(f"❌ Erreur sauvegarde décision: {e}")

    def monitoring_thread(self):
        """Thread principal de surveillance"""
        self.log("🔄 Thread de surveillance démarré")

        while self.running:
            try:
                # Vérifier chaque flux RSS
                for _feed_url, feed_state in self.feeds_state.items():
                    if not self.running:
                        break

                    # Vérifier si le flux doit être contrôlé
                    if feed_state.should_check(self.poll_interval):
                        new_articles = self.check_feed_optimized(feed_state)

                        # Traiter les nouveaux articles
                        for article in new_articles:
                            if not self.running:
                                break

                            # Stockage en base
                            self.store_article(article)

                            # Analyse immédiate en arrière-plan
                            threading.Thread(
                                target=self.analyze_article_realtime,
                                args=(article,),
                                daemon=True,
                            ).start()

                # Pause courte avant le prochain cycle
                time.sleep(1)

            except Exception as e:
                self.log(f"❌ Erreur dans le thread de surveillance: {e}")
                time.sleep(5)  # Pause plus longue en cas d'erreur

        self.log("🛑 Thread de surveillance arrêté")

    def display_stats(self):
        """Affiche les statistiques en temps réel"""
        uptime = datetime.now() - self.stats["start_time"]

        print("\n" + "=" * 50)
        print("📊 STATISTIQUES TEMPS RÉEL")
        print("=" * 50)
        print(f"⏱️  Uptime: {uptime}")
        print(f"🔄 Vérifications totales: {self.stats['total_checks']}")
        print(f"📈 Nouveaux articles: {self.stats['new_articles_found']}")
        print(f"🤖 Analyses complètes: {self.stats['analyses_completed']}")
        print(f"❌ Erreurs: {self.stats['errors']}")
        print(f"💾 Articles en cache: {len(self.processed_articles)}")
        print("=" * 50)

    def start(self):
        """Démarre la surveillance temps réel"""
        self.log("🚀 DÉMARRAGE DE LA SURVEILLANCE TEMPS RÉEL", "SUCCESS")
        self.log(f"⚡ Polling: {self.poll_interval} secondes")
        self.log("⏹️  Arrêt: Ctrl+C")

        # Initialiser la base de données
        init_db()

        # Démarrer le thread de surveillance
        self.running = True
        monitor_thread = threading.Thread(target=self.monitoring_thread, daemon=True)
        monitor_thread.start()

        try:
            # Boucle principale avec affichage des stats
            while True:
                time.sleep(30)  # Afficher les stats toutes les 30 secondes
                self.display_stats()

        except KeyboardInterrupt:
            self.log("🛑 Arrêt demandé par l'utilisateur", "WARNING")
        finally:
            self.running = False
            self.log("👋 Surveillance temps réel arrêtée", "SUCCESS")
            self.display_stats()


def main():
    """Point d'entrée principal"""
    # Configuration par défaut
    poll_interval = 30  # 30 secondes par défaut
    capital = 25000.0

    # Parsing des arguments
    if len(sys.argv) > 1:
        try:
            poll_interval = int(sys.argv[1])
            if poll_interval < 10:
                raise ValueError("L'intervalle doit être d'au moins 10 secondes")
        except ValueError as e:
            print(f"❌ Erreur: {e}")
            print("💡 Usage: python real_time_rss_monitor.py [poll_interval_seconds]")
            print("📊 Exemple: python real_time_rss_monitor.py 30")
            sys.exit(1)

    print("🚀 BERZERK Real-Time RSS Monitor")
    print("⚡ Surveillance quasi-instantanée avec polling optimisé")
    print(f"🔄 Intervalle: {poll_interval} secondes")
    print("-" * 70)

    # Lancement du monitor
    monitor = RealTimeRSSMonitor(poll_interval, capital)
    monitor.start()


if __name__ == "__main__":
    main()
