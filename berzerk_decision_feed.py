#!/usr/bin/env python3
"""
⚡ BERZERK - Decision Feed
========================

Interface épurée "Clarté Radicale" pour le suivi des décisions d'investissement IA.
Philosophie : Priorité à l'action, simplicité, hiérarchie claire.

Auteur: BERZERK Team
Phase: 8 - Interface Decision Feed
"""

import streamlit as st
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import yfinance as yf

# Configuration de la page
st.set_page_config(
    page_title="BERZERK Decision Feed",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def get_current_price(ticker: str) -> float:
    """Récupère le prix actuel d'une action via yfinance."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
        return 0.0
    except:
        return 0.0

def load_decisions_from_db() -> List[Dict[str, Any]]:
    """Charge les décisions depuis la base de données BERZERK."""
    try:
        conn = sqlite3.connect('berzerk.db')
        cursor = conn.cursor()
        
        # Récupérer les articles avec décisions des dernières 24h
        cursor.execute('''
            SELECT 
                title, link, published_date, decision_json, analyzed_at
            FROM articles 
            WHERE decision_json IS NOT NULL 
                AND analyzed_at >= datetime('now', '-7 days')
            ORDER BY analyzed_at DESC
            LIMIT 20
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        decisions = []
        for title, link, published_date, decision_json, analyzed_at in rows:
            try:
                decision_data = json.loads(decision_json)
                
                # Extraire le ticker si disponible
                ticker_value = decision_data.get('ticker')
                
                # CORRECTION : Vérifier si le ticker est None ou pas une chaîne de caractères
                if not isinstance(ticker_value, str):
                    continue  # On ignore cette décision si le ticker est invalide
                
                ticker = ticker_value.strip()
                
                if not ticker or ticker.lower() in ['n/a', 'null', 'none']:
                    continue
                
                # Construire l'objet decision
                decision = {
                    "action": decision_data.get('decision', 'IGNORER'),
                    "ticker": ticker,
                    "nom_entreprise": f"Entreprise {ticker}",  # À améliorer si disponible
                    "news_title": title,
                    "source": "Bloomberg",
                    "analyzed_at": analyzed_at,
                    "prix_decision": 0.0,  # À calculer/stocker si nécessaire
                    "prix_actuel": get_current_price(ticker),
                    "justification": decision_data.get('justification_synthetique', 'Analyse automatique BERZERK'),
                    "points_positifs": decision_data.get('points_cles_positifs', ['Analyse favorable']),
                    "points_negatifs": decision_data.get('points_cles_negatifs_risques', ['Risques standards']),
                    "allocation_pct": decision_data.get('allocation_capital_pourcentage', 0.0),
                    "article_link": link
                }
                
                decisions.append(decision)
                
            except json.JSONDecodeError:
                continue
                
        return decisions
        
    except Exception as e:
        st.error(f"Erreur lors du chargement des données : {e}")
        return []

def get_sample_decisions() -> List[Dict[str, Any]]:
    """Génère des décisions d'exemple pour la démonstration."""
    return [
        {
            "action": "ACHETER",
            "ticker": "AAPL",
            "nom_entreprise": "Apple Inc.",
            "news_title": "Apple annonce des avancées majeures dans l'IA pour l'iPhone 17.",
            "source": "Bloomberg",
            "analyzed_at": "2024-12-07T14:32:00",
            "prix_decision": 195.50,
            "prix_actuel": get_current_price("AAPL"),
            "justification": "L'annonce d'une nouvelle puce IA devrait booster les ventes et donner un avantage concurrentiel significatif à Apple sur le marché des smartphones.",
            "points_positifs": ["Avantage concurrentiel IA", "Cycle de remplacement accéléré", "Marges élevées"],
            "points_negatifs": ["Risques d'exécution", "Valorisation déjà élevée", "Concurrence intense"],
            "allocation_pct": 2.5,
            "article_link": "https://example.com/apple-ai-news"
        },
        {
            "action": "VENDRE",
            "ticker": "XOM",
            "nom_entreprise": "ExxonMobil Corporation",
            "news_title": "OPEC+ augmente la production, craintes de surabondance pétrolière",
            "source": "Bloomberg",
            "analyzed_at": "2024-12-07T12:15:00",
            "prix_decision": 118.75,
            "prix_actuel": get_current_price("XOM"),
            "justification": "La surabondance de l'offre pétrolière et les craintes sur la demande exercent une pression baissière directe sur la rentabilité future de XOM.",
            "points_positifs": ["Dividende stable", "Gestion financière solide"],
            "points_negatifs": ["Pression sur les prix du pétrole", "Surabondance de l'offre", "Demande incertaine"],
            "allocation_pct": 0.0,
            "article_link": "https://example.com/opec-oil-news"
        },
        {
            "action": "SURVEILLER",
            "ticker": "NVDA",
            "nom_entreprise": "NVIDIA Corporation",
            "news_title": "NVIDIA présente ses nouveaux processeurs IA de nouvelle génération",
            "source": "Bloomberg",
            "analyzed_at": "2024-12-07T10:45:00",
            "prix_decision": 485.20,
            "prix_actuel": get_current_price("NVDA"),
            "justification": "Innovation prometteuse mais valorisation déjà élevée. Attendre une correction pour une meilleure opportunité d'entrée.",
            "points_positifs": ["Leadership IA", "Innovation continue", "Demande croissante"],
            "points_negatifs": ["Valorisation excessive", "Volatilité élevée", "Dépendance cyclique"],
            "allocation_pct": 1.0,
            "article_link": "https://example.com/nvidia-ai-news"
        }
    ]

def display_decision_card(decision: Dict[str, Any]):
    """Affiche une carte de décision selon les spécifications."""
    
    # Container principal avec bordure
    with st.container(border=True):
        # Layout principal : Badge + Infos
        col1, col2 = st.columns([1, 8])
        
        # === COL1 : BADGE D'ACTION ===
        with col1:
            action = decision['action']
            
            # Couleurs selon l'action
            color_map = {
                "ACHETER": "#28a745",
                "VENDRE": "#dc3545", 
                "SURVEILLER": "#ffc107",
                "IGNORER": "#6c757d"
            }
            
            color = color_map.get(action, "#6c757d")
            
            # Badge coloré avec CSS
            st.markdown(f"""
                <div style="
                    background-color: {color};
                    color: white;
                    padding: 20px 10px;
                    text-align: center;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 16px;
                    margin-bottom: 10px;
                ">
                    {action}
                </div>
            """, unsafe_allow_html=True)
        
        # === COL2 : INFOS PRINCIPALES ===
        with col2:
            # Titre
            st.subheader(f"{decision['ticker']} - {decision['nom_entreprise']}")
            
            # News
            st.write(decision['news_title'])
            
            # Méta-données
            try:
                analyzed_dt = datetime.fromisoformat(decision['analyzed_at'].replace('Z', '+00:00'))
                formatted_date = analyzed_dt.strftime('%d/%m/%Y à %H:%M')
            except:
                formatted_date = decision['analyzed_at']
            
            st.caption(f"Source: {decision['source']} • Analysé le {formatted_date}")
        
        # === SECTION PERFORMANCE ===
        st.markdown("---")
        
        # Calcul de la performance
        prix_decision = decision['prix_decision']
        prix_actuel = decision['prix_actuel']
        
        if prix_decision > 0 and prix_actuel > 0:
            perf_pct = ((prix_actuel - prix_decision) / prix_decision) * 100
            
            # Déterminer couleur et emoji
            if perf_pct > 0:
                perf_color = "normal"
                emoji = "📈"
            else:
                perf_color = "inverse" 
                emoji = "📉"
        else:
            perf_pct = 0.0
            perf_color = "off"
            emoji = "📊"
        
        # Métriques de performance
        perf_col1, perf_col2, perf_col3 = st.columns(3)
        
        with perf_col1:
            if prix_decision > 0:
                st.metric("Prix Décision", f"${prix_decision:.2f}")
            else:
                st.metric("Prix Décision", "N/A")
        
        with perf_col2:
            if prix_actuel > 0:
                st.metric("Prix Actuel", f"${prix_actuel:.2f}")
            else:
                st.metric("Prix Actuel", "N/A")
        
        with perf_col3:
            if prix_decision > 0 and prix_actuel > 0:
                st.metric("Performance", f"{emoji} {perf_pct:+.2f}%", delta_color=perf_color)
            else:
                st.metric("Performance", f"{emoji} N/A")
        
        # === EXPANDER DÉTAILS ===
        with st.expander("▼ Voir le raisonnement de l'IA et les détails"):
            # Justification
            st.markdown("#### Justification de l'IA")
            st.write(decision['justification'])
            
            st.markdown("---")
            
            # Points positifs et négatifs
            col_pos, col_neg = st.columns(2)
            
            with col_pos:
                st.markdown("✅ **Points Clés Positifs**")
                for point in decision['points_positifs']:
                    st.write(f"• {point}")
            
            with col_neg:
                st.markdown("⚠️ **Risques & Points Négatifs**")
                for point in decision['points_negatifs']:
                    st.write(f"• {point}")
            
            # Allocation et lien
            st.info(f"💡 Allocation Suggérée: {decision['allocation_pct']}%")
            st.link_button("Consulter l'article original ↗", decision['article_link'])

def main():
    """Fonction principale de l'interface Decision Feed."""
    
    # === EN-TÊTE ===
    st.title("⚡ BERZERK - Decision Feed")
    st.caption("Analyse IA. Décisions Immédiates.")
    
    # === BARRE DE STATUT ===
    stat_col1, stat_col2, stat_col3 = st.columns(3)
    
    # Charger les décisions
    decisions = load_decisions_from_db()
    
    # Si pas de données réelles, utiliser les exemples
    if not decisions:
        st.warning("🔄 Aucune décision récente dans la base. Affichage des exemples.")
        decisions = get_sample_decisions()
    
    # Calculs pour les statistiques
    decisions_24h = len([d for d in decisions if d['analyzed_at']])
    achats_24h = len([d for d in decisions if d['action'] == 'ACHETER'])
    
    with stat_col1:
        st.metric("Statut Système", "🟢 Opérationnel")
    
    with stat_col2:
        st.metric("Décisions 24h", decisions_24h)
    
    with stat_col3:
        st.metric("Signaux ACHAT 24h", achats_24h)
    
    st.markdown("---")
    
    # === FLUX PRINCIPAL ===
    if decisions:
        st.markdown("### 📈 Flux de Décisions")
        
        for decision in decisions:
            display_decision_card(decision)
            st.markdown("")  # Espace entre les cartes
    else:
        st.info("📊 Aucune décision à afficher pour le moment.")
        st.markdown("Lancez le monitoring pour commencer à générer des décisions : `python real_time_rss_monitor.py`")

if __name__ == "__main__":
    main() 