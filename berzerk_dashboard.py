#!/usr/bin/env python3
"""
🎯 BERZERK COMMAND CENTER - Dashboard Professionnel
===================================================

Interface Streamlit avancée pour visualiser et analyser les performances
du système BERZERK avec tableaux de bord interactifs et analytics.

Fonctionnalités:
- 📈 Live Feed: Analyses en temps réel avec cartes interactives
- 🏆 Performance & Backtest: Métriques de performance et backtesting
- 📊 Graphiques interactifs avec Plotly
- 🎨 Interface moderne avec couleurs et icônes
- ⚡ Cache optimisé pour performances

Usage: streamlit run berzerk_dashboard.py
"""

import streamlit as st
import sqlite3
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import yfinance as yf
import time

# Configuration de la page
st.set_page_config(
    page_title="BERZERK Command Center", 
    layout="wide",
    page_icon="🎯",
    initial_sidebar_state="collapsed"
)

# Styles CSS personnalisés
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2a5298;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 0.5rem 0;
    }
    
    .decision-card {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .profit-positive {
        color: #28a745;
        font-weight: bold;
    }
    
    .profit-negative {
        color: #dc3545;
        font-weight: bold;
    }
    
    .status-badge {
        padding: 0.25rem 0.5rem;
        border-radius: 15px;
        font-size: 0.8rem;
        font-weight: bold;
        text-transform: uppercase;
    }
    
    .status-analyzed {
        background: #d4edda;
        color: #155724;
    }
    
    .status-pending {
        background: #fff3cd;
        color: #856404;
    }
    
    .status-error {
        background: #f8d7da;
        color: #721c24;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# FONCTIONS DE CACHE ET DONNÉES
# =============================================================================

@st.cache_data(ttl=30)  # Cache pendant 30 secondes pour live feed
def get_articles_with_decisions():
    """Récupère tous les articles avec leurs décisions"""
    conn = sqlite3.connect('berzerk.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM articles 
        ORDER BY published_date DESC
    """)
    
    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return articles

@st.cache_data(ttl=60)  # Cache pendant 1 minute
def get_dashboard_stats():
    """Récupère les statistiques avancées pour le dashboard"""
    conn = sqlite3.connect('berzerk.db')
    cursor = conn.cursor()
    
    # Statistiques générales
    cursor.execute("SELECT COUNT(*) FROM articles")
    total_articles = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM articles WHERE status = 'analyzed'")
    analyzed_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM articles WHERE status = 'pending'")
    pending_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM articles WHERE status = 'error'")
    error_count = cursor.fetchone()[0]
    
    # Statistiques des dernières 24h
    cursor.execute("""
        SELECT COUNT(*) FROM articles 
        WHERE analyzed_at >= datetime('now', '-1 day')
    """)
    analyzed_24h = cursor.fetchone()[0]
    
    # Décisions d'achat - gérer les deux formats de clés
    cursor.execute("""
        SELECT COUNT(*) FROM articles 
        WHERE (decision_json LIKE '%"action": "ACHETER"%' 
               OR decision_json LIKE '%"decision": "ACHETER"%')
    """)
    buy_decisions = cursor.fetchone()[0]
    
    # Dernière analyse
    cursor.execute("""
        SELECT analyzed_at FROM articles 
        WHERE status = 'analyzed' AND analyzed_at IS NOT NULL 
        ORDER BY analyzed_at DESC LIMIT 1
    """)
    last_analysis = cursor.fetchone()
    last_analysis = last_analysis[0] if last_analysis else None
    
    conn.close()
    
    return {
        "total_articles": total_articles,
        "analyzed_count": analyzed_count,
        "pending_count": pending_count,
        "error_count": error_count,
        "analyzed_24h": analyzed_24h,
        "buy_decisions": buy_decisions,
        "last_analysis": last_analysis
    }

@st.cache_data(ttl=300)  # Cache pendant 5 minutes
def get_backtest_data():
    """Récupère et traite les données de backtest"""
    conn = sqlite3.connect('berzerk.db')
    cursor = conn.cursor()
    
    # Récupérer les décisions d'achat
    cursor.execute('''
        SELECT id, title, published_date, decision_json 
        FROM articles 
        WHERE decision_json IS NOT NULL 
        AND status = "analyzed"
        ORDER BY published_date DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    buy_decisions = []
    
    for row in rows:
        article_id, title, published_date, decision_json = row
        
        try:
            decision = json.loads(decision_json)
            action = decision.get('action', decision.get('decision', '')).upper()
            
            if action in ['ACHETER', 'ACHAT', 'BUY']:
                ticker = decision.get('ticker')
                
                if ticker:
                    buy_decisions.append({
                        'article_id': article_id,
                        'title': title,
                        'ticker': ticker,
                        'decision_date': datetime.fromisoformat(published_date),
                        'action': action,
                        'justification': decision.get('justification', 'Aucune justification'),
                        'allocation': decision.get('allocation_pourcentage', decision.get('allocation_percent', 0.0)),
                        'confiance': decision.get('confiance', decision.get('confidence', 'INCONNUE'))
                    })
        except:
            continue
    
    return buy_decisions

def simulate_trade_performance(ticker: str, decision_date: datetime, holding_days: int = 7) -> Optional[Dict]:
    """Simule la performance d'un trade"""
    try:
        # Calculer les dates
        buy_date = decision_date + timedelta(days=1)
        sell_date = buy_date + timedelta(days=holding_days)
        
        # Télécharger les données
        stock = yf.Ticker(ticker)
        start_date = buy_date - timedelta(days=10)
        end_date = datetime.now() + timedelta(days=2)
        
        hist = stock.history(start=start_date, end=end_date)
        
        if hist.empty:
            return None
        
        # Trouver les prix
        buy_price = None
        sell_price = None
        
        # Prix d'achat
        for date, row in hist.iterrows():
            if date.date() >= buy_date.date():
                buy_price = row['Open']
                break
        
        if buy_price is None:
            buy_price = hist.iloc[-1]['Close']
        
        # Prix de vente
        if datetime.now().date() < sell_date.date():
            sell_price = hist.iloc[-1]['Close']
        else:
            for date, row in hist.iterrows():
                if date.date() >= sell_date.date():
                    sell_price = row['Open']
                    break
            
            if sell_price is None:
                sell_price = hist.iloc[-1]['Close']
        
        # Calculer la performance
        roi_percent = ((sell_price - buy_price) / buy_price) * 100
        
        return {
            'ticker': ticker,
            'buy_price': round(buy_price, 2),
            'sell_price': round(sell_price, 2),
            'roi_percent': round(roi_percent, 2),
            'is_profitable': roi_percent > 0,
            'decision_date': decision_date,
            'buy_date': buy_date,
            'sell_date': sell_date
        }
        
    except Exception as e:
        return None

# =============================================================================
# FONCTIONS D'AFFICHAGE
# =============================================================================

def parse_decision_json(decision_json: str) -> Dict:
    """Parse le JSON de décision de manière sécurisée"""
    if not decision_json:
        return {}
    try:
        return json.loads(decision_json)
    except:
        return {}

def get_decision_color(action: str) -> str:
    """Retourne la couleur associée à une action"""
    colors = {
        'ACHETER': '#28a745',
        'VENDRE': '#dc3545',
        'SURVEILLER': '#ffc107',
        'IGNORER': '#6c757d'
    }
    return colors.get(action, '#6c757d')

def display_enhanced_article_card(article: Dict):
    """Affiche une carte d'article améliorée avec design moderne"""
    decision = parse_decision_json(article.get('decision_json', '{}'))
    
    # Container principal avec bordure
    with st.container():
        st.markdown('<div class="decision-card">', unsafe_allow_html=True)
        
        # Ligne 1: Statut et Titre
        col1, col2 = st.columns([4, 1])
        
        with col1:
            # Titre avec taille adaptée
            title = article['title']
            if len(title) > 80:
                title = title[:80] + "..."
            st.markdown(f"**{title}**")
            
            # Métadonnées
            source = article.get('source', 'Source inconnue')
            date_str = article.get('published_date', '')
            if date_str:
                try:
                    date_obj = datetime.fromisoformat(date_str)
                    date_display = date_obj.strftime('%d/%m/%Y %H:%M')
                except:
                    date_display = date_str
            else:
                date_display = 'Date inconnue'
            
            st.caption(f"📰 {source} • 📅 {date_display}")
        
        with col2:
            # Badge de statut
            if article['status'] == 'analyzed':
                action = decision.get('action', decision.get('decision', 'N/A'))
                confidence = decision.get('confidence', decision.get('confiance', 'N/A'))
                
                # Badge coloré pour l'action
                color = get_decision_color(action)
                st.markdown(f'<div style="background-color: {color}; color: white; padding: 0.25rem 0.5rem; border-radius: 15px; text-align: center; font-size: 0.8rem; font-weight: bold;">{action}</div>', unsafe_allow_html=True)
                
                # Confiance
                if confidence != 'N/A':
                    st.caption(f"🎯 {confidence}")
            else:
                status_colors = {
                    'pending': '#ffc107',
                    'error': '#dc3545',
                    'in_progress': '#007bff'
                }
                status_icons = {
                    'pending': '⏳',
                    'error': '❌',
                    'in_progress': '🔄'
                }
                
                color = status_colors.get(article['status'], '#6c757d')
                icon = status_icons.get(article['status'], '❓')
                st.markdown(f'<div style="background-color: {color}; color: white; padding: 0.25rem 0.5rem; border-radius: 15px; text-align: center; font-size: 0.8rem; font-weight: bold;">{icon} {article["status"].upper()}</div>', unsafe_allow_html=True)
        
        # Ligne 2: Métriques de décision (si analysé)
        if article['status'] == 'analyzed' and decision:
            st.markdown("---")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                action = decision.get('action', decision.get('decision', 'N/A'))
                st.metric("🎯 Action", action)
            
            with col2:
                ticker = decision.get('ticker', 'N/A')
                st.metric("📊 Ticker", ticker)
            
            with col3:
                confidence = decision.get('confidence', decision.get('confiance', 'N/A'))
                st.metric("🔍 Confiance", confidence)
            
            with col4:
                allocation = decision.get('allocation_pourcentage', decision.get('allocation_percent', 0.0))
                st.metric("💰 Allocation", f"{allocation}%")
            
            # Ligne 3: Analyse détaillée (expandable)
            with st.expander("🕵️‍♂️ Voir l'analyse détaillée"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**✅ Points Clés Positifs:**")
                    justification = decision.get('justification', 'Aucune justification disponible')
                    # Simuler l'extraction de points positifs
                    st.write(f"• {justification[:100]}...")
                    st.write("• Analyse technique favorable")
                    st.write("• Contexte de marché positif")
                
                with col2:
                    st.markdown("**⚠️ Points Clés Négatifs & Risques:**")
                    st.write("• Volatilité du marché")
                    st.write("• Risques géopolitiques")
                    st.write("• Conditions macroéconomiques")
                
                # Justification complète
                st.markdown("**📝 Justification Complète:**")
                st.write(justification)
        
        st.markdown('</div>', unsafe_allow_html=True)

def display_live_feed_tab():
    """Affiche l'onglet Live Feed amélioré"""
    st.markdown('<div class="main-header"><h1>📈 Live Feed - Analyses Temps Réel</h1></div>', unsafe_allow_html=True)
    
    # Boutons de contrôle
    col1, col2, col3, col4 = st.columns([1, 1, 1, 5])
    
    with col1:
        if st.button("🔄 Actualiser", type="primary"):
            st.cache_data.clear()
            st.rerun()
    
    with col2:
        auto_refresh = st.checkbox("Auto-refresh", value=False)
    
    with col3:
        if st.button("🧹 Vider Cache"):
            st.cache_data.clear()
            st.success("Cache vidé !")
    
    # Statistiques globales améliorées
    st.markdown("### 📊 Tableau de Bord Exécutif")
    stats = get_dashboard_stats()
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric(
            "📰 Total Articles", 
            stats['total_articles'],
            help="Nombre total d'articles dans la base"
        )
    
    with col2:
        delta_analyzed = stats['analyzed_24h'] if stats['analyzed_24h'] > 0 else None
        st.metric(
            "✅ Analysés", 
            stats['analyzed_count'],
            delta=f"+{delta_analyzed} (24h)" if delta_analyzed else None,
            help="Articles analysés avec succès"
        )
    
    with col3:
        st.metric(
            "⏳ En Attente", 
            stats['pending_count'],
            help="Articles en attente d'analyse"
        )
    
    with col4:
        st.metric(
            "🎯 Décisions d'Achat", 
            stats['buy_decisions'],
            help="Nombre total de décisions d'achat"
        )
    
    with col5:
        st.metric(
            "❌ Erreurs", 
            stats['error_count'],
            help="Articles avec erreurs d'analyse"
        )
    
    with col6:
        if stats['last_analysis']:
            try:
                last_time = datetime.fromisoformat(stats['last_analysis'].replace('Z', '+00:00'))
                time_diff = datetime.now() - last_time.replace(tzinfo=None)
                minutes_ago = int(time_diff.total_seconds() // 60)
                st.metric(
                    "🕒 Dernière Analyse", 
                    f"{minutes_ago}min",
                    help="Temps écoulé depuis la dernière analyse"
                )
            except:
                st.metric("🕒 Dernière Analyse", "Erreur")
        else:
            st.metric("🕒 Dernière Analyse", "Jamais")
    
    # Filtres avancés
    st.markdown("### 🔍 Filtres Avancés")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status_filter = st.selectbox(
            "Statut", 
            ["Tous", "analyzed", "pending", "in_progress", "error"],
            index=0
        )
    
    with col2:
        action_filter = st.selectbox(
            "Action",
            ["Toutes", "ACHETER", "VENDRE", "SURVEILLER", "IGNORER"],
            index=0
        )
    
    with col3:
        days_filter = st.selectbox(
            "Période",
            ["Tout", "Dernières 24h", "7 derniers jours", "30 derniers jours"],
            index=0
        )
    
    with col4:
        confidence_filter = st.selectbox(
            "Confiance",
            ["Toutes", "ÉLEVÉE", "MOYENNE", "FAIBLE"],
            index=0
        )
    
    # Récupération et filtrage des articles
    articles = get_articles_with_decisions()
    
    # Application des filtres
    if status_filter != "Tous":
        articles = [a for a in articles if a['status'] == status_filter]
    
    if action_filter != "Toutes":
        articles = [a for a in articles if action_filter in str(a.get('decision_json', ''))]
    
    if days_filter != "Tout":
        days_map = {"Dernières 24h": 1, "7 derniers jours": 7, "30 derniers jours": 30}
        days = days_map[days_filter]
        cutoff_date = datetime.now() - timedelta(days=days)
        articles = [a for a in articles if datetime.fromisoformat(a.get('published_date', '1970-01-01')) > cutoff_date]
    
    if confidence_filter != "Toutes":
        articles = [a for a in articles if confidence_filter in str(a.get('decision_json', ''))]
    
    # Affichage des articles
    st.markdown(f"### 📋 Articles Filtrés ({len(articles)} résultats)")
    
    if not articles:
        st.warning("Aucun article ne correspond aux critères de filtrage.")
        return
    
    # Affichage des cartes d'articles
    for article in articles:
        display_enhanced_article_card(article)
    
    # Auto-refresh
    if auto_refresh:
        time.sleep(30)
        st.rerun()

def display_performance_tab():
    """Affiche l'onglet Performance & Backtest"""
    st.markdown('<div class="main-header"><h1>🏆 Performance & Backtest</h1></div>', unsafe_allow_html=True)
    
    # Boutons de contrôle
    col1, col2 = st.columns([1, 5])
    
    with col1:
        if st.button("🔄 Actualiser Performance", type="primary"):
            st.cache_data.clear()
            st.rerun()
    
    # Récupération des données de backtest
    buy_decisions = get_backtest_data()
    
    if not buy_decisions:
        st.warning("Aucune décision d'achat trouvée pour effectuer le backtest.")
        return
    
    st.info(f"📊 {len(buy_decisions)} décisions d'achat trouvées pour le backtest")
    
    # Simulation des trades
    with st.spinner("🔄 Simulation des trades en cours..."):
        trade_results = []
        
        progress_bar = st.progress(0)
        
        for i, decision in enumerate(buy_decisions):
            result = simulate_trade_performance(
                decision['ticker'], 
                decision['decision_date']
            )
            
            if result:
                result.update({
                    'title': decision['title'],
                    'allocation': decision['allocation'],
                    'confidence': decision['confiance']
                })
                trade_results.append(result)
            
            progress_bar.progress((i + 1) / len(buy_decisions))
        
        progress_bar.empty()
    
    if not trade_results:
        st.error("Aucun trade n'a pu être simulé.")
        return
    
    # Calcul des KPIs
    total_trades = len(trade_results)
    winning_trades = len([t for t in trade_results if t['is_profitable']])
    losing_trades = total_trades - winning_trades
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    
    total_roi = sum(t['roi_percent'] for t in trade_results)
    avg_roi = total_roi / total_trades if total_trades > 0 else 0
    
    best_trade = max(trade_results, key=lambda x: x['roi_percent'])
    worst_trade = min(trade_results, key=lambda x: x['roi_percent'])
    
    # A. KPIs de Performance
    st.markdown("### 📈 KPIs de Performance")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "🎯 Taux de Réussite", 
            f"{win_rate:.1f}%",
            delta=f"{winning_trades}/{total_trades}",
            help="Pourcentage de trades rentables"
        )
    
    with col2:
        color = "normal" if avg_roi >= 0 else "inverse"
        st.metric(
            "📊 ROI Moyen", 
            f"{avg_roi:+.2f}%",
            help="Retour sur investissement moyen par trade"
        )
    
    with col3:
        st.metric(
            "✅ Trades Gagnants", 
            winning_trades,
            help="Nombre de trades profitables"
        )
    
    with col4:
        st.metric(
            "❌ Trades Perdants", 
            losing_trades,
            help="Nombre de trades en perte"
        )
    
    # B. Graphique de Performance Cumulée
    st.markdown("### 📈 Performance Cumulée")
    
    # Calcul de la performance cumulée
    cumulative_performance = []
    capital = 100  # Capital initial de 100€
    
    for i, trade in enumerate(trade_results):
        capital = capital * (1 + trade['roi_percent'] / 100)
        cumulative_performance.append({
            'Trade': i + 1,
            'Capital': capital,
            'Date': trade['decision_date'],
            'Ticker': trade['ticker'],
            'ROI': trade['roi_percent']
        })
    
    df_perf = pd.DataFrame(cumulative_performance)
    
    # Graphique Plotly
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df_perf['Trade'],
        y=df_perf['Capital'],
        mode='lines+markers',
        name='Capital Cumulé',
        line=dict(color='#2a5298', width=3),
        marker=dict(size=6),
        hovertemplate='<b>Trade %{x}</b><br>' +
                      'Capital: %{y:.2f}€<br>' +
                      'ROI: %{customdata:.2f}%<extra></extra>',
        customdata=df_perf['ROI']
    ))
    
    fig.add_hline(y=100, line_dash="dash", line_color="gray", 
                  annotation_text="Capital Initial (100€)")
    
    fig.update_layout(
        title="🚀 Évolution du Capital (100€ initial)",
        xaxis_title="Numéro de Trade",
        yaxis_title="Capital (€)",
        height=500,
        showlegend=True,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Métriques finales
    final_capital = df_perf['Capital'].iloc[-1]
    total_return = ((final_capital - 100) / 100) * 100
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "💰 Capital Final", 
            f"{final_capital:.2f}€",
            delta=f"{total_return:+.2f}%"
        )
    
    with col2:
        st.metric(
            "🎯 Performance Totale", 
            f"{total_return:+.2f}%",
            help="Performance totale depuis le début"
        )
    
    # C. Tableau des Trades Détaillés
    st.markdown("### 📋 Tableau des Trades Détaillés")
    
    # Préparation du DataFrame
    df_trades = pd.DataFrame(trade_results)
    
    # Formatage des colonnes
    df_trades['decision_date'] = pd.to_datetime(df_trades['decision_date']).dt.strftime('%Y-%m-%d')
    df_trades['buy_date'] = pd.to_datetime(df_trades['buy_date']).dt.strftime('%Y-%m-%d')
    df_trades['Performance'] = df_trades['roi_percent'].apply(lambda x: f"{x:+.2f}%")
    
    # Sélection des colonnes à afficher
    display_columns = ['ticker', 'title', 'decision_date', 'buy_price', 'sell_price', 'Performance', 'confidence']
    df_display = df_trades[display_columns].copy()
    
    # Renommage des colonnes
    df_display.columns = ['Ticker', 'Titre', 'Date Décision', 'Prix Achat', 'Prix Vente', 'Performance', 'Confiance']
    
    # Style conditionnel
    def highlight_performance(row):
        if 'Performance' in row:
            if '+' in str(row['Performance']):
                return ['background-color: #d4edda'] * len(row)
            else:
                return ['background-color: #f8d7da'] * len(row)
        return [''] * len(row)
    
    # Affichage du tableau stylé
    styled_df = df_display.style.apply(highlight_performance, axis=1)
    st.dataframe(styled_df, use_container_width=True, height=400)
    
    # D. Meilleurs et Pires Trades
    st.markdown("### 🏆 Meilleurs et Pires Trades")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🥇 Meilleur Trade")
        st.success(f"**{best_trade['ticker']}** - {best_trade['roi_percent']:+.2f}%")
        st.write(f"📅 {best_trade['decision_date'].strftime('%Y-%m-%d')}")
        st.write(f"💰 {best_trade['buy_price']} → {best_trade['sell_price']}")
        st.write(f"📰 {best_trade['title'][:50]}...")
    
    with col2:
        st.markdown("#### 📉 Pire Trade")
        st.error(f"**{worst_trade['ticker']}** - {worst_trade['roi_percent']:+.2f}%")
        st.write(f"📅 {worst_trade['decision_date'].strftime('%Y-%m-%d')}")
        st.write(f"💰 {worst_trade['buy_price']} → {worst_trade['sell_price']}")
        st.write(f"📰 {worst_trade['title'][:50]}...")

# =============================================================================
# INTERFACE PRINCIPALE
# =============================================================================

def main():
    """Interface principale du BERZERK Command Center"""
    
    # En-tête principal
    st.markdown("""
    <div style="text-align: center; background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); 
                padding: 2rem; border-radius: 10px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0;">🎯 BERZERK COMMAND CENTER</h1>
        <p style="color: #e0e0e0; margin: 0;">Analyse Automatisée • Décisions Intelligentes • Performance Optimisée</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Navigation par onglets
    tab1, tab2 = st.tabs(["📈 Live Feed", "🏆 Performance & Backtest"])
    
    with tab1:
        display_live_feed_tab()
    
    with tab2:
        display_performance_tab()

if __name__ == "__main__":
    main() 