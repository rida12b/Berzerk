<prompt_cursor><objectif>Créer une table 'news_events' pour servir de file d'attente entre les services.</objectif><fichiers_en_contexte>
    diagnostic_db.py
  </fichiers_en_contexte><tache>
    - Dans le fichier `diagnostic_db.py`, modifie la fonction `create_trades_table` pour qu'elle s'appelle `setup_database` et qu'elle crée DEUX tables si elles n'existent pas.
    - La première table est la table `trades` existante.
    - Ajoute la création d'une deuxième table nommée `news_events`.
    - La table `news_events` doit contenir les colonnes suivantes :
        - `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
        - `ticker` (TEXT NOT NULL)
        - `news_title` (TEXT NOT NULL)
        - `news_link` (TEXT NOT NULL)
        - `detected_at` (DATETIME NOT NULL)
        - `is_processed` (BOOLEAN NOT NULL DEFAULT 0)
    - Assure-toi que la fonction `setup_database` est appelée au début de la fonction `diagnostic_db()`.
  </tache></prompt_cursor>


  <prompt_cursor><objectif>Modifier le moniteur de news pour qu'il publie des événements dans la nouvelle table 'news_events'.</objectif><fichiers_en_contexte>
    real_time_rss_monitor.py
    agents.py
  </fichiers_en_contexte><tache>
    - Ouvre `real_time_rss_monitor.py`.
    - Crée une nouvelle fonction `identify_tickers_in_text(text: str) -> list[str]`. Pour l'instant, cette fonction peut utiliser une simple expression régulière pour trouver des mots en majuscules de 2 à 5 caractères (ex: `re.findall(r'\b[A-Z]{2,5}\b', text)`).
    - Crée une autre fonction `publish_news_event(ticker: str, article: dict)`. Cette fonction se connectera à `berzerk.db` et insérera une nouvelle ligne dans la table `news_events` avec le ticker, le titre de l'article, le lien, la date de détection, et `is_processed` à 0.
    - Dans la fonction `check_feed_optimized`, après avoir identifié `new_articles`, boucle sur chaque `article`.
    - Pour chaque `article`, appelle `identify_tickers_in_text` sur son titre et son résumé.
    - Pour chaque `ticker` trouvé dans l'article, appelle `publish_news_event(ticker, article)`.
  </tache></prompt_cursor>


  <prompt_cursor><objectif>Implémenter la logique "Event-Driven" dans le gestionnaire de positions.</objectif><fichiers_en_contexte>
    position_manager.py
  </fichiers_en_contexte><tache>
    - Dans `position_manager.py`, crée une nouvelle fonction `get_unprocessed_news_for_ticker(ticker: str) -> list[dict]`.
    - Cette fonction doit se connecter à `berzerk.db` et exécuter deux requêtes :
        1.  Un `SELECT id, news_title, news_link FROM news_events WHERE ticker = ? AND is_processed = 0`.
        2.  Si des nouvelles sont trouvées, un `UPDATE news_events SET is_processed = 1 WHERE id IN (...)` en utilisant les IDs récupérés pour les marquer comme traitées.
    - La fonction doit retourner la liste des dictionnaires de news trouvées.
    - Modifie la `main_loop` :
        - Après les vérifications de Take-Profit et Stop-Loss, appelle `get_unprocessed_news_for_ticker` pour le ticker du trade en cours.
        - Si la fonction retourne une liste de news non vide, déclenche l'appel à l'agent `run_exit_strategist`.
        - Tu devras passer un résumé de ces nouvelles à l'agent. Formate la liste des titres de news en une seule chaîne de caractères.
    - Ajuste la pause à la fin de la `main_loop` à 60 secondes pour une réactivité accrue.
  </tache></prompt_cursor>


  <prompt_cursor><objectif>Adapter l'agent "Exit Strategist" pour qu'il analyse les nouvelles informations fournies.</objectif><fichiers_en_contexte>
    agents.py
    position_manager.py
  </fichiers_en_contexte><tache>
    - Ouvre le fichier `agents.py`.
    - Localise le `PromptTemplate` nommé `exit_strategist_template`.
    - Modifie la liste `input_variables` pour y inclure `new_information_summary`.
    - Réécris le `template` pour qu'il contienne une nouvelle section `**NOUVELLE(S) INFORMATION(S) DÉTECTÉE(S) :**` où la variable `{new_information_summary}` sera injectée.
    - La mission de l'agent dans le prompt doit être explicitement de réévaluer la thèse initiale **à la lumière de ces nouvelles informations**.
    - Modifie la signature de la fonction `run_exit_strategist` pour qu'elle accepte un argument supplémentaire `new_relevant_news: str`.
    - À l'intérieur de `run_exit_strategist`, passe cette nouvelle variable lors de l'appel `.invoke()` sur la chaîne de l'agent.
    - Finalement, retourne dans `position_manager.py` et assure-toi que l'appel à `run_exit_strategist` correspond à la nouvelle signature.
  </tache></prompt_cursor>