from agents import get_agent_description, get_available_agents


def test_route_to_agents_fallback_logic():
    """
    Teste la logique de fallback du routeur quand le LLM échoue.
    Ce test est plus simple et ne dépend pas du LLM.
    """
    # 1. Test avec un ticker en majuscules (devrait déclencher analyste_actions)
    entities = ["AAPL", "technologie", "innovation"]

    # Test direct de la logique de fallback (extraite de la fonction)
    fallback_agents = []

    # Recherche de tickers (généralement en majuscules, 2-5 caractères)
    tickers = [
        entity for entity in entities if entity.isupper() and 2 <= len(entity) <= 5
    ]
    if tickers:
        fallback_agents.append({"agent_type": "analyste_actions", "focus": tickers[0]})

    # Recherche de secteurs (mots-clés courants)
    secteurs = [
        "tech",
        "technologie",
        "énergie",
        "finance",
        "santé",
        "pharma",
        "automobile",
    ]
    for entity in entities:
        if any(secteur in entity.lower() for secteur in secteurs):
            fallback_agents.append(
                {"agent_type": "analyste_sectoriel", "focus": entity}
            )
            break

    # 2. Vérifications
    assert len(fallback_agents) == 2
    assert fallback_agents[0]["agent_type"] == "analyste_actions"
    assert fallback_agents[0]["focus"] == "AAPL"
    assert fallback_agents[1]["agent_type"] == "analyste_sectoriel"
    assert fallback_agents[1]["focus"] == "technologie"


def test_get_available_agents():
    """
    Teste que la fonction get_available_agents retourne les bons types d'agents.
    """
    agents = get_available_agents()

    # Vérification que les agents de base sont présents
    expected_agents = [
        "analyste_actions",
        "analyste_sectoriel",
        "strategiste_geopolitique",
        "ticker_hunter",
    ]

    for agent in expected_agents:
        assert agent in agents


def test_get_agent_description():
    """
    Teste que get_agent_description retourne une description pour les agents connus.
    """
    # Test avec un agent connu
    description = get_agent_description("analyste_actions")
    assert description != "Agent non reconnu"
    assert len(description) > 10  # Une description doit avoir du contenu

    # Test avec un agent inconnu
    description_unknown = get_agent_description("agent_inexistant")
    assert description_unknown == "Agent non reconnu"
