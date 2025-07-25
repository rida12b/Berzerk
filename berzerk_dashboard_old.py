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

import json
import sqlite3
import time
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# Configuration de la page simplifiée
st.set_page_config(
    page_title="BERZERK - Centre de Contrôle",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# En-tête principal SIMPLE et CLAIR
st.markdown(
    """
<div class="main-header">
    <h1 style="color: white; font-size: 2.5rem; margin: 0; font-weight: 700;">
        ⚡ BERZERK Command Center
    </h1>
    <p style="color: rgba(255,255,255,0.9); font-size: 1.2rem; margin: 0.5rem 0 0 0;">
        Intelligence Artificielle • Analyse d'Actualités Financières • Décisions d'Investissement
    </p>
</div>
""",
    unsafe_allow_html=True,
)

# Styles CSS ULTRA SIMPLES - Fond blanc, texte lisible
st.markdown(
    """
<style>
    /* Fond général blanc */
    .main {
        background-color: #ffffff !important;
        color: #333333 !important;
    }

    /* Supprimer le fond sombre de Streamlit */
    .stApp {
        background-color: #ffffff !important;
    }

    /* En-tête avec couleurs douces */
    .main-header {
        background: linear-gradient(135deg, #4285f4, #34a853);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        color: white !important;
    }

    /* Cartes avec bordures colorées et fond blanc */
    .metric-card {
        background: #ffffff !important;
        border: 2px solid #e8f0fe;
        border-left: 5px solid #4285f4;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        color: #333333 !important;
    }

    .metric-card h3 {
        color: #1a73e8 !important;
        font-size: 1.1rem !important;
        margin-bottom: 0.5rem !important;
    }

    /* Cartes d'articles avec fond blanc */
    .article-card {
        background: #ffffff !important;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        color: #333333 !important;
    }

    /* Titre d'article en noir */
    .article-title {
        color: #202124 !important;
        font-size: 1.2rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.8rem !important;
        line-height: 1.4 !important;
    }

    /* Méta infos en gris */
    .article-meta {
        color: #5f6368 !important;
        font-size: 0.9rem !important;
        margin-bottom: 1rem !important;
    }

    /* Badges d'action plus simples */
    .badge-acheter {
        background: #34a853 !important;
        color: white !important;
        padding: 0.7rem 1.5rem !important;
        border-radius: 6px !important;
        font-weight: bold !important;
        font-size: 1rem !important;
        display: inline-block !important;
        margin-bottom: 1rem !important;
    }

    .badge-surveiller {
        background: #fbbc04 !important;
        color: #333333 !important;
        padding: 0.7rem 1.5rem !important;
        border-radius: 6px !important;
        font-weight: bold !important;
        font-size: 1rem !important;
        display: inline-block !important;
        margin-bottom: 1rem !important;
    }

    .badge-vendre {
        background: #ea4335 !important;
        color: white !important;
        padding: 0.7rem 1.5rem !important;
        border-radius: 6px !important;
        font-weight: bold !important;
        font-size: 1rem !important;
        display: inline-block !important;
        margin-bottom: 1rem !important;
    }

    .badge-ignorer {
        background: #9aa0a6 !important;
        color: white !important;
        padding: 0.7rem 1.5rem !important;
        border-radius: 6px !important;
        font-weight: bold !important;
        font-size: 1rem !important;
        display: inline-block !important;
        margin-bottom: 1rem !important;
    }

    /* Métriques en ligne plus visibles */
    .inline-metric {
        background: #f8f9fa !important;
        border: 1px solid #e0e0e0 !important;
        padding: 0.8rem !important;
        border-radius: 6px !important;
        margin: 0.3rem !important;
        color: #333333 !important;
        font-size: 0.9rem !important;
    }

    .inline-metric strong {
        color: #1a73e8 !important;
    }

    /* Section headers plus clairs */
    .section-header {
        background: #f8f9fa !important;
        border: 1px solid #e0e0e0 !important;
        border-left: 4px solid #4285f4 !important;
        padding: 1rem 1.5rem !important;
        border-radius: 6px !important;
        margin: 1.5rem 0 1rem 0 !important;
        color: #333333 !important;
    }

    .section-header h3 {
        color: #1a73e8 !important;
        margin: 0 !important;
    }

    /* Améliorer les selectbox */
    .stSelectbox > div > div {
        background-color: #ffffff !important;
        border: 2px solid #dadce0 !important;
        border-radius: 6px !important;
        color: #333333 !important;
    }

    /* Forcer le texte en noir partout */
    .stMarkdown, .stText, p, span, div {
        color: #333333 !important;
    }

    /* Onglets plus visibles */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #f8f9fa !important;
        border-radius: 6px !important;
        padding: 0.5rem !important;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: transparent !important;
        color: #5f6368 !important;
        font-weight: 500 !important;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #ffffff !important;
        color: #1a73e8 !important;
        font-weight: 600 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# =============================================================================
# FONCTIONS DE CACHE ET DONNÉES
# =============================================================================


@st.cache_data(ttl=30)  # Cache pendant 30 secondes pour live feed
def get_articles_with_decisions():
    """Récupère tous les articles avec leurs décisions"""
    conn = sqlite3.connect("berzerk.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM articles
        ORDER BY published_date DESC
    """
    )

    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return articles


@st.cache_data(ttl=30)
def get_dashboard_stats():
    """Récupère les statistiques pour le tableau de bord - VERSION SIMPLIFIÉE"""
    try:
        conn = sqlite3.connect("berzerk.db")
        cursor = conn.cursor()

        # Métriques principales
        cursor.execute("SELECT COUNT(*) FROM articles")
        total_articles = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM articles WHERE status = 'analyzed'")
        analyzed_articles = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM articles WHERE status = 'pending'")
        pending_articles = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM articles WHERE status = 'error'")
        error_count = cursor.fetchone()[0]

        # Décisions d'achat (recherche dans decision_json)
        cursor.execute(
            """
            SELECT COUNT(*) FROM articles
            WHERE status = 'analyzed'
            AND (decision_json LIKE '%"action": "ACHETER"%' OR decision_json LIKE '%"decision": "ACHETER"%')
        """
        )
        buy_decisions = cursor.fetchone()[0]

        # Dernière analyse
        cursor.execute(
            """
            SELECT analyzed_at FROM articles
            WHERE status = 'analyzed' AND analyzed_at IS NOT NULL
            ORDER BY analyzed_at DESC LIMIT 1
        """
        )
        last_analysis = cursor.fetchone()

        # Calculer les minutes depuis la dernière analyse
        last_analysis_minutes = 999
        if last_analysis and last_analysis[0]:
            try:
                last_time = datetime.fromisoformat(last_analysis[0])
                time_diff = datetime.now() - last_time
                last_analysis_minutes = int(time_diff.total_seconds() // 60)
            except Exception:
                last_analysis_minutes = 999

        conn.close()

        return {
            "total_articles": total_articles,
            "analyzed_articles": analyzed_articles,
            "pending_articles": pending_articles,
            "error_count": error_count,
            "buy_decisions": buy_decisions,
            "last_analysis_minutes": last_analysis_minutes,
        }

    except Exception as e:
        st.error(f"Erreur lors de la récupération des statistiques: {e}")
        return {
            "total_articles": 0,
            "analyzed_articles": 0,
            "pending_articles": 0,
            "error_count": 0,
            "buy_decisions": 0,
            "last_analysis_minutes": 999,
        }


@st.cache_data(ttl=300)  # Cache pendant 5 minutes
def get_backtest_data():
    """Récupère et traite les données de backtest"""
    conn = sqlite3.connect("berzerk.db")
    cursor = conn.cursor()

    # Récupérer les décisions d'achat
    cursor.execute(
        """
        SELECT id, title, published_date, decision_json
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
        article_id, title, published_date, decision_json = row

        try:
            decision = json.loads(decision_json)
            action = decision.get("action", decision.get("decision", "")).upper()

            if action in ["ACHETER", "ACHAT", "BUY"]:
                ticker = decision.get("ticker")

                if ticker:
                    buy_decisions.append(
                        {
                            "article_id": article_id,
                            "title": title,
                            "ticker": ticker,
                            "decision_date": datetime.fromisoformat(published_date),
                            "action": action,
                            "justification": decision.get(
                                "justification", "Aucune justification"
                            ),
                            "allocation": decision.get(
                                "allocation_pourcentage",
                                decision.get("allocation_percent", 0.0),
                            ),
                            "confiance": decision.get(
                                "confiance", decision.get("confidence", "INCONNUE")
                            ),
                        }
                    )
        except Exception:
            continue

    return buy_decisions


def simulate_trade_performance(
    ticker: str, decision_date: datetime, holding_days: int = 7
) -> dict | None:
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
                buy_price = row["Open"]
                break

        if buy_price is None:
            buy_price = hist.iloc[-1]["Close"]

        # Prix de vente
        if datetime.now().date() < sell_date.date():
            sell_price = hist.iloc[-1]["Close"]
        else:
            for date, row in hist.iterrows():
                if date.date() >= sell_date.date():
                    sell_price = row["Open"]
                    break

            if sell_price is None:
                sell_price = hist.iloc[-1]["Close"]

        # Calculer la performance
        roi_percent = ((sell_price - buy_price) / buy_price) * 100

        return {
            "ticker": ticker,
            "buy_price": round(buy_price, 2),
            "sell_price": round(sell_price, 2),
            "roi_percent": round(roi_percent, 2),
            "is_profitable": roi_percent > 0,
            "decision_date": decision_date,
            "buy_date": buy_date,
            "sell_date": sell_date,
        }

    except Exception:
        return None


# =============================================================================
# FONCTIONS D'AFFICHAGE
# =============================================================================


def parse_decision_json(decision_json: str) -> dict:
    """Parse le JSON de décision de manière sécurisée"""
    if not decision_json:
        return {}
    try:
        return json.loads(decision_json)
    except Exception:
        return {}


def get_decision_color(action: str) -> str:
    """Retourne la couleur associée à une action"""
    colors = {
        "ACHETER": "#28a745",
        "VENDRE": "#dc3545",
        "SURVEILLER": "#ffc107",
        "IGNORER": "#6c757d",
    }
    return colors.get(action, "#6c757d")


def display_simple_article_card(article: dict):
    """Affiche une carte d'article ULTRA SIMPLE et LISIBLE"""
    decision = parse_decision_json(article.get("decision_json", "{}"))

    # Container principal
    st.markdown('<div class="article-card">', unsafe_allow_html=True)

    # TITRE de l'article (gros et lisible)
    title = article["title"]
    if len(title) > 80:
        title = title[:80] + "..."

    st.markdown(f'<div class="article-title">{title}</div>', unsafe_allow_html=True)

    # INFOS RAPIDES
    source = article.get("source", "Bloomberg")
    date_str = article.get("published_date", "")
    if date_str:
        try:
            date_obj = datetime.fromisoformat(date_str)
            date_display = date_obj.strftime("%d/%m à %H:%M")
        except Exception:
            date_display = "Date inconnue"
    else:
        date_display = "Date inconnue"

    st.markdown(
        f'<div class="article-meta">📰 {source} • 📅 {date_display}</div>',
        unsafe_allow_html=True,
    )

    # CONTENU PRINCIPAL selon le statut
    if article["status"] == "analyzed" and decision:
        # === ARTICLE ANALYSÉ ===

        # Action principale (gros badge visible)
        action = decision.get("action", decision.get("decision", "INCONNUE")).upper()
        ticker = decision.get("ticker", "N/A")

        if action == "ACHETER":
            badge_class = "badge-acheter"
            message = "✅ ACHETER"
            if ticker != "N/A":
                message += f" • {ticker}"
        elif action == "SURVEILLER":
            badge_class = "badge-surveiller"
            message = "👀 SURVEILLER"
            if ticker != "N/A":
                message += f" • {ticker}"
        elif action == "VENDRE":
            badge_class = "badge-vendre"
            message = "❌ VENDRE"
            if ticker != "N/A":
                message += f" • {ticker}"
        else:
            badge_class = "badge-ignorer"
            message = "⚪ IGNORER"

        st.markdown(
            f'<div class="{badge_class}">{message}</div>', unsafe_allow_html=True
        )

        # Détails importants (3 colonnes)
        col1, col2, col3 = st.columns(3)

        with col1:
            confidence = decision.get("confidence", decision.get("confiance", "N/A"))
            st.markdown(
                f'<div class="inline-metric"><strong>Confiance:</strong><br/>{confidence}</div>',
                unsafe_allow_html=True,
            )

        with col2:
            allocation = decision.get(
                "allocation_pourcentage", decision.get("allocation_percent", 0.0)
            )
            st.markdown(
                f'<div class="inline-metric"><strong>Allocation:</strong><br/>{allocation}%</div>',
                unsafe_allow_html=True,
            )

        with col3:
            if ticker != "N/A":
                st.markdown(
                    f'<div class="inline-metric"><strong>Titre:</strong><br/>{ticker}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="inline-metric"><strong>Statut:</strong><br/>Pas de titre</div>',
                    unsafe_allow_html=True,
                )

        # Justification (simple)
        justification = decision.get("justification", "")
        if len(justification) > 20:
            with st.expander("📋 Voir le raisonnement complet"):
                st.write(justification)

    else:
        # === ARTICLE NON ANALYSÉ ===
        if article["status"] == "pending":
            st.markdown("**🕒 EN ATTENTE D'ANALYSE**")
            st.info("Cet article sera analysé bientôt.")
        elif article["status"] == "in_progress":
            st.markdown("**⚡ ANALYSE EN COURS**")
            st.info("L'IA analyse cet article maintenant.")
        elif article["status"] == "error":
            st.markdown("**❌ ERREUR**")
            st.error("Problème lors de l'analyse.")
        else:
            st.markdown(f'**❓ STATUT: {article["status"].upper()}**')

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")  # Séparateur visible


def display_live_feed_tab():
    """Affiche l'onglet Live Feed ultra-simplifié"""

    # Récupération des statistiques
    stats = get_dashboard_stats()

    # EN-TÊTE SIMPLE
    st.markdown("# 📈 Analyses en Temps Réel")
    st.markdown("Surveillance automatique des actualités financières Bloomberg")
    st.markdown("---")

    # Controls rapides
    col1, col2 = st.columns([1, 3])

    with col1:
        if st.button("🔄 Actualiser", type="primary"):
            st.cache_data.clear()
            st.rerun()

    with col2:
        auto_refresh = st.checkbox(
            "🔁 Auto-actualisation",
            value=False,
            help="Actualise automatiquement toutes les 30 secondes",
        )
        if auto_refresh:
            time.sleep(30)
            st.rerun()

    # TABLEAU DE BORD SIMPLE
    st.markdown("## 📊 Situation Actuelle")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "📰 Articles Total",
            stats["total_articles"],
            help="Nombre total d'articles dans la base",
        )

    with col2:
        analyzed_count = stats["analyzed_articles"]
        st.metric("✅ Analysés", analyzed_count, help="Articles analysés par l'IA")

    with col3:
        buy_count = stats.get("buy_decisions", 0)
        st.metric(
            "🎯 Opportunités", buy_count, help="Recommandations d'achat détectées"
        )

    # FILTRES SIMPLES
    st.markdown("---")
    st.markdown("## 🔍 Filtres")

    col1, col2 = st.columns(2)

    with col1:
        show_filter = st.selectbox(
            "Afficher:",
            [
                "Tous les articles",
                "Seulement les analysés",
                "Seulement les recommandations d'achat",
            ],
        )

    with col2:
        period_filter = st.selectbox(
            "Période:", ["Toutes", "Dernières 24h", "Cette semaine"]
        )

    # RÉCUPÉRATION ET FILTRAGE DES ARTICLES
    articles = get_articles_with_decisions()

    # Application des filtres
    if show_filter == "Seulement les analysés":
        articles = [a for a in articles if a["status"] == "analyzed"]
    elif show_filter == "Seulement les recommandations d'achat":
        articles = [
            a
            for a in articles
            if a["status"] == "analyzed"
            and "ACHETER" in str(a.get("decision_json", ""))
        ]

    if period_filter != "Toutes":
        days_map = {"Dernières 24h": 1, "Cette semaine": 7}
        days = days_map[period_filter]
        cutoff_date = datetime.now() - timedelta(days=days)
        articles = [
            a
            for a in articles
            if datetime.fromisoformat(a.get("published_date", "1970-01-01"))
            > cutoff_date
        ]

    # AFFICHAGE DES ARTICLES
    st.markdown("---")
    st.markdown(f"## 📋 Articles ({len(articles)} résultats)")

    if len(articles) == 0:
        st.info("🔍 Aucun article trouvé avec ces filtres.")
    else:
        for article in articles:
            display_simple_article_card(article)


def display_performance_tab():
    """Affiche l'onglet Performance & Backtest"""
    st.markdown(
        '<div class="main-header"><h1>🏆 Performance & Backtest</h1></div>',
        unsafe_allow_html=True,
    )

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
                decision["ticker"], decision["decision_date"]
            )

            if result:
                result.update(
                    {
                        "title": decision["title"],
                        "allocation": decision["allocation"],
                        "confidence": decision["confiance"],
                    }
                )
                trade_results.append(result)

            progress_bar.progress((i + 1) / len(buy_decisions))

        progress_bar.empty()

    if not trade_results:
        st.error("Aucun trade n'a pu être simulé.")
        return

    # Calcul des KPIs
    total_trades = len(trade_results)
    winning_trades = len([t for t in trade_results if t["is_profitable"]])
    losing_trades = total_trades - winning_trades
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0

    total_roi = sum(t["roi_percent"] for t in trade_results)
    avg_roi = total_roi / total_trades if total_trades > 0 else 0

    best_trade = max(trade_results, key=lambda x: x["roi_percent"])
    worst_trade = min(trade_results, key=lambda x: x["roi_percent"])

    # A. KPIs de Performance
    st.markdown("### 📈 KPIs de Performance")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "🎯 Taux de Réussite",
            f"{win_rate:.1f}%",
            delta=f"{winning_trades}/{total_trades}",
            help="Pourcentage de trades rentables",
        )

    with col2:
        st.metric(
            "📊 ROI Moyen",
            f"{avg_roi:+.2f}%",
            help="Retour sur investissement moyen par trade",
        )

    with col3:
        st.metric(
            "✅ Trades Gagnants", winning_trades, help="Nombre de trades profitables"
        )

    with col4:
        st.metric("❌ Trades Perdants", losing_trades, help="Nombre de trades en perte")

    # B. Graphique de Performance Cumulée
    st.markdown("### 📈 Performance Cumulée")

    # Calcul de la performance cumulée
    cumulative_performance = []
    capital = 100  # Capital initial de 100€

    for i, trade in enumerate(trade_results):
        capital = capital * (1 + trade["roi_percent"] / 100)
        cumulative_performance.append(
            {
                "Trade": i + 1,
                "Capital": capital,
                "Date": trade["decision_date"],
                "Ticker": trade["ticker"],
                "ROI": trade["roi_percent"],
            }
        )

    df_perf = pd.DataFrame(cumulative_performance)

    # Graphique Plotly
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df_perf["Trade"],
            y=df_perf["Capital"],
            mode="lines+markers",
            name="Capital Cumulé",
            line={"color": "#2a5298", "width": 3},
            marker={"size": 6},
            hovertemplate="<b>Trade %{x}</b><br>"
            + "Capital: %{y:.2f}€<br>"
            + "ROI: %{customdata:.2f}%<extra></extra>",
            customdata=df_perf["ROI"],
        )
    )

    fig.add_hline(
        y=100,
        line_dash="dash",
        line_color="gray",
        annotation_text="Capital Initial (100€)",
    )

    fig.update_layout(
        title="🚀 Évolution du Capital (100€ initial)",
        xaxis_title="Numéro de Trade",
        yaxis_title="Capital (€)",
        height=500,
        showlegend=True,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Métriques finales
    final_capital = df_perf["Capital"].iloc[-1]
    total_return = ((final_capital - 100) / 100) * 100

    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "💰 Capital Final", f"{final_capital:.2f}€", delta=f"{total_return:+.2f}%"
        )

    with col2:
        st.metric(
            "🎯 Performance Totale",
            f"{total_return:+.2f}%",
            help="Performance totale depuis le début",
        )

    # C. Tableau des Trades Détaillés
    st.markdown("### 📋 Tableau des Trades Détaillés")

    # Préparation du DataFrame
    df_trades = pd.DataFrame(trade_results)

    # Formatage des colonnes
    df_trades["decision_date"] = pd.to_datetime(df_trades["decision_date"]).dt.strftime(
        "%Y-%m-%d"
    )
    df_trades["buy_date"] = pd.to_datetime(df_trades["buy_date"]).dt.strftime(
        "%Y-%m-%d"
    )
    df_trades["Performance"] = df_trades["roi_percent"].apply(lambda x: f"{x:+.2f}%")

    # Sélection des colonnes à afficher
    display_columns = [
        "ticker",
        "title",
        "decision_date",
        "buy_price",
        "sell_price",
        "Performance",
        "confidence",
    ]
    df_display = df_trades[display_columns].copy()

    # Renommage des colonnes
    df_display.columns = [
        "Ticker",
        "Titre",
        "Date Décision",
        "Prix Achat",
        "Prix Vente",
        "Performance",
        "Confiance",
    ]

    # Style conditionnel
    def highlight_performance(row):
        if "Performance" in row:
            if "+" in str(row["Performance"]):
                return ["background-color: #d4edda"] * len(row)
            else:
                return ["background-color: #f8d7da"] * len(row)
        return [""] * len(row)

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

    # Navigation par onglets
    tab1, tab2 = st.tabs(["📈 Live Feed", "🏆 Performance & Backtest"])

    with tab1:
        display_live_feed_tab()

    with tab2:
        display_performance_tab()


if __name__ == "__main__":
    main()
