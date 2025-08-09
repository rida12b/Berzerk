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