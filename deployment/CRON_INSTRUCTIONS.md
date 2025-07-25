# ⚙️ Configuration du Rapport de Portefeuille Périodique

Ce guide explique comment configurer une tâche planifiée (`cron job`) sur votre VPS pour recevoir un résumé de votre portefeuille BERZERK toutes les 6 heures sur Telegram.

## 1. Se Connecter au VPS

Connectez-vous à votre VPS avec votre utilisateur habituel (celui qui a les droits `sudo`).

## 2. Ouvrir l'Éditeur Crontab

Nous allons éditer les tâches planifiées pour l'utilisateur `berzerk` afin que le script s'exécute dans le bon environnement.

```bash
sudo crontab -u berzerk -e
```

Si c'est la première fois, il vous demandera de choisir un éditeur. Choisissez `nano` (généralement l'option 1), c'est le plus simple.

## 3. Ajouter la Tâche Planifiée

Allez tout à la fin du fichier et ajoutez la ligne suivante. Copiez-la exactement.

```
0 */6 * * * /home/berzerk/app/venv/bin/python /home/berzerk/app/send_portfolio_update.py
```

### Explication de la commande :

- `0 */6 * * *` : C'est la planification. Elle signifie "Exécute à la minute 0, toutes les 6 heures, tous les jours". Le script tournera donc à 00:00, 06:00, 12:00, et 18:00.
- `/home/berzerk/app/venv/bin/python` : C'est le chemin **absolu** vers l'interpréteur Python de votre environnement virtuel. C'est crucial pour que le script utilise les bonnes dépendances.
- `/home/berzerk/app/send_portfolio_update.py` : C'est le chemin **absolu** vers le script que nous voulons exécuter.

## 4. Sauvegarder et Quitter

- Appuyez sur `Ctrl+X`.
- Appuyez sur `Y` pour confirmer la sauvegarde.
- Appuyez sur `Entrée` pour valider le nom du fichier.

Vous devriez voir un message comme `crontab: installing new crontab`.

C'est tout ! Votre rapporteur de portefeuille est maintenant configuré et s'exécutera automatiquement. 