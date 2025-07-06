"""
Module d'Agents IA Spécialisés pour le Projet BERZERK
====================================================

Ce module contient une équipe d'agents IA spécialisés pour analyser les news financières
sous différents angles. Chaque agent a une expertise unique et apporte sa perspective
à l'analyse globale.

Auteur: BERZERK Team
Phase: 2 - Agents IA Spécialisés
"""

import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# LangChain Imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# Imports pour les outils
from langchain_community.tools.tavily_search import TavilySearchResults
import yfinance as yf

# --- CONFIGURATION & SETUP ---
load_dotenv()

# Initialisation du LLM avec température plus élevée pour la personnalité des agents
try:
    llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite-preview-06-17", 
    temperature=0.3
    # Le paramètre convert_system_message_to_human est maintenant géré automatiquement
)
    print("✅ LLM initialisé avec succès pour les agents IA")
except Exception as e:
    print(f"❌ Erreur d'initialisation du LLM pour les agents: {e}")
    llm = None

# --- OUTILS POUR AGENTS AUGMENTÉS ---

# 1. Outil de recherche web avec Tavily
try:
    web_search_tool = TavilySearchResults(
        max_results=3,  # Limiter pour éviter la surcharge d'informations
        search_depth="basic"  # Recherche basique pour être plus rapide
    )
    print("✅ Outil de recherche web (Tavily) initialisé")
except Exception as e:
    print(f"❌ Erreur d'initialisation de Tavily: {e}")
    web_search_tool = None

# 2. Outil de données financières avec yfinance
@tool
def get_stock_price(ticker: str) -> str:
    """Récupère le prix actuel et la variation journalière pour un ticker donné."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="2d")  # 2 jours pour calculer la variation
        if hist.empty:
            return f"❌ Données non trouvées pour {ticker}"
        
        # Prix actuel (dernière clôture)
        current_price = hist['Close'].iloc[-1]
        
        # Variation par rapport à la veille
        if len(hist) >= 2:
            previous_price = hist['Close'].iloc[-2]
            change_percent = ((current_price - previous_price) / previous_price) * 100
            change_symbol = "📈" if change_percent > 0 else "📉" if change_percent < 0 else "➡️"
            
            return f"💰 {ticker}: {current_price:.2f} USD {change_symbol} {change_percent:+.2f}% vs hier"
        else:
            return f"💰 {ticker}: {current_price:.2f} USD (variation non disponible)"
            
    except Exception as e:
        return f"❌ Erreur lors de la récupération des données pour {ticker}: {str(e)}"

@tool
def get_market_sentiment(ticker: str) -> str:
    """Récupère des informations sur le sentiment du marché pour un ticker."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Informations clés
        market_cap = info.get('marketCap', 'N/A')
        pe_ratio = info.get('trailingPE', 'N/A')
        volume = info.get('averageVolume', 'N/A')
        
        # Formatage des grandes valeurs
        if isinstance(market_cap, (int, float)):
            if market_cap > 1e12:
                market_cap_str = f"{market_cap/1e12:.1f}T USD"
            elif market_cap > 1e9:
                market_cap_str = f"{market_cap/1e9:.1f}B USD"
            else:
                market_cap_str = f"{market_cap/1e6:.1f}M USD"
        else:
            market_cap_str = "N/A"
            
        return f"📊 {ticker} - Cap: {market_cap_str} | P/E: {pe_ratio} | Volume moy: {volume:,}" if isinstance(volume, int) else f"📊 {ticker} - Cap: {market_cap_str} | P/E: {pe_ratio} | Volume moy: {volume}"
        
    except Exception as e:
        return f"❌ Erreur sentiment marché pour {ticker}: {str(e)}"

print("✅ Outils financiers (yfinance) initialisés")

# --- MODÈLES PYDANTIC POUR LA VALIDATION ---

class AgentSelection(BaseModel):
    """Modèle pour la sélection d'agents par le routeur."""
    agents: List[Dict[str, str]] = Field(
        description="Liste des agents sélectionnés avec leur type et focus"
    )

class TickerIdentification(BaseModel):
    """Modèle pour la sortie de l'agent Ticker Hunter."""
    ticker: str = Field(description="Symbole boursier de l'entreprise")
    nom_entreprise: str = Field(description="Nom complet de l'entreprise")
    justification_impact: str = Field(description="Justification de l'impact sur cette entreprise")

class TickerHunterResult(BaseModel):
    """Modèle pour la sortie complète de l'agent Ticker Hunter."""
    tickers_identifies: List[TickerIdentification] = Field(
        description="Liste des tickers identifiés avec leurs justifications"
    )

# --- PROFILS D'AGENTS SPÉCIALISÉS ---

# Ticker Hunter - Agent spécialisé dans l'identification de tickers actionnables
ticker_hunter_template = PromptTemplate(
    input_variables=["news_summary", "full_article_text"],
    template="""
Tu es "The Ticker Hunter", un analyste financier redoutable pour le fonds BERZERK. Ta seule et unique mission est d'identifier des opportunités de trading actionnables à partir d'informations. Tu ignores les concepts vagues et tu te concentres sur les entreprises cotées.

Analyse le résumé et le texte complet de l'article ci-dessous.

**Résumé :**
{news_summary}

**Texte Complet :**
{full_article_text}

---
**TACHE :**
Identifie les 1 à 5 entreprises cotées en bourse (et leurs tickers boursiers) les plus directement et significativement impactées par cette news.
Pour chaque entreprise, fournis une justification concise expliquant POURQUOI elle est impactée.

Réponds IMPÉRATIVEMENT au format JSON suivant, et rien d'autre. Si aucune action n'est clairement identifiable, retourne une liste vide.

{{
    "tickers_identifies": [
        {{
            "ticker": "AAPL",
            "nom_entreprise": "Apple Inc.",
            "justification_impact": "L'article mentionne des problèmes dans la chaîne d'approvisionnement des iPhones en Chine."
        }},
        {{
            "ticker": "QCOM",
            "nom_entreprise": "Qualcomm",
            "justification_impact": "En tant que fournisseur clé d'Apple, Qualcomm serait directement affecté par un ralentissement de la production."
        }}
    ]
}}

**RÈGLES CRITIQUES :**
- Seules les entreprises publiques avec des tickers boursiers réels (NYSE, NASDAQ, etc.)
- Impact direct et mesurable sur le business
- Justification factuelle basée sur le contenu de l'article
- Maximum 5 tickers pour rester focus
- Si aucun ticker n'est clairement identifiable, retourne une liste vide
"""
)

# Analyste Actions - Spécialisé dans l'analyse d'actions individuelles
analyste_actions_template = PromptTemplate(
    input_variables=["focus", "news_summary", "full_article_text"],
    template="""
Tu es un Analyste Financier Senior spécialisé en actions pour le fonds d'investissement BERZERK.

**Ton Focus Exclusif : L'action {focus}.**

Ta mission est d'évaluer l'impact d'une nouvelle sur cette action spécifique. Ignore les autres aspects.
Tu dois analyser avec précision l'impact potentiel sur le cours de l'action, les volumes, et les perspectives.

Résumé de la news :
{news_summary}

Texte complet de l'article :
{full_article_text}

---
Produis une analyse concise au format Markdown avec les sections suivantes :

### 🎯 Évaluation sur {focus}
- **Sentiment :** (Positif, Négatif, Neutre)
- **Impact (1-10) :** (Note l'impact potentiel sur le cours de l'action)
- **Justification :** (Explique ton raisonnement en 2-3 phrases claires, en te basant sur des faits de l'article.)

### 📊 Analyse Technique
- **Catalyseurs identifiés :** (Éléments qui pourraient faire bouger le cours)
- **Risques potentiels :** (Éléments négatifs à surveiller)

### 🎯 Recommandation d'Action
- **Horizon :** (Court Terme, Moyen Terme, Long Terme)
- **Action :** (Surveiller, Renforcer la position, Alléger la position, Ne rien faire)
- **Niveau de confiance :** (Faible, Moyen, Élevé)
"""
)

# Analyste Sectoriel - Spécialisé dans l'analyse de secteurs d'activité
analyste_sectoriel_template = PromptTemplate(
    input_variables=["focus", "news_summary", "full_article_text"],
    template="""
Tu es un Analyste Sectoriel Expert pour le fonds d'investissement BERZERK.

**Ton Focus Exclusif : Le secteur {focus}.**

Ta mission est d'analyser l'impact d'une nouvelle sur l'ensemble du secteur. Tu dois identifier les tendances,
les dynamiques concurrentielles et les implications pour toutes les entreprises du secteur.

Résumé de la news :
{news_summary}

Texte complet de l'article :
{full_article_text}

---
Produis une analyse sectorielle au format Markdown avec les sections suivantes :

### 🏭 Impact Sectoriel sur {focus}
- **Sentiment Global :** (Positif, Négatif, Neutre)
- **Ampleur d'Impact (1-10) :** (Note l'impact sur l'ensemble du secteur)
- **Justification :** (Explique les mécanismes d'impact sur le secteur)

### 🔄 Dynamiques Concurrentielles
- **Gagnants potentiels :** (Quelles entreprises/sous-secteurs pourraient bénéficier)
- **Perdants potentiels :** (Quelles entreprises/sous-secteurs pourraient souffrir)
- **Changements structurels :** (Évolutions durables attendues)

### 🎯 Implications Stratégiques
- **Opportunités d'investissement :** (Nouvelles opportunités créées)
- **Risques sectoriels :** (Nouveaux risques à surveiller)
- **Horizon temporel :** (Court/Moyen/Long terme pour les impacts)
"""
)

# Stratégiste Géopolitique - Spécialisé dans l'analyse géopolitique et macroéconomique
strategiste_geopolitique_template = PromptTemplate(
    input_variables=["focus", "news_summary", "full_article_text"],
    template="""
Tu es un Stratégiste Géopolitique Senior pour le fonds d'investissement BERZERK.

**Ton Focus Exclusif : {focus}.**

Ta mission est d'analyser les implications géopolitiques et macroéconomiques d'une nouvelle.
Tu dois identifier les ramifications sur les relations internationales, les politiques économiques,
et les flux de capitaux mondiaux.

Résumé de la news :
{news_summary}

Texte complet de l'article :
{full_article_text}

---
Produis une analyse géopolitique au format Markdown avec les sections suivantes :

### 🌍 Analyse Géopolitique : {focus}
- **Sentiment Géopolitique :** (Stabilisant, Déstabilisant, Neutre)
- **Niveau de Risque (1-10) :** (Impact sur la stabilité géopolitique)
- **Justification :** (Explique les mécanismes géopolitiques en jeu)

### 🗺️ Implications Régionales
- **Régions affectées :** (Zones géographiques principales concernées)
- **Acteurs clés :** (Pays, institutions, alliances impliqués)
- **Tensions potentielles :** (Nouveaux conflits ou résolutions possibles)

### 💰 Impact sur les Marchés
- **Devises affectées :** (Monnaies qui pourraient être impactées)
- **Secteurs sensibles :** (Industries particulièrement exposées)
- **Flux de capitaux :** (Réallocations d'investissement attendues)

### 🎯 Recommandations Stratégiques
- **Positionnement recommandé :** (Défensif, Offensif, Neutre)
- **Horizon d'impact :** (Court/Moyen/Long terme)
- **Indicateurs à surveiller :** (Signaux d'alerte ou d'opportunité)
"""
)

# Agent Investisseur Final - Le superviseur qui prend la décision finale
investisseur_final_template = PromptTemplate(
    input_variables=["debriefing_equipe", "capital_disponible", "actionable_tickers"],
    template="""
Tu es l'Agent Investisseur en chef du fonds BERZERK. Tu es froid, logique, et uniquement guidé par la performance et la gestion du risque.

Ta mission est de prendre la décision finale d'investissement basée sur le rapport consolidé de ton équipe d'analystes spécialisés.

**Tickers Identifiés par le Ticker Hunter :**
{actionable_tickers}

**Rapport de l'Équipe d'Analystes :**
---
{debriefing_equipe}
---

**Contexte Financier Actuel :**
- Capital total disponible pour de nouveaux trades : {capital_disponible} €

**TACHE FINALE :**
Sur la base EXCLUSIVE des informations ci-dessus, produis une décision d'investissement structurée au format JSON. Ne rien ajouter d'autre.

**PRIORITÉ :** Concentre-toi sur les tickers spécifiques identifiés par le Ticker Hunter. Ignore les analyses macro générales.

Le format JSON doit contenir les clés suivantes :
- "decision": "ACHETER", "VENDRE", "SURVEILLER" ou "IGNORER".
- "ticker": Le ticker de l'action concernée (string, ou null si IGNORER).
- "confiance": "ÉLEVÉE", "MOYENNE", "FAIBLE" (string).
- "justification_synthetique": Une phrase unique et directe expliquant la décision.
- "allocation_capital_pourcentage": Le pourcentage du capital disponible à allouer à ce trade (nombre flottant, de 0.0 à 5.0). Allouer 0 si la décision n'est pas "ACHETER". Une allocation typique pour une confiance MOYENNE est 1%, ÉLEVÉE est 2-3%.
- "points_cles_positifs": Une liste de 2-3 points clés positifs tirés du rapport.
- "points_cles_negatifs_risques": Une liste de 2-3 risques ou points négatifs tirés du rapport.
"""
)

# Dictionnaire des profils d'agents
AGENT_PROFILES = {
    "ticker_hunter": ticker_hunter_template,
    "analyste_actions": analyste_actions_template,
    "analyste_sectoriel": analyste_sectoriel_template,
    "strategiste_geopolitique": strategiste_geopolitique_template,
    "investisseur_final": investisseur_final_template,
}

# --- FONCTIONS PRINCIPALES ---

def route_to_agents(entities: List[str], news_summary: str) -> List[Dict[str, str]]:
    """
    Routeur intelligent qui sélectionne les agents appropriés selon les entités détectées.
    
    Args:
        entities: Liste des entités détectées (tickers, secteurs, concepts)
        news_summary: Résumé de la news
    
    Returns:
        Liste de dictionnaires avec agent_type et focus pour chaque agent sélectionné
    """
    if not llm:
        print("❌ LLM non disponible pour le routage")
        return []
    
    # Prompt pour le routeur intelligent
    router_template = PromptTemplate(
        input_variables=["entities", "news_summary", "available_agents"],
        template="""
Tu es le Chef d'Orchestre du système d'analyse BERZERK. Ta mission est de sélectionner
la meilleure équipe d'agents IA pour analyser une news financière.

**Agents disponibles :**
{available_agents}

**Entités détectées dans la news :**
{entities}

**Résumé de la news :**
{news_summary}

**Instructions :**
1. Analyse les entités et le contenu de la news
2. Sélectionne 1 à 3 agents maximum (évite la redondance)
3. Pour chaque agent, définis un focus précis basé sur les entités

**Critères de sélection :**
- **analyste_actions** : Si des tickers d'actions spécifiques sont mentionnés (ex: AAPL, TSLA)
- **analyste_sectoriel** : Si des secteurs d'activité sont concernés (ex: Tech, Pharma, Énergie)
- **strategiste_geopolitique** : Si des aspects géopolitiques, monétaires ou macroéconomiques sont présents

**Format de réponse attendu (JSON strict) :**
{{
    "agents": [
        {{"agent_type": "analyste_actions", "focus": "AAPL"}},
        {{"agent_type": "analyste_sectoriel", "focus": "Technologie"}},
        {{"agent_type": "strategiste_geopolitique", "focus": "Relations commerciales USA-Chine"}}
    ]
}}

Assure-toi que chaque focus soit spécifique et pertinent pour l'agent sélectionné.
"""
    )
    
    try:
        # Préparation des données
        available_agents = """
- analyste_actions : Analyse d'actions individuelles et de tickers spécifiques
- analyste_sectoriel : Analyse de secteurs d'activité et industries
- strategiste_geopolitique : Analyse géopolitique et macroéconomique
"""
        
        # Configuration du parser JSON
        parser = JsonOutputParser(pydantic_object=AgentSelection)
        
        # Création de la chaîne LangChain
        chain = router_template | llm | parser
        
        # Exécution du routage
        result = chain.invoke({
            "entities": ", ".join(entities),
            "news_summary": news_summary,
            "available_agents": available_agents
        })
        
        selected_agents = result.get("agents", [])
        print(f"✅ Routeur : {len(selected_agents)} agent(s) sélectionné(s)")
        
        return selected_agents
        
    except Exception as e:
        print(f"❌ Erreur dans le routage des agents: {e}")
        # Fallback : sélection basique basée sur les entités
        fallback_agents = []
        
        # Recherche de tickers (généralement en majuscules, 2-5 caractères)
        tickers = [entity for entity in entities if entity.isupper() and 2 <= len(entity) <= 5]
        if tickers:
            fallback_agents.append({"agent_type": "analyste_actions", "focus": tickers[0]})
        
        # Recherche de secteurs (mots-clés courants)
        secteurs = ["tech", "technologie", "énergie", "finance", "santé", "pharma", "automobile"]
        for entity in entities:
            if any(secteur in entity.lower() for secteur in secteurs):
                fallback_agents.append({"agent_type": "analyste_sectoriel", "focus": entity})
                break
        
        return fallback_agents

def run_agent_analysis(
    agent_type: str, 
    focus: str, 
    news_summary: str, 
    full_article_text: str
) -> str:
    """
    Exécute l'analyse d'un agent spécifique.
    
    Args:
        agent_type: Type d'agent (clé du dictionnaire AGENT_PROFILES)
        focus: Focus spécifique pour l'analyse
        news_summary: Résumé de la news
        full_article_text: Texte complet de l'article
    
    Returns:
        Analyse formatée en Markdown ou message d'erreur
    """
    if not llm:
        return "❌ **Erreur :** LLM non disponible pour l'analyse"
    
    if agent_type not in AGENT_PROFILES:
        return f"❌ **Erreur :** Agent '{agent_type}' non reconnu"
    
    try:
        # Récupération du template de l'agent
        agent_prompt = AGENT_PROFILES[agent_type]
        
        # Création de la chaîne LangChain
        chain = agent_prompt | llm
        
        # Exécution de l'analyse
        analysis_result = chain.invoke({
            "focus": focus,
            "news_summary": news_summary,
            "full_article_text": full_article_text
        })
        
        print(f"✅ Analyse terminée - Agent: {agent_type}, Focus: {focus}")
        return analysis_result.content if hasattr(analysis_result, 'content') else str(analysis_result)
        
    except Exception as e:
        error_msg = f"❌ **Erreur lors de l'analyse** - Agent: {agent_type}, Focus: {focus}\n**Détail:** {str(e)}"
        print(error_msg)
        return error_msg

def run_ticker_hunter(news_summary: str, full_article_text: str) -> Dict[str, List[Dict]]:
    """
    Exécute l'agent Ticker Hunter pour identifier les tickers actionnables.
    
    Args:
        news_summary: Résumé de la news
        full_article_text: Texte complet de l'article
    
    Returns:
        Dictionnaire avec la liste des tickers identifiés
    """
    if not llm:
        print("❌ LLM non disponible pour le Ticker Hunter")
        return {"tickers_identifies": []}
    
    try:
        # Configuration du parser JSON avec validation Pydantic
        parser = JsonOutputParser(pydantic_object=TickerHunterResult)
        
        # Récupération du template du Ticker Hunter
        ticker_hunter_prompt = AGENT_PROFILES["ticker_hunter"]
        
        # Création de la chaîne LangChain
        chain = ticker_hunter_prompt | llm | parser
        
        # Exécution de l'analyse
        result = chain.invoke({
            "news_summary": news_summary,
            "full_article_text": full_article_text
        })
        
        tickers_found = result.get("tickers_identifies", [])
        print(f"✅ Ticker Hunter : {len(tickers_found)} ticker(s) identifié(s)")
        
        if tickers_found:
            for ticker_info in tickers_found:
                # Gestion des objets Pydantic ET des dictionnaires
                if hasattr(ticker_info, 'ticker'):
                    ticker = ticker_info.ticker
                    company = ticker_info.nom_entreprise
                else:
                    ticker = ticker_info.get('ticker', 'N/A')
                    company = ticker_info.get('nom_entreprise', 'N/A')
                print(f"   🎯 {ticker} - {company}")
        
        return result
        
    except Exception as e:
        print(f"❌ Erreur dans le Ticker Hunter: {e}")
        return {"tickers_identifies": []}

# --- AGENTS AUGMENTÉS (AVEC OUTILS) ---

def create_augmented_analyst(focus_ticker: str = None) -> AgentExecutor:
    """
    Crée un agent analyste augmenté avec accès à des outils web et financiers.
    
    Args:
        focus_ticker: Ticker à analyser en priorité (optionnel)
    
    Returns:
        AgentExecutor configuré avec les outils
    """
    if not llm:
        raise ValueError("LLM non disponible pour créer l'agent augmenté")
    
    # Définition des outils disponibles
    tools = []
    
    # Ajout des outils disponibles
    if web_search_tool:
        tools.append(web_search_tool)
    
    tools.extend([get_stock_price, get_market_sentiment])
    
    # Prompt système pour l'agent augmenté
    focus_instruction = f" Tu te concentres principalement sur {focus_ticker}." if focus_ticker else ""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""Tu es un analyste financier expert du fonds BERZERK avec accès à des outils temps réel.{focus_instruction}

**Tes outils disponibles :**
- web_search_tool : Recherche d'informations complémentaires sur le web
- get_stock_price : Prix actuel et variation des actions
- get_market_sentiment : Informations sur capitalisation, P/E, volume

**Ton processus d'analyse :**
1. Analyse d'abord la news fournie
2. Utilise tes outils pour vérifier le contexte actuel du marché
3. Recherche des informations complémentaires si nécessaire
4. Produis une analyse complète et nuancée

**Règles importantes :**
- Utilise tes outils de manière stratégique (pas systématiquement)
- Mentionne si le marché a déjà réagi à la news
- Contextualise tes recommandations avec les données temps réel
- Sois précis et actionnable dans tes conclusions"""),
        
        ("user", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    # Création de l'agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    
    # Création de l'exécuteur
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,  # Pour voir le processus de réflexion
        max_iterations=5,  # Limiter les itérations pour éviter les boucles
        early_stopping_method="generate"  # Arrêt anticipé si nécessaire
    )
    
    return agent_executor

def run_augmented_analysis(ticker: str, news_summary: str, full_article_text: str) -> str:
    """
    Exécute une analyse augmentée avec accès aux outils externes.
    
    Args:
        ticker: Ticker à analyser
        news_summary: Résumé de la news
        full_article_text: Texte complet de l'article
    
    Returns:
        Analyse complète avec données temps réel
    """
    try:
        # Création de l'agent augmenté pour ce ticker
        agent_executor = create_augmented_analyst(focus_ticker=ticker)
        
        # Préparation de la requête
        query = f"""
        Analyse l'impact de cette news sur l'action {ticker}.
        
        **Résumé de la news :**
        {news_summary}
        
        **Texte complet :**
        {full_article_text[:2000]}...  # Limitation pour éviter les tokens excessifs
        
        **Ta mission :**
        1. Vérifie le prix actuel et la variation de {ticker}
        2. Recherche des informations complémentaires si nécessaire
        3. Évalue si le marché a déjà intégré cette news
        4. Produis une recommandation d'investissement précise
        
        Utilise tes outils pour avoir une vision complète du contexte actuel !
        """
        
        # Exécution de l'analyse
        result = agent_executor.invoke({"input": query})
        
        return result.get("output", "Erreur dans l'analyse augmentée")
        
    except Exception as e:
        return f"❌ **Erreur dans l'analyse augmentée :** {str(e)}"

# --- FONCTIONS UTILITAIRES ---

def get_available_agents() -> List[str]:
    """Retourne la liste des agents disponibles."""
    return list(AGENT_PROFILES.keys())

def get_agent_description(agent_type: str) -> str:
    """Retourne une description d'un agent spécifique."""
    descriptions = {
        "analyste_actions": "Spécialisé dans l'analyse d'actions individuelles et de tickers spécifiques",
        "analyste_sectoriel": "Expert en analyse de secteurs d'activité et dynamiques industrielles",
        "strategiste_geopolitique": "Spécialisé dans l'analyse géopolitique et macroéconomique"
    }
    return descriptions.get(agent_type, "Agent non reconnu")

# --- FONCTION DE TEST ---

def test_agents_module():
    """Fonction de test pour vérifier le bon fonctionnement du module."""
    print("🧪 Test du module agents.py")
    print("-" * 50)
    
    # Test 1: Vérification des profils
    print(f"✅ {len(AGENT_PROFILES)} profils d'agents chargés")
    for agent_type in AGENT_PROFILES.keys():
        print(f"   - {agent_type}: {get_agent_description(agent_type)}")
    
    # Test 2: Test du routeur
    test_entities = ["AAPL", "TSLA", "Technologie", "Intelligence Artificielle"]
    test_summary = "Apple et Tesla annoncent un partenariat dans l'IA automobile"
    
    print(f"\n🔀 Test du routeur avec entités: {test_entities}")
    selected_agents = route_to_agents(test_entities, test_summary)
    print(f"✅ Agents sélectionnés: {selected_agents}")
    
    print("\n🎯 Module agents.py prêt à l'emploi !")

if __name__ == "__main__":
    test_agents_module() 