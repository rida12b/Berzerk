# 🚀 Guide de Déploiement BERZERK

## Configuration du Serveur de Production

### 1. Préparation du serveur

#### Générer une paire de clés SSH
```bash
ssh-keygen -t ed25519 -C "berzerk-deploy-key"
```

#### Cloner le projet sur le serveur
```bash
git clone https://github.com/votre-nom/berzerk.git /home/berzerk/app
```

#### Créer l'environnement virtuel
```bash
cd /home/berzerk/app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Créer le fichier .env sur le serveur
```bash
nano /home/berzerk/app/.env
# Ajoutez vos clés :
# GOOGLE_API_KEY=votre_clé_google
# TAVILY_API_KEY=votre_clé_tavily
```

### 2. Configuration du service systemd

#### Copier le fichier de service
```bash
sudo cp deployment/berzerk-monitor.service /etc/systemd/system/
```

#### Activer et démarrer le service
```bash
sudo systemctl daemon-reload
sudo systemctl enable berzerk-monitor.service
sudo systemctl start berzerk-monitor.service
```

#### Vérifier le statut
```bash
sudo systemctl status berzerk-monitor
journalctl -u berzerk-monitor -f
```

### 3. Configuration GitHub

#### Variables (Settings > Secrets and variables > Actions > Variables)
- `GOOGLE_API_KEY`: Votre clé API Google Gemini
- `TAVILY_API_KEY`: Votre clé API Tavily

#### Secrets (Settings > Secrets and variables > Actions > Secrets)
- `PROD_HOST`: Adresse IP ou domaine du serveur
- `PROD_USERNAME`: Nom d'utilisateur SSH (ex: ubuntu, berzerk)
- `PROD_SSH_KEY`: Clé SSH privée pour l'authentification

### 4. Workflow de Déploiement

Le système CI/CD fonctionne ainsi :

1. **Push vers main** → Déclenche le workflow CI
2. **Tests & Linting** → Validation automatique de la qualité
3. **Déploiement** → Si CI réussie, déploiement automatique
4. **Redémarrage services** → Application des changements 