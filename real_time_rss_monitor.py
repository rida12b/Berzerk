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

import asyncio
import threading
import time
import requests
import feedparser
import hashlib
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import sys
import traceback

# Import des modules BERZERK
from berzerk_lab import RSS_FEEDS, init_db, get_article_text, analyze_news_with_llm
from orchestrator import run_berzerk_pipeline


@dataclass
class FeedState:
    """État d'un flux RSS avec optimisations HTTP"""
    url: str
    last_modified: Optional[str] = None
    etag: Optional[str] = None
    last_check: Optional[datetime] = None
    last_content_hash: Optional[str] = None
    consecutive_errors: int = 0
    # articles_cache supprimé - causait des doublons après redémarrage
    
    def should_check(self, min_interval: int) -> bool:
        """Détermine si le flux doit être vérifié maintenant"""
        if self.last_check is None:
            return True
        
        # Algorithme adaptatif : plus d'erreurs = moins de vérifications
        if self.consecutive_errors > 0:
            penalty = min(self.consecutive_errors * 30, 300)  # Max 5 minutes de penalty
            return (datetime.now() - self.last_check).total_seconds() > (min_interval + penalty)
        
        return (datetime.now() - self.last_check).total_seconds() >= min_interval


class RealTimeRSSMonitor:
    """Surveillant RSS temps réel avec optimisations avancées"""
    
    def __init__(self, poll_interval: int = 30, capital: float = 25000.0):
        self.poll_interval = poll_interval  # En secondes
        self.capital = capital
        self.feeds_state: Dict[str, FeedState] = {}
        self.running = False
        self.processed_articles: Set[str] = set()
        self.stats = {
            'total_checks': 0,
            'new_articles_found': 0,
            'analyses_completed': 0,
            'errors': 0,
            'start_time': datetime.now()
        }
        
        # Configuration des requêtes HTTP optimisées
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'BERZERK-RSS-Monitor/1.0 (Real-Time News Analysis)',
            'Accept': 'application/rss+xml, application/xml, text/xml',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # Initialisation
        self.init_feeds_state()
        self.load_processed_articles()
        
        print(f"🚀 BERZERK Real-Time RSS Monitor initialisé")
        print(f"   ⚡ Polling: {poll_interval} secondes (haute fréquence)")
        print(f"   📈 Flux RSS: {len(RSS_FEEDS)} source (Bloomberg uniquement)")
        for feed_name, feed_url in RSS_FEEDS.items():
            print(f"   📡 {feed_name}: {feed_url}")
        print(f"   💰 Capital: {capital:,.2f}€")
        print(f"   🔄 Optimisations: ETags, Last-Modified, Threading")
        print(f"   📊 Articles déjà traités: {len(self.processed_articles)}")
        print("-" * 70)
    
    def init_feeds_state(self):
        """Initialise l'état de chaque flux RSS"""
        for feed_name, feed_url in RSS_FEEDS.items():
            self.feeds_state[feed_url] = FeedState(url=feed_url)
    
    def load_processed_articles(self):
        """Charge les articles déjà traités depuis la base de données"""
        try:
            conn = sqlite3.connect('berzerk.db')
            cursor = conn.cursor()
            # Charger TOUS les articles existants (peu importe le statut)
            cursor.execute("SELECT link FROM articles")
            self.processed_articles = {row[0] for row in cursor.fetchall()}
            conn.close()
            
            self.log(f"📥 {len(self.processed_articles)} articles existants chargés")
            self.log("🎯 Seuls les vrais nouveaux articles RSS seront traités")
        except Exception as e:
            self.log(f"⚠️ Erreur lors du chargement des articles traités: {e}")
            self.processed_articles = set()
    
    def log(self, message: str, level: str = "INFO"):
        """Logger avec timestamp et niveau"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        level_emoji = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DETECTION": "🔍"
        }.get(level, "📝")
        print(f"⚡ [{timestamp}] {level_emoji} {message}")
    
    def calculate_content_hash(self, content: str) -> str:
        """Calcule un hash du contenu pour détecter les changements"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def check_feed_optimized(self, feed_state: FeedState) -> List[Dict]:
        """Vérifie un flux RSS avec optimisations HTTP"""
        try:
            headers = {}
            
            # Optimisations HTTP conditionnelles
            if feed_state.etag:
                headers['If-None-Match'] = feed_state.etag
            if feed_state.last_modified:
                headers['If-Modified-Since'] = feed_state.last_modified
            
            # Requête HTTP avec timeout court
            response = self.session.get(
                feed_state.url, 
                headers=headers, 
                timeout=10
            )
            
            feed_state.last_check = datetime.now()
            self.stats['total_checks'] += 1
            
            # Gestion des codes de statut HTTP
            if response.status_code == 304:
                # Not Modified - aucun changement
                self.log(f"🔄 Pas de changement: {feed_state.url[:50]}...")
                feed_state.consecutive_errors = 0
                return []
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")
            
            # Mise à jour des métadonnées de cache
            feed_state.etag = response.headers.get('ETag')
            feed_state.last_modified = response.headers.get('Last-Modified')
            
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
                article_link = entry.get('link', '')
                
                # ✅ CORRECTION : Ne vérifier que processed_articles (pas articles_cache)
                if article_link and article_link not in self.processed_articles:
                    
                    # Marquer immédiatement comme traité pour éviter les doublons
                    self.processed_articles.add(article_link)
                    
                    # Extraction des métadonnées
                    published_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'published'):
                        try:
                            published_date = parsedate_to_datetime(entry.published)
                        except:
                            published_date = datetime.now()
                    else:
                        published_date = datetime.now()
                    
                    article = {
                        'title': entry.get('title', 'Titre non disponible'),
                        'link': article_link,
                        'published_date': published_date,
                        'summary': entry.get('summary', ''),
                        'source': feed_state.url,
                        'discovered_at': datetime.now()
                    }
                    
                    new_articles.append(article)
            
            # Succès - reset des erreurs
            feed_state.consecutive_errors = 0
            
            if new_articles:
                self.log(f"🎯 {len(new_articles)} VRAIS nouveaux articles détectés sur {feed_state.url[:50]}...", "DETECTION")
                self.stats['new_articles_found'] += len(new_articles)
            
            return new_articles
            
        except Exception as e:
            feed_state.consecutive_errors += 1
            self.stats['errors'] += 1
            self.log(f"❌ Erreur sur {feed_state.url[:50]}: {e}")
            return []
    
    def store_article(self, article: Dict):
        """Stocke un article dans la base de données"""
        try:
            conn = sqlite3.connect('berzerk.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR IGNORE INTO articles 
                (title, link, published_date, source, status, published_str)
                VALUES (?, ?, ?, ?, 'pending', ?)
            """, (
                article['title'],
                article['link'],
                article['published_date'].isoformat(),
                article['source'],
                article.get('summary', 'RSS Feed')  # Utilise summary comme published_str
            ))
            
            conn.commit()
            conn.close()
            
            if cursor.rowcount > 0:
                self.log(f"💾 Article stocké: {article['title'][:50]}...")
            
        except Exception as e:
            self.log(f"❌ Erreur stockage: {e}")
    
    def analyze_article_realtime(self, article: Dict) -> Optional[Dict]:
        """Analyse un article en temps réel avec le pipeline BERZERK"""
        try:
            self.log(f"🤖 Analyse TEMPS RÉEL: {article['title'][:50]}...")
            
            # Lancement du pipeline complet
            result = run_berzerk_pipeline(article['link'], self.capital)
            
            if result and 'final_decision' in result:
                # Sauvegarde de la décision
                self.save_decision_to_db(article['link'], result['final_decision'])
                
                # Marquer comme traité
                self.processed_articles.add(article['link'])
                
                # Statistiques
                self.stats['analyses_completed'] += 1
                
                # Affichage du résultat
                decision = result['final_decision']
                action = decision.get('decision', 'INCONNU')
                
                if action == 'ACHETER':
                    self.log(f"🚀 ACHAT IDENTIFIÉ: {article['title'][:50]}...", "SUCCESS")
                    ticker = decision.get('ticker_cible', 'N/A')
                    allocation = decision.get('allocation_pourcentage', 0)
                    self.log(f"   💰 Ticker: {ticker}, Allocation: {allocation}%")
                elif action == 'SURVEILLER':
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
    
    def save_decision_to_db(self, article_link: str, decision: Dict):
        """Sauvegarde la décision dans la base de données"""
        try:
            conn = sqlite3.connect('berzerk.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE articles 
                SET decision_json = ?, 
                    status = 'analyzed', 
                    analyzed_at = ?
                WHERE link = ?
            """, (
                json.dumps(decision, ensure_ascii=False),
                datetime.now().isoformat(),
                article_link
            ))
            
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
                for feed_url, feed_state in self.feeds_state.items():
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
                                daemon=True
                            ).start()
                
                # Pause courte avant le prochain cycle
                time.sleep(1)
                
            except Exception as e:
                self.log(f"❌ Erreur dans le thread de surveillance: {e}")
                time.sleep(5)  # Pause plus longue en cas d'erreur
        
        self.log("🛑 Thread de surveillance arrêté")
    
    def display_stats(self):
        """Affiche les statistiques en temps réel"""
        uptime = datetime.now() - self.stats['start_time']
        
        print("\n" + "="*50)
        print("📊 STATISTIQUES TEMPS RÉEL")
        print("="*50)
        print(f"⏱️  Uptime: {uptime}")
        print(f"🔄 Vérifications totales: {self.stats['total_checks']}")
        print(f"📈 Nouveaux articles: {self.stats['new_articles_found']}")
        print(f"🤖 Analyses complètes: {self.stats['analyses_completed']}")
        print(f"❌ Erreurs: {self.stats['errors']}")
        print(f"💾 Articles en cache: {len(self.processed_articles)}")
        print("="*50)
    
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
    
    print(f"🚀 BERZERK Real-Time RSS Monitor")
    print(f"⚡ Surveillance quasi-instantanée avec polling optimisé")
    print(f"🔄 Intervalle: {poll_interval} secondes")
    print("-" * 70)
    
    # Lancement du monitor
    monitor = RealTimeRSSMonitor(poll_interval, capital)
    monitor.start()


if __name__ == "__main__":
    main() 