"""
Orchestrateur Automatisé BERZERK - Phase 2.3
============================================

Ce module contient le pipeline automatisé complet utilisant LangGraph pour orchestrer
l'ensemble de la chaîne d'analyse financière : de la news brute à la décision d'investissement.

Architecture : News → Analyse Initiale → Routage Agents → Analyses Spécialisées → Décision Finale

Auteur: BERZERK Team
Phase: 2.3 - Automatisation Complète
"""

import sys
from datetime import datetime
from typing import Any, TypedDict

import yfinance as yf
from langchain_core.output_parsers import JsonOutputParser

# LangGraph Imports
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from agents import (
    AGENT_PROFILES,
    llm,
    route_to_agents,
    run_agent_analysis,
    run_pure_prediction_analysis,  # NOUVEAU : Agent de prédiction pure
    run_ticker_hunter,
)

# Imports depuis nos modules existants
from berzerk_lab import analyze_news_with_llm, get_article_text

import os

# --- DÉFINITION DE L'ÉTAT DU GRAPHE ---


class GraphState(TypedDict):
    """État qui circule dans le graphe et est mis à jour à chaque étape."""

    news_link: str
    news_summary: str
    full_article_text: str
    initial_analysis: dict[str, Any]
    actionable_tickers: list[dict[str, str]]  # Nouveau : Résultat du Ticker Hunter
    agent_team: list[dict[str, str]]
    agent_debriefing: str
    final_decision: dict[str, Any]
    capital_disponible: float
    execution_log: list[str]
    timestamp: str


# --- MODÈLE PYDANTIC POUR LA DÉCISION FINALE ---


class InvestmentDecision(BaseModel):
    """Modèle pour valider la décision finale d'investissement."""

    decision: str = Field(description="LONG (pari sur la hausse), SHORT (pari sur la baisse), SURVEILLER ou IGNORER")
    ticker: str = Field(description="Ticker de l'action concernée ou null")
    confiance: str = Field(description="ÉLEVÉE, MOYENNE ou FAIBLE")
    horizon: str = Field(description="Court Terme, Moyen Terme, ou Long Terme")
    justification_synthetique: str = Field(description="Justification en une phrase")
    allocation_capital_pourcentage: float = Field(
        description="Pourcentage du capital à allouer (0.0 à 5.0)"
    )
    points_cles_positifs: list[str] = Field(description="Points positifs clés")
    points_cles_negatifs_risques: list[str] = Field(description="Risques identifiés")


# --- FONCTION DE CAPTURE DE PRIX ---


def get_live_price(ticker: str) -> float:
    """Récupère le prix le plus récent disponible pour un ticker avec des fallbacks robustes."""
    ticker = ticker.strip().replace("$", "")
    if not ticker:
        print(f"[WARN] Ticker vide ou invalide pour la capture de prix.")
        return 0.0
    try:
        stock = yf.Ticker(ticker)
        # 1. Tentative Intraday
        print(f"[INFO] Tentative de récupération du prix intraday pour {ticker}...")
        try:
            data = stock.history(period="1d", interval="1m")
            if not data.empty:
                price = float(data["Close"].iloc[-1])
                print(f"[INFO] Prix intraday récupéré pour {ticker}: {price}")
                return price
            else:
                print(f"[WARN] Pas de données intraday pour {ticker}.")
        except Exception as e:
            print(f"[WARN] Échec récupération intraday pour {ticker}: {e}")
        # 2. Tentative via stock.info
        print(f"[INFO] Tentative de récupération du prix via info pour {ticker}...")
        try:
            info = stock.info
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            if price:
                print(f"[INFO] Prix info récupéré pour {ticker}: {price}")
                return float(price)
            else:
                print(f"[WARN] Pas de prix dans info pour {ticker}.")
        except Exception as e:
            print(f"[WARN] Échec récupération info pour {ticker}: {e}")
        # 3. Tentative Historique 5j
        print(f"[INFO] Tentative de récupération du prix historique (5j) pour {ticker}...")
        try:
            hist = stock.history(period="5d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                print(f"[INFO] Prix historique récupéré pour {ticker}: {price}")
                return price
            else:
                print(f"[WARN] Pas de données historiques pour {ticker}.")
        except Exception as e:
            print(f"[WARN] Échec récupération historique pour {ticker}: {e}")
        print(f"[WARN] Impossible de récupérer le prix pour {ticker} après tous les fallbacks.")
        return 0.0
    except Exception as e:
        print(f"[WARN] Exception inattendue lors de la récupération du prix pour {ticker}: {e}")
        return 0.0


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
        "parse_mode": "Markdown"
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


# --- FONCTIONS UTILITAIRES ---


def log_step(state: GraphState, message: str) -> None:
    """Ajoute un log à l'état avec timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    state["execution_log"].append(log_message)
    print(f"🔄 {log_message}")


def format_debriefing(agent_analyses: list[dict[str, str]]) -> str:
    """Formate les analyses des agents pour le superviseur."""
    debriefing_parts = []
    for i, analysis in enumerate(agent_analyses, 1):
        debriefing_parts.append(
            f"\n--- ANALYSE {i} : {analysis['agent_type'].upper().replace('_', ' ')} ---\n"
            f"Focus : {analysis['focus']}\n\n"
            f"{analysis['analysis']}\n"
            f"{'='*80}"
        )
    return "\n".join(debriefing_parts)


# --- NŒUDS DU GRAPHE (chaque nœud est une fonction) ---


def node_initial_analysis(state: GraphState) -> GraphState:
    """Nœud 1 : Récupère le texte de l'article et fait l'analyse initiale."""
    log_step(state, "DÉMARRAGE - Analyse Initiale")

    try:
        # Récupération du texte complet
        full_text = get_article_text(state["news_link"])
        if not full_text:
            raise ValueError("Impossible de récupérer le texte de l'article")

        # Analyse initiale avec LLM
        analysis = analyze_news_with_llm(full_text)
        if not analysis:
            raise ValueError("Échec de l'analyse initiale")

        # Mise à jour de l'état
        state["full_article_text"] = full_text
        state["initial_analysis"] = analysis
        state["news_summary"] = analysis.get("resume", "")

        log_step(
            state,
            f"✅ Analyse initiale terminée - Impact: {analysis.get('impact', 'N/A')}/10",
        )
        log_step(
            state, f"✅ Entités détectées: {', '.join(analysis.get('entites', []))}"
        )

    except Exception as e:
        log_step(state, f"❌ ERREUR dans l'analyse initiale: {str(e)}")
        state["initial_analysis"] = {"error": str(e)}

    return state


def node_find_actionable_tickers(state: GraphState) -> GraphState:
    """Nœud 2 : Chasse aux Tickers - Identifie les tickers actionnables."""
    log_step(state, "TICKER HUNTER - Identification des tickers actionnables")

    try:
        if "error" in state["initial_analysis"]:
            raise ValueError(
                "Analyse initiale échouée, impossible d'identifier les tickers"
            )

        # Exécution du Ticker Hunter
        ticker_result = run_ticker_hunter(
            news_summary=state["news_summary"],
            full_article_text=state["full_article_text"],
        )

        raw_tickers = ticker_result.get("tickers_identifies", [])
        
        if not raw_tickers:
            log_step(state, "⚠️  Aucun ticker actionnable identifié par l'IA.")
            state["actionable_tickers"] = []
            return state

        log_step(state, f"🔬 {len(raw_tickers)} ticker(s) brut(s) identifié(s). Validation en cours...")
        
        validated_tickers = []
        for ticker_info in raw_tickers:
            # Gestion des Pydantic/dict
            ticker_symbol = ticker_info.ticker if hasattr(ticker_info, 'ticker') else ticker_info.get("ticker", "")
            
            # 1. Nettoyage (déjà fait dans agents.py mais redondance sécuritaire)
            clean_ticker = ticker_symbol.strip().replace("$", "")

            # 2. Vérification de viabilité avec yfinance (L'AJOUT CRUCIAL)
            try:
                stock = yf.Ticker(clean_ticker)
                # On fait un appel très léger juste pour voir si le ticker existe
                info = stock.info
                if not info or info.get('regularMarketPrice') is None and info.get('currentPrice') is None:
                    raise ValueError("Ticker non trouvé ou sans données de prix.")
                
                log_step(state, f"✅ Ticker '{clean_ticker}' validé avec yfinance.")
                
                # Mettre à jour le ticker nettoyé dans l'objet
                if hasattr(ticker_info, 'ticker'):
                    ticker_info.ticker = clean_ticker
                else:
                    ticker_info['ticker'] = clean_ticker

                validated_tickers.append(ticker_info)

            except Exception as e:
                log_step(state, f"❌ Ticker '{clean_ticker}' REJETÉ après validation yfinance. Raison: {e}")

        state["actionable_tickers"] = validated_tickers
        log_step(state, f"🎯 {len(validated_tickers)} ticker(s) final(aux) après validation.")

    except Exception as e:
        log_step(state, f"❌ ERREUR dans le Ticker Hunter: {str(e)}")
        state["actionable_tickers"] = []

    return state


def node_route_to_agents(state: GraphState) -> GraphState:
    """Nœud 3 : Recrute l'équipe d'agents basée sur les tickers identifiés."""
    log_step(state, "ROUTAGE - Recrutement de l'équipe d'agents (basé sur tickers)")

    try:
        if "error" in state["initial_analysis"]:
            raise ValueError("Analyse initiale échouée, impossible de router")

        actionable_tickers = state.get("actionable_tickers", [])

        if actionable_tickers:
            # Mode PRÉCIS : Tickers identifiés → Agents ciblés
            team = []

            # Pour chaque ticker, on crée un analyste d'actions dédié
            for ticker_info in actionable_tickers:
                # Gestion des objets Pydantic ET des dictionnaires
                if hasattr(ticker_info, "ticker"):
                    ticker = ticker_info.ticker
                    company = ticker_info.nom_entreprise
                else:
                    ticker = ticker_info.get("ticker", "")
                    company = ticker_info.get("nom_entreprise", "")

                team.append(
                    {"agent_type": "analyste_actions", "focus": f"{ticker} ({company})"}
                )

            # Ajout d'un analyste sectoriel si multiple tickers
            if len(actionable_tickers) > 1:
                sectors = []
                for ticker_info in actionable_tickers:
                    # Gestion des objets Pydantic ET des dictionnaires
                    if hasattr(ticker_info, "justification_impact"):
                        justification = ticker_info.justification_impact
                    else:
                        justification = ticker_info.get("justification_impact", "")
                    # Extraction de mots-clés sectoriels basiques
                    if any(
                        word in justification.lower()
                        for word in [
                            "tech",
                            "technologie",
                            "intelligence artificielle",
                            "ia",
                        ]
                    ):
                        sectors.append("Technologie")
                    elif any(
                        word in justification.lower()
                        for word in ["auto", "véhicule", "transport"]
                    ):
                        sectors.append("Automobile")
                    elif any(
                        word in justification.lower()
                        for word in ["énergie", "pétrole", "gaz"]
                    ):
                        sectors.append("Énergie")
                    elif any(
                        word in justification.lower()
                        for word in ["finance", "banque", "crédit"]
                    ):
                        sectors.append("Finance")

                if sectors:
                    unique_sectors = list(set(sectors))
                    team.append(
                        {
                            "agent_type": "analyste_sectoriel",
                            "focus": f"Impact sectoriel sur {', '.join(unique_sectors)}",
                        }
                    )

            log_step(
                state,
                f"🎯 Mode PRÉCIS activé - {len(actionable_tickers)} ticker(s) ciblé(s)",
            )

        else:
            # Mode FALLBACK : Analyse macro classique
            team = [
                {
                    "agent_type": "strategiste_geopolitique",
                    "focus": "Analyse macroéconomique générale de la situation"
                }
            ]
            log_step(state, "⚠️ Aucun ticker actionnable, fallback sur agent macro.")

        state["agent_team"] = team

        # --- DÉBUT DE LA MODIFICATION ---
        # Filet de sécurité : Si, pour une raison quelconque, aucun agent n'est
        # recruté en mode fallback, on assigne un stratège géopolitique par défaut.
        if not team:
            log_step(state, "⚠️ Aucun agent recruté. Assignation d'un agent par défaut pour éviter l'échec.")
            state["agent_team"] = [
                {
                    "agent_type": "strategiste_geopolitique",
                    "focus": "Analyse macroéconomique générale de la situation"
                }
            ]
        # --- FIN DE LA MODIFICATION ---

        log_step(state, f"✅ Équipe recrutée: {len(state['agent_team'])} agent(s)")
        for agent in team:
            log_step(state, f"   - {agent['agent_type']} → Focus: {agent['focus']}")

    except Exception as e:
        log_step(state, f"❌ ERREUR dans le routage des agents: {str(e)}")
        state["agent_team"] = []

    return state


def node_run_agent_analyses(state: GraphState) -> GraphState:
    """Nœud 4 : Exécute les analyses de chaque agent spécialisé (mode PURE PREDICTION)."""
    log_step(
        state, "EXÉCUTION - Analyses spécialisées PURE PREDICTION (mode 'tac au tac')"
    )

    try:
        if not state["agent_team"]:
            raise ValueError("Aucun agent disponible pour l'analyse")

        agent_analyses = []
        actionable_tickers = state.get("actionable_tickers", [])

        for i, agent in enumerate(state["agent_team"], 1):
            log_step(
                state,
                f"Exécution agent {i}/{len(state['agent_team'])}: {agent['agent_type']}",
            )

            # Détecter si c'est un agent d'analyse d'actions avec ticker identifié
            is_ticker_analysis = (
                agent["agent_type"] == "analyste_actions"
                and actionable_tickers
                and len(actionable_tickers) > 0
            )

            if is_ticker_analysis:
                # Extraire le ticker du focus (format: "AAPL (Apple Inc.)")
                focus_text = agent["focus"]
                ticker = None

                # Chercher le ticker dans les actionable_tickers
                for ticker_info in actionable_tickers:
                    # Gestion des objets Pydantic ET des dictionnaires
                    if hasattr(ticker_info, "ticker"):
                        ticker_value = ticker_info.ticker
                    else:
                        ticker_value = ticker_info.get("ticker", "")

                    if ticker_value in focus_text:
                        ticker = ticker_value
                        break

                if ticker:
                    log_step(
                        state,
                        f"🚀 Analyse PURE PREDICTION pour {ticker} (mode 'tac au tac')",
                    )

                    # === MODIFICATION CLÉ ICI ===
                    # Utiliser l'agent de pure prédiction sans données de prix
                    analysis = run_pure_prediction_analysis(
                        ticker=ticker,
                        news_summary=state["news_summary"],
                        full_article_text=state["full_article_text"],
                    )

                    agent_analyses.append(
                        {
                            "agent_type": agent["agent_type"]
                            + "_pure_prediction",  # Marquer le mode
                            "focus": agent["focus"],
                            "analysis": analysis,
                            "ticker": ticker,
                            "is_augmented": False,  # Il n'est plus "augmenté" avec des données de prix
                        }
                    )

                    log_step(
                        state, f"✅ Analyse PURE PREDICTION terminée pour {ticker}"
                    )
                else:
                    # Fallback vers l'analyse classique
                    log_step(
                        state,
                        f"⚠️ Ticker non trouvé, analyse classique pour {focus_text}",
                    )
                    analysis = run_agent_analysis(
                        agent_type=agent["agent_type"],
                        focus=agent["focus"],
                        news_summary=state["news_summary"],
                        full_article_text=state["full_article_text"],
                    )

                    agent_analyses.append(
                        {
                            "agent_type": agent["agent_type"],
                            "focus": agent["focus"],
                            "analysis": analysis,
                            "is_augmented": False,
                        }
                    )

                    log_step(
                        state, f"✅ Analyse classique terminée: {agent['agent_type']}"
                    )
            else:
                # Agent classique (sectoriel, géopolitique, etc.)
                log_step(state, f"📊 Analyse classique pour {agent['agent_type']}")

                analysis = run_agent_analysis(
                    agent_type=agent["agent_type"],
                    focus=agent["focus"],
                    news_summary=state["news_summary"],
                    full_article_text=state["full_article_text"],
                )

                agent_analyses.append(
                    {
                        "agent_type": agent["agent_type"],
                        "focus": agent["focus"],
                        "analysis": analysis,
                        "is_augmented": False,
                    }
                )

                log_step(state, f"✅ Analyse classique terminée: {agent['agent_type']}")

        # Formatage du debriefing pour le superviseur
        state["agent_debriefing"] = format_debriefing(agent_analyses)

        # Compter les analyses pure prediction
        pure_prediction_count = sum(
            1 for a in agent_analyses if "pure_prediction" in a.get("agent_type", "")
        )
        log_step(
            state,
            f"✅ Debriefing consolidé - {len(agent_analyses)} analyses ({pure_prediction_count} pure prediction)",
        )

    except Exception as e:
        log_step(state, f"❌ ERREUR dans les analyses d'agents: {str(e)}")
        state["agent_debriefing"] = f"ERREUR: {str(e)}"

    return state


def node_final_investor_decision(state: GraphState) -> GraphState:
    """Nœud 5 : Prend la décision finale d'investissement via l'Agent Superviseur."""
    log_step(state, "DÉCISION - Agent Investisseur Final")

    try:
        if not state["agent_debriefing"] or "ERREUR" in state["agent_debriefing"]:
            raise ValueError("Debriefing invalide, impossible de prendre une décision")

        # Configuration du parser JSON
        parser = JsonOutputParser(pydantic_object=InvestmentDecision)

        # Récupération du template de l'investisseur final
        investor_prompt = AGENT_PROFILES["investisseur_final"]

        # Formatage des tickers pour l'investisseur final
        actionable_tickers = state.get("actionable_tickers", [])
        tickers_summary = "Aucun ticker spécifique identifié"

        if actionable_tickers:
            tickers_list = []
            for ticker_info in actionable_tickers:
                # Gestion des objets Pydantic ET des dictionnaires
                if hasattr(ticker_info, "ticker"):
                    # Objet Pydantic
                    ticker = ticker_info.ticker
                    company = ticker_info.nom_entreprise
                    justification = ticker_info.justification_impact
                else:
                    # Dictionnaire classique (fallback)
                    ticker = ticker_info.get("ticker", "N/A")
                    company = ticker_info.get("nom_entreprise", "N/A")
                    justification = ticker_info.get("justification_impact", "N/A")

                tickers_list.append(f"• {ticker} ({company}): {justification}")
            tickers_summary = "\n".join(tickers_list)

        # Création de la chaîne LangChain
        chain = investor_prompt | llm | parser

        # Exécution de la décision
        decision_result = chain.invoke(
            {
                "debriefing_equipe": state["agent_debriefing"],
                "capital_disponible": state["capital_disponible"],
                "actionable_tickers": tickers_summary,
            }
        )

        # --- DÉBUT DE LA CORRECTION ---
        decision_obj = None
        if isinstance(decision_result, list):
            if decision_result:
                # Si le LLM retourne une liste, on prend le premier élément
                log_step(
                    state, "⚠️  Le LLM a retourné une liste, prise du premier élément."
                )
                decision_obj = decision_result[0]
            else:
                raise ValueError("Le LLM a retourné une liste vide.")
        else:
            # Comportement normal (objet Pydantic ou dict)
            decision_obj = decision_result

        # Maintenant, on s'assure que decision_obj est un dictionnaire
        if hasattr(decision_obj, "decision"):
            # C'est un objet Pydantic, convertir en dict
            decision_dict = {
                "decision": decision_obj.decision,
                "ticker": decision_obj.ticker,
                "confiance": decision_obj.confiance,
                "justification_synthetique": decision_obj.justification_synthetique,
                "allocation_capital_pourcentage": decision_obj.allocation_capital_pourcentage,
                "points_cles_positifs": decision_obj.points_cles_positifs,
                "points_cles_negatifs_risques": decision_obj.points_cles_negatifs_risques,
            }
        else:
            # C'est déjà un dictionnaire
            decision_dict = decision_obj
        # --- FIN DE LA CORRECTION ---

        # --- NOUVEAU : CAPTURE DU PRIX AU MOMENT DE LA DÉCISION ---
        decision_ticker = decision_dict.get("ticker")
        prix_au_moment_decision = 0.0
        if decision_ticker:
            log_step(state, f"💰 Capture du prix live pour {decision_ticker}...")
            prix_au_moment_decision = get_live_price(decision_ticker)
            if prix_au_moment_decision > 0:
                log_step(state, f"✅ Prix capturé : {prix_au_moment_decision:.2f} USD")
            else:
                log_step(state, f"⚠️  Impossible de capturer le prix pour {decision_ticker}")

        # NOUVEAU : On ajoute le prix "gravé" à la décision
        decision_dict["prix_a_la_decision"] = prix_au_moment_decision
        # --- FIN DE LA CAPTURE DE PRIX ---

        # --- DÉBUT DE LA CORRECTION LOGIQUE ---
        # Si la décision est LONG mais que l'allocation est nulle,
        # la confiance est insuffisante. On ramène la décision à SURVEILLER.
        if (
            decision_dict.get("decision") == "LONG"
            and decision_dict.get("allocation_capital_pourcentage", 0.0) == 0.0
        ):

            log_step(
                state,
                "⚠️  INCOHÉRENCE DÉTECTÉE: LONG avec 0% d'allocation. Décision rétrogradée à SURVEILLER.",
            )

            # Rétrograder la décision
            decision_dict["decision"] = "SURVEILLER"
            decision_dict["confiance"] = "FAIBLE"  # Forcer la confiance à FAIBLE
            decision_dict["justification_synthetique"] = (
                f"[Rétrogradé] Signal LONG détecté mais confiance insuffisante pour une allocation de capital. {decision_dict.get('justification_synthetique', '')}"
            )
        # --- FIN DE LA CORRECTION LOGIQUE ---

        state["final_decision"] = decision_dict

        # Logs détaillés de la décision
        log_step(state, f"✅ DÉCISION PRISE: {decision_dict.get('decision', 'N/A')}")
        log_step(state, f"   🎯 Ticker: {decision_dict.get('ticker', 'N/A')}")
        log_step(state, f"   📊 Confiance: {decision_dict.get('confiance', 'N/A')}")
        log_step(
            state,
            f"   💰 Allocation: {decision_dict.get('allocation_capital_pourcentage', 0)}%",
        )
        log_step(
            state,
            f"   📝 Justification: {decision_dict.get('justification_synthetique', 'N/A')}",
        )

    except Exception as e:
        log_step(state, f"❌ ERREUR dans la décision finale: {str(e)}")
        state["final_decision"] = {
            "decision": "ERREUR",
            "ticker": None,
            "confiance": "AUCUNE",
            "justification_synthetique": f"Erreur système: {str(e)}",
            "allocation_capital_pourcentage": 0.0,
            "points_cles_positifs": [],
            "points_cles_negatifs_risques": ["Erreur système"],
        }

    return state


# --- CONSTRUCTION DU GRAPHE LANGGRAPH ---


def create_workflow() -> StateGraph:
    """Crée et configure le graphe d'orchestration avec le nouveau Ticker Hunter."""

    workflow = StateGraph(GraphState)

    # Ajout des nœuds (dans l'ordre d'exécution)
    workflow.add_node("initial_analysis", node_initial_analysis)
    workflow.add_node(
        "find_actionable_tickers", node_find_actionable_tickers
    )  # NOUVEAU
    workflow.add_node("route_to_agents", node_route_to_agents)
    workflow.add_node("run_agent_analyses", node_run_agent_analyses)
    workflow.add_node("final_investor_decision", node_final_investor_decision)

    # Définition des transitions (nouveau flux avec Ticker Hunter)
    workflow.set_entry_point("initial_analysis")
    workflow.add_edge("initial_analysis", "find_actionable_tickers")  # 1 → 2
    workflow.add_edge("find_actionable_tickers", "route_to_agents")  # 2 → 3
    workflow.add_edge("route_to_agents", "run_agent_analyses")  # 3 → 4
    workflow.add_edge("run_agent_analyses", "final_investor_decision")  # 4 → 5
    workflow.add_edge("final_investor_decision", END)  # 5 → FIN

    return workflow


# --- FONCTION PRINCIPALE D'ORCHESTRATION ---


def run_berzerk_pipeline(
    news_link: str, capital_disponible: float = 30000.0
) -> dict[str, Any]:
    """
    Exécute le pipeline complet d'analyse BERZERK.

    Args:
        news_link: URL de l'article à analyser
        capital_disponible: Capital disponible pour l'investissement

    Returns:
        État final avec la décision d'investissement
    """

    print("\n" + "=" * 80)
    print("🚀 DÉMARRAGE DU PIPELINE AUTOMATISÉ BERZERK")
    print("=" * 80)

    # État initial
    initial_state = GraphState(
        news_link=news_link,
        news_summary="",
        full_article_text="",
        initial_analysis={},
        actionable_tickers=[],  # NOUVEAU : Pour stocker les tickers identifiés
        agent_team=[],
        agent_debriefing="",
        final_decision={},
        capital_disponible=capital_disponible,
        execution_log=[],
        timestamp=datetime.now().isoformat(),
    )

    # Création et compilation du graphe
    workflow = create_workflow()
    app = workflow.compile()

    # Exécution du pipeline
    try:
        final_state = app.invoke(initial_state)

        print("\n" + "=" * 80)
        print("🎯 PIPELINE TERMINÉ - RÉSULTATS FINAUX")
        print("=" * 80)

        return final_state

    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE DANS LE PIPELINE: {str(e)}")
        return {
            "error": str(e),
            "execution_log": initial_state.get("execution_log", []),
            "final_decision": {
                "decision": "ERREUR_CRITIQUE",
                "justification_synthetique": f"Pipeline interrompu: {str(e)}",
            },
        }


# --- FONCTION D'AFFICHAGE DES RÉSULTATS ---


def display_final_results(final_state: dict[str, Any]) -> None:
    """Affiche les résultats finaux de manière formatée."""

    # Affichage des tickers identifiés
    actionable_tickers = final_state.get("actionable_tickers", [])
    if actionable_tickers:
        print("\n🎯 TICKERS IDENTIFIÉS PAR LE TICKER HUNTER:")
        for ticker_info in actionable_tickers:
            # Gestion des objets Pydantic ET des dictionnaires
            if hasattr(ticker_info, "ticker"):
                ticker = ticker_info.ticker
                company = ticker_info.nom_entreprise
                justification = ticker_info.justification_impact
            else:
                ticker = ticker_info.get("ticker", "N/A")
                company = ticker_info.get("nom_entreprise", "N/A")
                justification = ticker_info.get("justification_impact", "N/A")
            print(f"   🏢 {ticker} ({company})")
            print(f"      📝 {justification}")
    else:
        print("\n⚠️ AUCUN TICKER ACTIONNABLE IDENTIFIÉ")

    decision = final_state.get("final_decision", {})

    print("\n📊 DÉCISION FINALE BERZERK:")
    print(f"   🎯 Action: {decision.get('decision', 'N/A')}")
    print(f"   📈 Ticker: {decision.get('ticker', 'N/A')}")
    print(f"   🔒 Confiance: {decision.get('confiance', 'N/A')}")
    print(f"   💰 Allocation: {decision.get('allocation_capital_pourcentage', 0)}%")
    print(f"   📝 Justification: {decision.get('justification_synthetique', 'N/A')}")

    positifs = decision.get("points_cles_positifs", [])
    if positifs:
        print("\n✅ Points Positifs:")
        for point in positifs:
            print(f"   • {point}")

    risques = decision.get("points_cles_negatifs_risques", [])
    if risques:
        print("\n⚠️ Risques Identifiés:")
        for risque in risques:
            print(f"   • {risque}")

    print("\n📋 Logs d'exécution:")
    for log in final_state.get("execution_log", []):
        print(f"   {log}")


# --- TESTS ET EXÉCUTION PRINCIPALE ---


def test_pipeline():
    """Fonction de test avec des exemples d'articles."""

    print("🧪 MODE TEST - Sélection automatique d'un article récent")

    # Pour le test, on peut utiliser un URL simple ou une simulation
    test_url = "https://finance.yahoo.com/news/"  # URL générique pour test

    return run_berzerk_pipeline(news_link=test_url, capital_disponible=25000.0)


if __name__ == "__main__":
    """Point d'entrée principal."""

    # Vérification des arguments de ligne de commande
    if len(sys.argv) > 1:
        news_url = sys.argv[1]
        capital = float(sys.argv[2]) if len(sys.argv) > 2 else 30000.0

        print(f"📰 Analyse de: {news_url}")
        print(f"💰 Capital disponible: {capital}€")

        final_state = run_berzerk_pipeline(news_url, capital)
        display_final_results(final_state)

    else:
        print("🧪 MODE DEMO - Exécution du pipeline de test")
        final_state = test_pipeline()
        display_final_results(final_state)

        print("\n💡 Usage: python orchestrator.py <URL_NEWS> [CAPITAL]")
        print(
            "   Exemple: python orchestrator.py 'https://finance.yahoo.com/news/apple-ai-news' 25000"
        )
