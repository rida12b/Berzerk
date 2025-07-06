import feedparser
import requests

# Définition des flux RSS à tester
RSS_FEEDS = {
    "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss"
}

print("--- Lancement du diagnostic des flux RSS ---")

# On boucle sur chaque flux pour le tester individuellement
for source, url in RSS_FEEDS.items():
    print(f"\n[TEST] Source : {source}")
    print(f"       URL    : {url}")
    
    try:
        # On simule un navigateur en ajoutant un User-Agent
        # C'est la correction la plus probable
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # On télécharge d'abord le contenu avec requests, qui permet de passer les headers
        response = requests.get(url, headers=headers, timeout=10)
        
        # On vérifie le code de statut HTTP. 200 = OK. 403 = Interdit. 404 = Non trouvé.
        print(f"       Statut HTTP : {response.status_code}")

        if response.status_code == 200:
            # Si la requête a réussi, on donne le contenu à feedparser
            feed = feedparser.parse(response.content)
            
            # On vérifie si feedparser a bien trouvé des articles
            if feed.entries:
                print(f"       ✅ SUCCÈS : {len(feed.entries)} article(s) trouvé(s).")
            elif feed.bozo:
                # feed.bozo = 1 signifie que le flux est mal formé
                print(f"       ⚠️ AVERTISSEMENT : Le flux est mal formé. Erreur : {feed.bozo_exception}")
            else:
                print("       ⚠️ AVERTISSEMENT : Le flux est valide mais ne contient aucun article.")
        else:
            print(f"       ❌ ÉCHEC : Le serveur a refusé la connexion (Code {response.status_code}). Le flux est probablement protégé ou mort.")

    except Exception as e:
        print(f"       ❌ ERREUR : Impossible de se connecter au flux. Erreur : {e}")

print("\n--- Diagnostic terminé ---")