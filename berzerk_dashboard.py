#!/usr/bin/env python3
"""
⚡ BERZERK - Decision Feed
========================

Interface épurée "Clarté Radicale" pour le suivi des décisions d'investissement IA.
Philosophie : Priorité à l'action, simplicité, hiérarchie claire.

Auteur: BERZERK Team
Phase: 8.1 - Ajout du suivi de performance instantané
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# Configuration de la page
st.set_page_config(
    page_title="BERZERK Decision Feed",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- NOUVELLES FONCTIONS DE PERFORMANCE ---



@st.cache_data(ttl=60)  # Cache 1 minute pour les prix actuels
def get_current_price(ticker: str) -> float:
    """Récupère le prix actuel d'une action avec des fallbacks robustes."""
    ticker = ticker.strip().replace("$", "")  # Nettoyage du ticker
    if not ticker:
        return 0.0
    try:
        stock = yf.Ticker(ticker)
        
        # 1. Priorité aux données intraday
        data = stock.history(period="1d", interval="1m")
        if not data.empty:
            return float(data["Close"].iloc[-1])

        # 2. Fallback sur 'info'
        info = stock.info
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        if price:
            return float(price)

        # 3. Fallback ultime sur la dernière clôture historique
        hist = stock.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
            
        return 0.0
    except Exception:
        # Gestion silencieuse des erreurs
        return 0.0


# --- FONCTIONS EXISTANTES (MODIFIÉES ET CONSERVÉES) ---


def display_confidence_signal(confidence: str):
    """Affiche un indicateur visuel de force du signal."""
    confidence_map = {"ÉLEVÉE": 3, "MOYENNE": 2, "FAIBLE": 1}
    level = confidence_map.get(confidence.upper(), 0)

    bars = "".join(
        [
            f'<div class="signal-bar {"filled" if i < level else ""}"></div>'
            for i in range(3)
        ]
    )

    st.markdown(
        f"""
        <div class="signal-container">
            <div class="signal-bars">{bars}</div>
            <span class="signal-text">{confidence.capitalize()}</span>
        </div>
    """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=900)  # Cache de 15 minutes pour les graphiques
def get_sparkline_chart(ticker: str):
    """Génère un mini-graphique (sparkline) avec couleur de tendance."""
    ticker = ticker.strip().replace("$", "")  # Nettoyage du ticker
    if not ticker:
        return None, "N/A"

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="7d", interval="1d")

        if len(hist) < 2:
            return None, "N/A"

        start_price = hist["Close"].iloc[0]
        end_price = hist["Close"].iloc[-1]

        color = "#28a745" if end_price > start_price else "#dc3545"
        fill_color = (
            "rgba(40, 167, 69, 0.1)"
            if end_price > start_price
            else "rgba(220, 53, 69, 0.1)"
        )
        trend = "Haussier" if end_price > start_price else "Baissier"

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=hist.index,
                y=hist["Close"],
                mode="lines",
                line={"color": color, "width": 2.5},
                fill="tozeroy",
                fillcolor=fill_color,
            )
        )
        fig.update_layout(
            height=50,
            margin={"l": 0, "r": 0, "t": 5, "b": 0},
            xaxis={"visible": False},
            yaxis={"visible": False},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )
        return fig, trend
    except Exception:
        # Gestion silencieuse des erreurs
        return None, "N/A"


@st.cache_data(ttl=60)  # Cache de 60 secondes
def load_decisions_from_db() -> list[dict[str, Any]]:
    """Charge les décisions depuis la DB et les enrichit avec les données de performance."""
    try:
        conn = sqlite3.connect("berzerk.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT title, link, published_date, decision_json, analyzed_at
            FROM articles
            WHERE decision_json IS NOT NULL AND status = 'analyzed'
            AND analyzed_at >= datetime('now', '-30 days')
            ORDER BY analyzed_at DESC
        """
        )

        rows = cursor.fetchall()
        conn.close()

        decisions = []
        for title, link, _published_date, decision_json, analyzed_at in rows:
            try:
                decision_data = json.loads(decision_json)
                
                # --- DÉBUT DE LA MODIFICATION ---
                # Récupérer l'action brute, quelle que soit la clé utilisée ("action" ou "decision")
                action_brute = decision_data.get("action", decision_data.get("decision", "INCONNUE")).upper()
                
                # Normaliser l'action pour qu'elle soit compatible avec le nouveau système
                if action_brute == "ACHETER":
                    action_normalisee = "LONG"
                elif action_brute == "VENDRE":
                    action_normalisee = "SHORT"
                else:
                    # Garde les actions déjà au bon format (LONG, SHORT, SURVEILLER)
                    action_normalisee = action_brute
                # --- FIN DE LA MODIFICATION ---
                
                ticker = decision_data.get("ticker", None)

                if action_normalisee in ["INCONNUE", "ERREUR"] or not ticker:
                    continue

                # Créer un identifiant unique basé sur analyzed_at pour éviter les clés dupliquées
                unique_id = hashlib.md5(f"{analyzed_at}_{link}".encode()).hexdigest()[
                    :8
                ]

                # --- ENRICHISSEMENT AVEC DONNÉES DE PERFORMANCE ---
                prix_decision = float(decision_data.get("prix_a_la_decision", 0.0))
                
                # On récupère le prix actuel pour la comparaison
                prix_actuel = get_current_price(ticker)

                decision = {
                    "action": action_normalisee,
                    "ticker": ticker,
                    "unique_id": unique_id,  # Identifiant unique pour éviter les doublons
                    "nom_entreprise": decision_data.get(
                        "nom_entreprise", f"Entreprise {ticker}"
                    ),
                    "news_title": title,
                    "analyzed_at": analyzed_at,
                    # NOUVELLES DONNÉES DE PERFORMANCE
                    "prix_decision": prix_decision,
                    "prix_actuel": prix_actuel,
                    # ---
                    "justification": decision_data.get(
                        "justification_synthetique",
                        decision_data.get(
                            "justification", "Analyse automatique BERZERK"
                        ),
                    ),
                    "points_positifs": decision_data.get(
                        "points_cles_positifs", ["Analyse favorable"]
                    ),
                    "points_negatifs": decision_data.get(
                        "points_cles_negatifs_risques", ["Risques standards"]
                    ),
                    "allocation_pct": decision_data.get(
                        "allocation_capital_pourcentage",
                        decision_data.get("allocation_pourcentage", 0.0),
                    ),
                    "confiance": decision_data.get("confiance", "MOYENNE"),
                    "horizon": decision_data.get("horizon", "Court Terme"),
                    "article_link": link,
                }
                decisions.append(decision)

            except (json.JSONDecodeError, KeyError) as e:
                print(f"Erreur parsing JSON pour '{title}': {e}")
                continue

        return decisions

    except Exception as e:
        st.error(f"Erreur critique chargement données : {e}")
        return []


def get_sample_decisions() -> list[dict[str, Any]]:
    """Génère des décisions d'exemple pour la démonstration (avec données de performance)."""
    return [
        {
            "action": "LONG",
            "ticker": "AAPL",
            "unique_id": "sample001",
            "nom_entreprise": "Apple Inc.",
            "news_title": "Apple annonce des avancées majeures dans l'IA pour l'iPhone 17.",
            "analyzed_at": "2024-12-07T14:32:00",
            "prix_decision": 195.50,
            "prix_actuel": get_current_price("AAPL"),
            "justification": "L'annonce d'une nouvelle puce IA devrait booster les ventes et donner un avantage concurrentiel significatif à Apple sur le marché des smartphones.",
            "points_positifs": [
                "Avantage concurrentiel IA",
                "Cycle de remplacement accéléré",
                "Marges élevées",
            ],
            "points_negatifs": [
                "Risques d'exécution",
                "Valorisation déjà élevée",
                "Concurrence intense",
            ],
            "allocation_pct": 2.5,
            "confiance": "ÉLEVÉE",
            "horizon": "Moyen Terme",
            "article_link": "https://example.com/apple-ai-news",
        },
        {
            "action": "SHORT",
            "ticker": "XOM",
            "unique_id": "sample002",
            "nom_entreprise": "ExxonMobil Corporation",
            "news_title": "OPEC+ augmente la production, craintes de surabondance pétrolière",
            "analyzed_at": "2024-12-07T12:15:00",
            "prix_decision": 118.75,
            "prix_actuel": get_current_price("XOM"),
            "justification": "La surabondance de l'offre pétrolière et les craintes sur la demande exercent une pression baissière directe sur la rentabilité future de XOM.",
            "points_positifs": ["Dividende stable", "Gestion financière solide"],
            "points_negatifs": [
                "Pression sur les prix du pétrole",
                "Surabondance de l'offre",
                "Demande incertaine",
            ],
            "allocation_pct": 0.0,
            "confiance": "MOYENNE",
            "horizon": "Court Terme",
            "article_link": "https://example.com/opec-oil-news",
        },
        {
            "action": "SURVEILLER",
            "ticker": "NVDA",
            "unique_id": "sample003",
            "nom_entreprise": "NVIDIA Corporation",
            "news_title": "NVIDIA présente ses nouveaux processeurs IA de nouvelle génération",
            "analyzed_at": "2024-12-07T10:45:00",
            "prix_decision": 485.20,
            "prix_actuel": get_current_price("NVDA"),
            "justification": "Innovation prometteuse mais valorisation déjà élevée. Attendre une correction pour une meilleure opportunité d'entrée.",
            "points_positifs": [
                "Leadership IA",
                "Innovation continue",
                "Demande croissante",
            ],
            "points_negatifs": [
                "Valorisation excessive",
                "Volatilité élevée",
                "Dépendance cyclique",
            ],
            "allocation_pct": 1.0,
            "confiance": "FAIBLE",
            "horizon": "Long Terme",
            "article_link": "https://example.com/nvidia-ai-news",
        },
    ]


def display_decision_card(decision: dict[str, Any]):
    """Affiche une carte de décision 2.1 avec suivi de performance intégré."""
    action = decision["action"]
    color_map = {
        "LONG": "#28a745",      # Vert pour LONG
        "SHORT": "#dc3545",     # Rouge pour SHORT
        "ACHETER": "#28a745",   # Compatibilité avec les anciennes données
        "VENDRE": "#dc3545",    # Compatibilité avec les anciennes données
        "SURVEILLER": "#ffc107",
        "IGNORER": "#6c757d",
    }

    with st.container(border=True):

        # === EN-TÊTE INTÉGRÉ (INFO + GRAPHIQUE) ===
        header_cols = st.columns([1, 2.5, 2])

        with header_cols[0]:
            # Badge d'action
            st.markdown(
                f"""
                <div style="background-color: {color_map.get(action, '#6c757d')}; color: white; padding: 12px; text-align: center; border-radius: 8px; font-weight: bold; font-size: 1.1rem; height: 100%;">
                    {action}
                </div>
            """,
                unsafe_allow_html=True,
            )

        with header_cols[1]:
            # Ticker, Nom et News
            st.subheader(f"{decision['ticker']} - {decision['nom_entreprise']}")
            st.write(f"_{decision['news_title']}_")
            analyzed_dt = datetime.fromisoformat(
                decision["analyzed_at"].replace("Z", "+00:00")
            )
            st.caption(f"Analyse du {analyzed_dt.strftime('%d/%m/%y %H:%M')}")

        with header_cols[2]:
            # Sparkline avec clé unique
            sparkline_fig, trend = get_sparkline_chart(decision["ticker"])
            if sparkline_fig:
                # Clé unique utilisant ticker + unique_id pour éviter les doublons
                unique_key = f"sparkline_{decision['ticker']}_{decision['unique_id']}"
                st.plotly_chart(sparkline_fig, use_container_width=True, key=unique_key)
                st.caption(f"Tendance 7J: {trend}")
            else:
                st.caption("Tendance 7J: Données indisponibles")

        # Affichage conditionnel pour IGNORER/SURVEILLER
        if action in ["IGNORER", "SURVEILLER"]:
            st.info(f"Raison de la surveillance : {decision['justification']}")
        else:
            # --- SECTION ROBUSTE : SUIVI DE PERFORMANCE ---
            st.markdown("---")
            st.markdown(
                '<div class="key-indicator-title" style="text-align:left; margin-bottom: 0.5rem;">📊 Suivi de la Position</div>',
                unsafe_allow_html=True,
            )

            perf_cols = st.columns(3)
            prix_decision = decision.get("prix_decision", 0.0)
            prix_actuel = decision.get("prix_actuel", 0.0)
            # Affichage du Prix à la Décision
            with perf_cols[0]:
                if prix_decision > 0:
                    st.metric("Prix à la décision", f"{prix_decision:.2f} $")
                else:
                    st.metric("Prix à la décision", "N/A", help="Le prix n'a pas pu être capturé au moment de la décision.")
            # Affichage du Prix Actuel
            with perf_cols[1]:
                if prix_actuel > 0:
                    st.metric("Prix actuel", f"{prix_actuel:.2f} $")
                else:
                    st.metric("Prix actuel", "N/A", help="Le prix actuel est indisponible (marché fermé ou ticker invalide).")
            # Affichage de la Performance (conditionnel)
            with perf_cols[2]:
                if prix_decision > 0 and prix_actuel > 0:
                    perf_pct = 0
                    if decision["action"] == "LONG":
                        perf_pct = ((prix_actuel - prix_decision) / prix_decision) * 100
                    elif decision["action"] == "SHORT":
                        perf_pct = ((prix_decision - prix_actuel) / prix_decision) * 100
                    st.metric(
                        "Performance",
                        f"{perf_pct:+.2f}%",
                        delta_color="normal" if perf_pct >= 0 else "inverse",
                    )
                else:
                    st.metric("Performance", "N/A", help="Calcul impossible sans les deux prix.")
            st.markdown("---")
        # --- FIN DE LA SECTION MODIFIÉE ---

        # === INDICATEURS CLÉS ===
        kpi_cols = st.columns(3)

        # Récupération du secteur via yfinance (gestion silencieuse des erreurs)
        sector = "N/A"
        try:
            stock_info = yf.Ticker(decision["ticker"]).info
            sector = stock_info.get("sector", "N/A")
        except Exception:
            pass

        with kpi_cols[0]:
            st.markdown(
                '<div class="key-indicator-title">Force du Signal</div>',
                unsafe_allow_html=True,
            )
            display_confidence_signal(decision.get("confiance", "INCONNUE"))

        with kpi_cols[1]:
            st.markdown(
                '<div class="key-indicator-title">Horizon</div>', unsafe_allow_html=True
            )
            st.markdown(
                f'<div class="key-indicator-value">{decision.get("horizon", "N/A")}</div>',
                unsafe_allow_html=True,
            )

        with kpi_cols[2]:
            st.markdown(
                '<div class="key-indicator-title">Secteur</div>', unsafe_allow_html=True
            )
            st.markdown(
                f'<div class="key-indicator-value">{sector}</div>',
                unsafe_allow_html=True,
            )

        # === EXPANDER POUR LES DÉTAILS ===
        with st.expander("▼ Voir le raisonnement de l'IA et les détails"):
            st.markdown("#### Justification de l'IA")
            st.write(decision["justification"])
            st.markdown("---")
            col_pos, col_neg = st.columns(2)
            with col_pos:
                st.markdown("✅ **Points Clés Positifs**")
                for point in decision["points_positifs"]:
                    st.write(f"• {point}")
            with col_neg:
                st.markdown("⚠️ **Risques & Points Négatifs**")
                for point in decision["points_negatifs"]:
                    st.write(f"• {point}")
            if decision["action"] == "LONG":
                st.info(
                    f"💡 Allocation Suggérée: {decision['allocation_pct']}% du capital de trading."
                )
            st.link_button("Consulter l'article original ↗", decision["article_link"])


def display_decision_feed():
    """Affiche le flux de décisions avec suivi de performance."""
    # === BARRE DE STATUT ===
    stat_col1, stat_col2, stat_col3 = st.columns(3)

    # Charger les décisions
    decisions = load_decisions_from_db()

    # Si pas de données réelles, utiliser les exemples
    if not decisions:
        st.warning("🔄 Aucune décision récente dans la base. Affichage des exemples.")
        decisions = get_sample_decisions()

    # Calculs pour les statistiques
    now = datetime.now()
    decisions_24h = len(
        [
            d
            for d in decisions
            if datetime.fromisoformat(d["analyzed_at"].replace("Z", "+00:00"))
            > now - timedelta(hours=24)
        ]
    )
    # Compter les signaux LONG des dernières 24h
    longs_24h = len(
        [
            d
            for d in decisions
            if d["action"] == "LONG"
            and datetime.fromisoformat(d["analyzed_at"].replace("Z", "+00:00"))
            > now - timedelta(hours=24)
        ]
    )

    with stat_col1:
        st.metric("Statut Système", "🟢 Opérationnel")

    with stat_col2:
        st.metric("Décisions 24h", decisions_24h)

    with stat_col3:
        st.metric("Signaux LONG 24h", longs_24h)

    st.markdown("---")

    # === FLUX PRINCIPAL ===
    if decisions:
        st.markdown("### 📈 Flux de Décisions avec Suivi de Performance")

        for decision in decisions:
            display_decision_card(decision)
            st.markdown("")  # Espace entre les cartes
    else:
        st.info("📊 Aucune décision à afficher pour le moment.")
        st.markdown(
            "Lancez le monitoring pour commencer à générer des décisions : `python start_realtime_monitor.py`"
        )


def display_active_portfolio():
    """Affiche le portefeuille actif avec KPIs et tableau détaillé."""
    st.header("📊 Suivi du Portefeuille Actif")
    
    decisions = load_decisions_from_db()
    
    # --- VÉRIFICATION CLÉ ---
    # Ce filtrage fonctionnera maintenant grâce à la normalisation faite en Phase 1
    active_positions = [d for d in decisions if d['action'] in ['LONG', 'SHORT']]
    # --- FIN DE LA VÉRIFICATION ---

    if not active_positions:
        st.warning("ℹ️ Aucune position LONG ou SHORT n'a été trouvée dans les décisions récentes.")
        st.write("Le portefeuille actif s'affichera ici dès que de nouvelles positions de trading seront prises par l'IA.")
        return
    
    # Calculer les KPIs globaux
    total_pnl_pct = 0
    winning_trades = 0
    
    for pos in active_positions:
        prix_decision = pos.get("prix_decision", 0.0)
        prix_actuel = pos.get("prix_actuel", 0.0)
        pnl_pct = 0
        if prix_decision > 0 and prix_actuel > 0:
            if pos['action'] == 'LONG':
                pnl_pct = ((prix_actuel - prix_decision) / prix_decision) * 100
            elif pos['action'] == 'SHORT':
                pnl_pct = ((prix_decision - prix_actuel) / prix_decision) * 100
        
        if pnl_pct > 0:
            winning_trades += 1
        total_pnl_pct += pnl_pct

    avg_pnl = total_pnl_pct / len(active_positions)
    win_rate = (winning_trades / len(active_positions)) * 100
    
    # Afficher les KPIs
    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        st.metric("Positions Ouvertes", len(active_positions))
    with kpi_cols[1]:
        long_count = len([p for p in active_positions if p['action'] == 'LONG'])
        st.metric("Positions LONG", long_count)
    with kpi_cols[2]:
        short_count = len([p for p in active_positions if p['action'] == 'SHORT'])
        st.metric("Positions SHORT", short_count)
    with kpi_cols[3]:
        st.metric("Taux de Réussite", f"{win_rate:.1f}%")
        
    st.markdown("---")
    
    # Tableau détaillé des positions
    st.subheader("Détail des Positions")
    
    # Créer les en-têtes du tableau
    header_cols = st.columns([1, 1, 2, 1.5, 1.5, 1.5])
    headers = ["Ticker", "Direction", "Date Entrée", "Prix Entrée", "Prix Actuel", "Performance (%)"]
    for col, header in zip(header_cols, headers):
        col.markdown(f"**{header}**")

    # Mapping des couleurs
    color_map = {
        "LONG": "#28a745",
        "SHORT": "#dc3545",
        "SURVEILLER": "#ffc107",
        "IGNORER": "#6c757d",
    }

    # Afficher chaque position
    for pos in active_positions:
        prix_decision = pos.get("prix_decision", 0.0)
        prix_actuel = pos.get("prix_actuel", 0.0)
        pnl_pct = 0
        
        if prix_decision > 0 and prix_actuel > 0:
            if pos['action'] == 'LONG':
                pnl_pct = ((prix_actuel - prix_decision) / prix_decision) * 100
            elif pos['action'] == 'SHORT':
                pnl_pct = ((prix_decision - prix_actuel) / prix_decision) * 100

        color = "green" if pnl_pct >= 0 else "red"
        
        row_cols = st.columns([1, 1, 2, 1.5, 1.5, 1.5])
        row_cols[0].text(pos['ticker'])
        row_cols[1].markdown(f"**<font color='{color_map[pos['action']]}'>{pos['action']}</font>**", unsafe_allow_html=True)
        analyzed_dt = datetime.fromisoformat(pos["analyzed_at"].replace("Z", "+00:00"))
        row_cols[2].text(analyzed_dt.strftime('%d/%m/%y %H:%M'))
        row_cols[3].text(f"{prix_decision:.2f} $")
        row_cols[4].text(f"{prix_actuel:.2f} $")
        row_cols[5].markdown(f"**<font color='{color}'>{pnl_pct:+.2f}%</font>**", unsafe_allow_html=True)
        
        # Ajouter un expander pour les détails du signal original
        with st.expander(f"Voir détails pour {pos['ticker']}"):
            st.write(f"**Signal original :** {pos['news_title']}")
            st.write(f"**Justification IA :** {pos['justification']}")


def main():
    """Fonction principale de l'interface Decision Feed."""

    # === STYLES CSS ENRICHIS ===
    st.markdown(
        """
        <style>
        /* STYLES EXISTANTS POUR LA CARTE AMÉLIORÉE */
        .signal-container {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .signal-bars {
            display: flex;
            align-items: flex-end;
            gap: 2px;
        }
        .signal-bar {
            width: 6px;
            background-color: #e0e0e0;
            border-radius: 2px;
        }
        .signal-bar:nth-child(1) { height: 8px; }
        .signal-bar:nth-child(2) { height: 12px; }
        .signal-bar:nth-child(3) { height: 16px; }
        .signal-bar.filled {
            background-color: #34a853;
        }
        .signal-text {
            font-size: 0.9rem;
            font-weight: 500;
        }
        .key-indicator-title {
            font-size: 0.8rem;
            color: #5f6368;
            margin-bottom: 0.3rem;
            text-transform: uppercase;
        }
        .key-indicator-value {
            font-size: 1rem;
            font-weight: 600;
            color: #202124;
        }

        /* NOUVEAUX STYLES POUR LA PERFORMANCE */
        .perf-container {
            border: 1px solid #e0e0e0;
            border-radius: 0.5rem;
            padding: 0.8rem 1rem;
            text-align: center;
            background-color: #f8f9fa;
        }
        .perf-label {
            font-size: 0.75rem;
            color: #5f6368;
            margin-bottom: 0.25rem;
            text-transform: uppercase;
            font-weight: 500;
        }
        .perf-value {
            font-size: 1.2rem;
            font-weight: 700;
        }
        .perf-positive { color: #1e8e3e; }
        .perf-negative { color: #d93025; }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # === EN-TÊTE ===
    st.title("⚡ BERZERK - Centre de Commandement Trading")
    st.caption("Analyse IA. Décisions Immédiates. Suivi de Performance Temps Réel.")

    # Création des deux onglets principaux
    tab1, tab2 = st.tabs(["⚡ Flux de Décisions", "📊 Portefeuille Actif"])

    with tab1:
        display_decision_feed()

    with tab2:
        display_active_portfolio()
    
    # Rafraîchissement automatique natif Python - Solution robuste
    from streamlit_autorefresh import st_autorefresh

    # Configure le composant pour rafraîchir la page toutes les 60 secondes (60000 millisecondes)
    # On peut aussi ajouter un compteur visuel si on le souhaite.
    st_autorefresh(interval=60 * 1000, key="price_refresher")

    # Ajouter un indicateur visuel pour l'utilisateur
    st.markdown("""
        <div style="position: fixed; bottom: 10px; right: 15px; padding: 6px 12px; background: rgba(0, 0, 0, 0.6); color: white; border-radius: 8px; font-family: monospace; font-size: 12px; z-index: 9999;">
            Auto-Refresh: 60s
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
