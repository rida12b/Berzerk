import sqlite3
from datetime import datetime

import feedparser
import requests
import streamlit as st
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

# LangChain Imports
from langchain_google_genai import ChatGoogleGenerativeAI

# NOUVEAU : Import depuis notre module d'agents
from agents import route_to_agents, run_agent_analysis

# --- CONFIGURATION & SETUP ---
load_dotenv()


def init_db():
    """Initialise la base de données SQLite et crée la table articles."""
    conn = sqlite3.connect("berzerk.db")
    cursor = conn.cursor()
    # On crée une table pour stocker les articles.
    # Le lien (link) est UNIQUE pour éviter les doublons.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            link TEXT NOT NULL UNIQUE,
            published_str TEXT,
            published_date DATETIME NOT NULL,
            fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            decision_json TEXT,
            analyzed_at DATETIME
        )
    """
    )

    # Ajouter les nouvelles colonnes si elles n'existent pas (pour les anciennes bases)
    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN status TEXT DEFAULT 'pending'")
    except sqlite3.OperationalError:
        pass  # La colonne existe déjà

    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN decision_json TEXT")
    except sqlite3.OperationalError:
        pass  # La colonne existe déjà

    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN analyzed_at DATETIME")
    except sqlite3.OperationalError:
        pass  # La colonne existe déjà

    conn.commit()
    conn.close()


# Définition de la structure de sortie attendue
class Analysis(BaseModel):
    resume: str = Field(description="Résumé de la news en 3 phrases maximum.")
    impact: int = Field(
        description="Note d'impact de 1 (faible) à 10 (très fort) sur les marchés."
    )
    evaluation: str = Field(
        description="Une chaîne de caractères: 'Positif', 'Négatif' ou 'Neutre'."
    )
    entites: list[str] = Field(
        description="Liste de tickers d'actions (ex: ['AAPL', 'TSLA']), de noms de sociétés et de secteurs concernés."
    )


# Initialisation du modèle LLM via LangChain
try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite-preview-06-17", temperature=0
    )
except Exception as e:
    st.error(
        f"Erreur d'initialisation du modèle LangChain. Vérifiez votre GOOGLE_API_KEY. Erreur: {e}"
    )
    llm = None

# Liste des flux RSS fonctionnels (après notre diagnostic)
RSS_FEEDS = {"Bloomberg": "https://feeds.bloomberg.com/markets/news.rss"}

# --- FONCTIONS CORE ---


def fetch_and_store_news(feeds):
    """Parcourt les flux RSS et insère les nouveaux articles dans la DB."""
    conn = sqlite3.connect("berzerk.db")
    cursor = conn.cursor()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    new_articles_found = 0
    for source, url in feeds.items():
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                for entry in feed.entries:
                    # On récupère la date et on la convertit en objet datetime
                    # feedparser a une structure pratique pour ça dans "published_parsed"
                    published_tuple = entry.get("published_parsed")
                    if published_tuple:
                        dt_object = datetime(*published_tuple[:6])
                    else:
                        dt_object = datetime.now()  # Fallback si pas de date

                    # INSERT OR IGNORE est la clé : il n'insère que si le lien n'existe pas déjà
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO articles (source, title, link, published_str, published_date)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            source,
                            entry.title,
                            entry.link,
                            entry.get("published", "N/A"),
                            dt_object,
                        ),
                    )

                    if cursor.rowcount > 0:
                        new_articles_found += 1

        except Exception as e:
            print(f"Erreur lors de la récupération du flux de {source}: {e}")

    conn.commit()
    conn.close()
    return new_articles_found


def get_articles_from_db():
    """Récupère tous les articles de la DB, triés par date de publication."""
    conn = sqlite3.connect("berzerk.db")
    # On force la connexion à retourner des dictionnaires au lieu de tuples, c'est plus pratique
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM articles ORDER BY published_date DESC")
    articles = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return articles


def get_article_text(url):
    # (Cette fonction ne change pas)
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        paragraphs = soup.find_all("p")
        article_text = " ".join([p.get_text() for p in paragraphs])
        return article_text
    except Exception as e:
        print(f"Erreur de récupération de l'article à l'URL {url}: {e}")
        return None


def analyze_news_with_llm(article_text: str):
    """Analyse un article en utilisant une chaîne LangChain."""
    if not llm or not article_text:
        return None

    parser = JsonOutputParser(pydantic_object=Analysis)
    prompt_template = """Tu es un analyste financier expert pour le système BERSERK. Analyse l'article de presse suivant et extrais les informations clés.
    {format_instructions}
    Voici l'article :
    ---
    {article}
    ---"""
    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["article"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | llm | parser

    try:
        analysis_result = chain.invoke({"article": article_text})
        return analysis_result
    except Exception as e:
        st.error(f"Erreur lors de l'exécution de la chaîne LangChain : {e}")
        return None


# --- INTERFACE UTILISATEUR (STREAMLIT) ---

st.set_page_config(page_title="BERSERK Labo", layout="wide")
st.title("📘 BERSERK - Labo d'Analyse (Phase 2)")
st.caption("Moteur: LangChain + Gemini + Agents IA | Monitoring: LangSmith")

# NOUVEAU : On initialise la DB au démarrage de l'app
init_db()

if "articles" not in st.session_state:
    # Au premier chargement, on remplit la liste depuis la DB
    st.session_state.articles = get_articles_from_db()
if "selected_article_link" not in st.session_state:
    st.session_state.selected_article_link = None
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

# NOUVEAU : Ajouter ces lignes pour gérer l'état des agents
if "agent_team" not in st.session_state:
    st.session_state.agent_team = None
if "agent_analyses" not in st.session_state:
    st.session_state.agent_analyses = None

left_column, right_column = st.columns([1, 2])

with left_column:
    st.header("Flux d'actualités")

    if st.button("🔄 Charger les dernières actualités", use_container_width=True):
        with st.spinner("Recherche de nouveaux articles..."):
            # 1. On cherche et stocke les nouveaux articles
            new_count = fetch_and_store_news(RSS_FEEDS)
            st.toast(f"{new_count} nouvel(s) article(s) trouvé(s) !")
            # 2. On recharge la liste COMPLÈTE et TRIÉE depuis la DB
            st.session_state.articles = get_articles_from_db()
            st.session_state.selected_article_link = None
            st.session_state.analysis_result = None
            # NOUVEAU : Réinitialiser aussi les agents
            st.session_state.agent_team = None
            st.session_state.agent_analyses = None
        st.rerun()

    # On affiche les articles de st.session_state, qui est maintenant toujours trié
    if st.session_state.articles:
        for article in st.session_state.articles:
            with st.container(border=True):
                st.markdown(f"**{article['title']}**")

                # NOUVEAU : On affiche la source et l'heure de publication
                # On reformate l'objet datetime pour un affichage lisible
                pub_date = datetime.fromisoformat(article["published_date"])
                st.caption(
                    f"Source: {article['source']} | Publié le: {pub_date.strftime('%d/%m/%Y à %H:%M')}"
                )

                if st.button("🤖 Analyser", key=article["link"]):
                    st.session_state.selected_article_link = article["link"]
                    st.session_state.analysis_result = None
                    # NOUVEAU : Réinitialiser aussi les agents
                    st.session_state.agent_team = None
                    st.session_state.agent_analyses = None
                    st.rerun()
    else:
        st.info(
            "Aucun article en base. Cliquez sur 'Charger les dernières actualités' pour commencer."
        )

with right_column:
    st.header("🔬 Analyse de l'IA")

    if st.session_state.selected_article_link:
        if st.session_state.analysis_result is None:
            with st.spinner("Analyse en cours (LangChain)..."):
                link = st.session_state.selected_article_link
                text = get_article_text(link)
                if text:
                    st.session_state.analysis_result = analyze_news_with_llm(text)
                else:
                    st.session_state.analysis_result = {"error": "Contenu inaccessible"}
            st.rerun()

        analysis = st.session_state.analysis_result
        if analysis:
            if "error" in analysis:
                st.error(analysis["error"])
            else:
                st.success("Analyse terminée !")

                # MISE EN FORME COMME SUR TON SCREENSHOT
                st.subheader("📝 Résumé")
                st.write(analysis.get("resume", "N/A"))

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Évaluation", analysis.get("evaluation", "N/A"))
                with col2:
                    st.metric("Impact Potentiel", f"{analysis.get('impact', 0)}/10")

                st.subheader("📈 Entités Concernées")
                # st.write(analysis.get('entites', [])) # Moins joli
                st.json(analysis.get("entites", []))  # Plus joli

                st.divider()  # Ajoute une ligne de séparation visuelle

                # --- NOUVELLE SECTION : ORCHESTRATION DES AGENTS ---

                # Si l'équipe n'a pas encore été recrutée, afficher le bouton
                if st.session_state.agent_team is None:
                    if st.button(
                        "👥 Recruter l'Équipe d'Agents Spécialisés",
                        use_container_width=True,
                    ):
                        with st.spinner("Le Chef d'Orchestre recrute l'équipe..."):
                            # On récupère les entités et le résumé de l'analyse initiale
                            entities = analysis.get("entites", [])
                            summary = analysis.get("resume", "")
                            # On appelle notre routeur intelligent
                            st.session_state.agent_team = route_to_agents(
                                entities, summary
                            )
                        st.rerun()

                # Si l'équipe est recrutée, on l'affiche et on lance les analyses
                if st.session_state.agent_team is not None:
                    st.subheader("👥 Équipe d'Agents Recrutée")

                    # Afficher l'équipe
                    for agent in st.session_state.agent_team:
                        st.info(
                            f"**{agent['agent_type'].replace('_', ' ').title()}** recruté avec le focus : *{agent['focus']}*"
                        )

                    # Si les analyses ne sont pas encore faites, afficher le bouton pour les lancer
                    if st.session_state.agent_analyses is None:
                        if st.button(
                            "🚀 Lancer les Analyses de l'Équipe",
                            type="primary",
                            use_container_width=True,
                        ):
                            st.session_state.agent_analyses = []

                            # On récupère le texte complet de l'article UNE SEULE FOIS
                            full_text = get_article_text(
                                st.session_state.selected_article_link
                            )

                            if full_text:
                                # On boucle sur chaque agent recruté pour lancer son analyse
                                with st.spinner(
                                    "Les agents travaillent... Cette opération peut prendre un certain temps."
                                ):
                                    for agent in st.session_state.agent_team:
                                        # On appelle la fonction d'exécution de notre module agents.py
                                        single_analysis = run_agent_analysis(
                                            agent_type=agent["agent_type"],
                                            focus=agent["focus"],
                                            news_summary=analysis.get("resume", ""),
                                            full_article_text=full_text,
                                        )
                                        st.session_state.agent_analyses.append(
                                            {
                                                "agent_type": agent["agent_type"],
                                                "focus": agent["focus"],
                                                "analysis": single_analysis,
                                            }
                                        )
                            else:
                                st.error(
                                    "Impossible de récupérer le texte complet de l'article pour les agents."
                                )
                                st.session_state.agent_analyses = (
                                    []
                                )  # Pour éviter de relancer
                            st.rerun()

                # Si les analyses sont terminées, on les affiche
                if st.session_state.agent_analyses is not None:
                    st.subheader("📝 Debriefing de l'Équipe")
                    for result in st.session_state.agent_analyses:
                        with st.expander(
                            f"**Analyse du {result['agent_type'].replace('_', ' ').title()}** - Focus : *{result['focus']}*"
                        ):
                            st.markdown(result["analysis"])
    else:
        st.info("Cliquez sur 'Analyser' sur une news pour commencer.")
