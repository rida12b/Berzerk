#!/usr/bin/env python3
"""
🚀 Script de Lancement BERZERK Real-Time Monitor
===============================================

Ce script simplifie le lancement du système de surveillance RSS temps réel.
Il peut également lancer le dashboard en parallèle pour une visualisation complète.

Usage:
    python start_realtime_monitor.py                    # Surveillance seule
    python start_realtime_monitor.py --with-dashboard   # Surveillance + Dashboard
    python start_realtime_monitor.py --interval 30      # Intervalle personnalisé
"""

import subprocess
import sys
import time
import threading
import os
from datetime import datetime

def log(message: str):
    """Logger avec timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"🚀 [{timestamp}] {message}")

def launch_dashboard():
    """Lance le dashboard Streamlit en arrière-plan"""
    try:
        log("Lancement du dashboard Streamlit...")
        
        # Lancer le dashboard
        process = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", "berzerk_dashboard.py",
            "--server.headless", "true",
            "--server.port", "8501",
            "--browser.gatherUsageStats", "false"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Attendre quelques secondes pour voir si le lancement réussit
        time.sleep(3)
        
        if process.poll() is None:
            log("✅ Dashboard démarré sur http://localhost:8501")
            return process
        else:
            log("❌ Échec du démarrage du dashboard")
            return None
    
    except Exception as e:
        log(f"❌ Erreur lors du lancement du dashboard: {e}")
        return None

def launch_realtime_monitor(interval: int = 30):
    """Lance le monitor temps réel"""
    try:
        log(f"Lancement du monitor temps réel (intervalle: {interval}s)...")
        
        # Lancer le monitor
        process = subprocess.Popen([
            sys.executable, "real_time_rss_monitor.py", str(interval)
        ])
        
        return process
        
    except Exception as e:
        log(f"❌ Erreur lors du lancement du monitor: {e}")
        return None

def main():
    """Fonction principale"""
    
    # Configuration par défaut
    interval = 30
    with_dashboard = False
    
    # Parsing des arguments
    args = sys.argv[1:]
    
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg == "--with-dashboard":
            with_dashboard = True
        elif arg == "--interval":
            if i + 1 < len(args):
                try:
                    interval = int(args[i + 1])
                    i += 1  # Skip next argument
                except ValueError:
                    print("❌ Erreur: L'intervalle doit être un nombre entier")
                    sys.exit(1)
            else:
                print("❌ Erreur: --interval nécessite une valeur")
                sys.exit(1)
        elif arg == "--help" or arg == "-h":
            print(__doc__)
            sys.exit(0)
        else:
            print(f"❌ Argument inconnu: {arg}")
            print("💡 Utilisez --help pour voir les options disponibles")
            sys.exit(1)
        
        i += 1
    
    # Affichage de la configuration
    print("\n" + "="*70)
    print("🚀 BERZERK Real-Time Monitor - Lancement")
    print("="*70)
    print(f"⚡ Intervalle de surveillance: {interval} secondes")
    print(f"📊 Dashboard inclus: {'Oui' if with_dashboard else 'Non'}")
    print("="*70)
    
    # Vérification des prérequis
    if not os.path.exists("real_time_rss_monitor.py"):
        print("❌ Erreur: real_time_rss_monitor.py non trouvé")
        sys.exit(1)
    
    if with_dashboard and not os.path.exists("berzerk_dashboard.py"):
        print("❌ Erreur: berzerk_dashboard.py non trouvé")
        sys.exit(1)
    
    # Lancement des composants
    dashboard_process = None
    monitor_process = None
    
    try:
        # Lancer le dashboard si demandé
        if with_dashboard:
            dashboard_process = launch_dashboard()
            if dashboard_process:
                time.sleep(2)  # Laisser le dashboard se stabiliser
        
        # Lancer le monitor temps réel
        monitor_process = launch_realtime_monitor(interval)
        
        if monitor_process:
            log("✅ Monitor temps réel démarré")
            
            if with_dashboard:
                log("🌐 Accédez au dashboard: http://localhost:8501")
            
            log("⏹️  Appuyez sur Ctrl+C pour arrêter")
            
            # Attendre la fin du processus principal
            monitor_process.wait()
        else:
            log("❌ Échec du démarrage du monitor")
            
    except KeyboardInterrupt:
        log("🛑 Arrêt demandé par l'utilisateur")
    
    except Exception as e:
        log(f"❌ Erreur fatale: {e}")
    
    finally:
        # Nettoyage des processus
        if monitor_process and monitor_process.poll() is None:
            log("Arrêt du monitor temps réel...")
            monitor_process.terminate()
            monitor_process.wait()
        
        if dashboard_process and dashboard_process.poll() is None:
            log("Arrêt du dashboard...")
            dashboard_process.terminate()
            dashboard_process.wait()
        
        log("👋 Tous les processus arrêtés")

if __name__ == "__main__":
    main() 