# Suivi Projet BERZERK

## 1. Description Générale
Objectif : Orchestration automatisée de décisions d'investissement IA avec traçabilité et suivi de performance. Capture robuste du prix à la décision, stockage, et affichage comparatif dans le dashboard.

## 2. Plan de Tâches
- [x] Fonction robuste de capture de prix en temps réel (`get_live_price`) avec fallback multi-niveaux et logs WARN.
- [x] Intégration de la capture du prix exact dans `node_final_investor_decision` (orchestrator.py).
- [x] Ajout de la clé `prix_a_la_decision` dans la structure de décision.
- [x] Lecture et affichage du prix à la décision dans le dashboard (`berzerk_dashboard.py`).
- [x] Affichage conditionnel de la performance et gestion des cas N/A.

## 3. Journal des Modifications
- 2024-05-07 : Ajout de `get_live_price` robuste (fallback intraday, info, historique, gestion exceptions).
- 2024-05-07 : Enrichissement de la décision avec le prix capturé dans `node_final_investor_decision`.
- 2024-05-07 : Lecture de la clé `prix_a_la_decision` dans `load_decisions_from_db` et affichage dans `display_decision_card` et `display_active_portfolio`.
- 2024-05-07 : Affichage conditionnel et aide utilisateur pour les cas où le prix n'est pas disponible.

## 4. Suivi des Erreurs
- Si le prix n'est pas capturé (0.0), affichage WARN dans la console et "N/A" dans le dashboard avec explication.
- Robustesse assurée par gestion d'exceptions à chaque étape de récupération de prix.

## 5. Résultats des Tests
- Test manuel sur tickers valides et invalides : prix capturé ou fallback, logs WARN visibles.
- Dashboard affiche correctement prix à la décision, prix actuel, performance ou "N/A".

## 6. Documentation Consultée
- [yfinance - Doc officielle](https://github.com/ranaroussi/yfinance)
- [Streamlit st.metric](https://docs.streamlit.io/library/api-reference/data/st.metric)

## 7. Structure du Projet (extrait)
- orchestrator.py : logique de décision, capture prix
- berzerk_dashboard.py : affichage, calculs de performance
- suivi_projet.md : documentation centrale

## 8. Réflexions & Décisions
- Approche multi-fallback pour la robustesse de la capture de prix.
- Ajout systématique de logs pour la traçabilité.
- Affichage UX-friendly pour les cas d'indisponibilité de prix.
- Compatibilité ascendante assurée (clé absente = 0.0, affichage N/A). 