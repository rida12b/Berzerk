#!/usr/bin/env python3
"""
⚡ BERZERK - Decision Feed
========================

Interface épurée "Clarté Radicale" pour le suivi des décisions d'investissement IA.
Philosophie : Priorité à l'action, simplicité, hiérarchie claire.

Auteur: BERZERK Team
Phase: 8.1 - Ajout du suivi de performance instantané
"""

import streamlit as st
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any
import yfinance as yf
import plotly.graph_objects as go

# Configuration de la page
st.set_page_config(
    page_title="BERZERK Decision Feed",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- NOUVELLES FONCTIONS DE PERFORMANCE ---


@st.cache_data(ttl=86400)  # Cache de 1 jour, car ce prix historique ne changera pas.
def get_price_at_decision_time(ticker: str, decision_time_str: str) -> float:
    """
    Récupère le prix de clôture du jour de la décision (ou du jour précédent si marché fermé).
    Cette méthode est extrêmement rapide car elle n'utilise que des données journalières.
    """
    ticker = ticker.strip().replace("$", "")
    if not ticker:
        return 0.0

    try:
        decision_dt = datetime.fromisoformat(decision_time_str.replace("Z", "+00:00"))
        decision_date = decision_dt.date()

        stock = yf.Ticker(ticker)

        # On télécharge une petite plage de données journalières autour de la date de décision. C'est très rapide.
        hist = stock.history(
            start=decision_date - timedelta(days=7),
            end=decision_date + timedelta(days=1),
        )

        if hist.empty:
            return 0.0

        # On cherche les données pour le jour exact de la décision
        day_data = hist[hist.index.date == decision_date]

        # CAS 1: Le marché était ouvert ce jour-là. On prend le prix de clôture.
        if not day_data.empty:
            return float(day_data["Close"].iloc[0])

        # CAS 2: Le marché était fermé (weekend/jour férié). On prend la clôture du jour d'avant.
        else:
            previous_days_data = hist[hist.index.date < decision_date]
            if not previous_days_data.empty:
                return float(previous_days_data["Close"].iloc[-1])

        return 0.0
    except Exception:
        return 0.0


@st.cache_data(ttl=60)  # Cache 1 minute pour les prix actuels
def get_current_price(ticker: str) -> float:
    """Récupère le prix actuel d'une action via yfinance (version robuste)."""
    ticker = ticker.strip().replace("$", "")  # Nettoyage du ticker
    if not ticker:
        return 0.0

    try:
        stock = yf.Ticker(ticker)
        data = stock.history(
            period="1d", interval="1m"
        )  # On prend la dernière minute pour le prix le plus récent
        if not data.empty:
            return float(data["Close"].iloc[-1])

        # Fallback si les données intraday ne sont pas dispo
        price = stock.info.get("regularMarketPrice")
        if price:
            return float(price)

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
                line=dict(color=color, width=2.5),
                fill="tozeroy",
                fillcolor=fill_color,
            )
        )
        fig.update_layout(
            height=50,
            margin=dict(l=0, r=0, t=5, b=0),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )
        return fig, trend
    except Exception as e:
        # Gestion silencieuse des erreurs
        return None, "N/A"


@st.cache_data(ttl=60)  # Cache de 60 secondes
def load_decisions_from_db() -> List[Dict[str, Any]]:
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
        for title, link, published_date, decision_json, analyzed_at in rows:
            try:
                decision_data = json.loads(decision_json)
                action = decision_data.get(
                    "action", decision_data.get("decision", "INCONNUE")
                ).upper()
                ticker = decision_data.get("ticker", None)

                if action == "INCONNUE" or not ticker:
                    continue

                # Créer un identifiant unique basé sur analyzed_at pour éviter les clés dupliquées
                unique_id = hashlib.md5(f"{analyzed_at}_{link}".encode()).hexdigest()[
                    :8
                ]

                # --- ENRICHISSEMENT AVEC DONNÉES DE PERFORMANCE ---
                prix_decision = get_price_at_decision_time(ticker, analyzed_at)
                prix_actuel = get_current_price(ticker)

                decision = {
                    "action": action,
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


def get_sample_decisions() -> List[Dict[str, Any]]:
    """Génère des décisions d'exemple pour la démonstration (avec données de performance)."""
    return [
        {
            "action": "ACHETER",
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
            "action": "VENDRE",
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


def display_decision_card(decision: Dict[str, Any]):
    """Affiche une carte de décision 2.1 avec suivi de performance intégré."""
    action = decision["action"]
    color_map = {
        "ACHETER": "#28a745",
        "VENDRE": "#dc3545",
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

        # --- NOUVELLE SECTION : SUIVI DE PERFORMANCE (AVEC CONDITION) ---
        # On affiche la performance SEULEMENT si on a un prix de décision valide (> 0)
        if decision["prix_decision"] > 0 and decision["prix_actuel"] > 0:
            st.markdown("---")
            st.markdown(
                '<div class="key-indicator-title" style="text-align:left; margin-bottom: 0.5rem;">📊 Suivi de la Position</div>',
                unsafe_allow_html=True,
            )

            perf_cols = st.columns(3)

            # Calcul de la performance
            perf_pct = 0
            if decision["action"] == "ACHETER":
                perf_pct = (
                    (decision["prix_actuel"] - decision["prix_decision"])
                    / decision["prix_decision"]
                ) * 100
            elif decision["action"] == "VENDRE":  # Vente à découvert
                perf_pct = (
                    (decision["prix_decision"] - decision["prix_actuel"])
                    / decision["prix_decision"]
                ) * 100

            perf_color = "perf-positive" if perf_pct >= 0 else "perf-negative"
            perf_emoji = "📈" if perf_pct >= 0 else "📉"

            with perf_cols[0]:
                st.metric("Prix à la décision", f"{decision['prix_decision']:.2f} $")
            with perf_cols[1]:
                st.metric("Prix actuel", f"{decision['prix_actuel']:.2f} $")
            with perf_cols[2]:
                # On remplace le conteneur de performance par une métrique standard pour un meilleur alignement
                st.metric(
                    "Performance",
                    f"{perf_pct:+.2f}%",
                    delta_color="normal" if perf_pct >= 0 else "inverse",
                )

        st.markdown("---")
        # --- FIN DE LA SECTION MODIFIÉE ---

        # === INDICATEURS CLÉS ===
        kpi_cols = st.columns(3)

        # Récupération du secteur via yfinance (gestion silencieuse des erreurs)
        sector = "N/A"
        try:
            stock_info = yf.Ticker(decision["ticker"]).info
            sector = stock_info.get("sector", "N/A")
        except:
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
            if decision["action"] == "ACHETER":
                st.info(
                    f"💡 Allocation Suggérée: {decision['allocation_pct']}% du capital de trading."
                )
            st.link_button("Consulter l'article original ↗", decision["article_link"])


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
    st.title("⚡ BERZERK - Decision Feed")
    st.caption("Analyse IA. Décisions Immédiates. Suivi de Performance Temps Réel.")

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
    achats_24h = len(
        [
            d
            for d in decisions
            if d["action"] == "ACHETER"
            and datetime.fromisoformat(d["analyzed_at"].replace("Z", "+00:00"))
            > now - timedelta(hours=24)
        ]
    )

    with stat_col1:
        st.metric("Statut Système", "🟢 Opérationnel")

    with stat_col2:
        st.metric("Décisions 24h", decisions_24h)

    with stat_col3:
        st.metric("Signaux ACHAT 24h", achats_24h)

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


if __name__ == "__main__":
    main()
