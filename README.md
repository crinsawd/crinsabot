<div align="center">

# 🤖 CrinsaBot

**Le bot Discord tout-en-un : modération, niveaux, tickets, giveaways, logs, automod et plus encore.**

Un seul fichier. Zéro dépendance superflue. Configuration 100 % interactive.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.4+-5865F2?logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
[![SQLite](https://img.shields.io/badge/SQLite-aiosqlite-003B57?logo=sqlite&logoColor=white)](https://aiosqlite.omnilib.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#-licence)

</div>

---

## 📖 Sommaire

- [Présentation](#-présentation)
- [Fonctionnalités](#-fonctionnalités)
- [Aperçu des commandes](#-aperçu-des-commandes)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Déploiement](#-déploiement)
- [Architecture](#-architecture)
- [FAQ](#-faq)
- [Contribuer](#-contribuer)
- [Licence](#-licence)

---

## 🎯 Présentation

**CrinsaBot** est un bot Discord **complet, autonome et open-source**, écrit en **Python 3.12** avec [`discord.py 2.x`](https://discordpy.readthedocs.io/). Il tient dans **un seul fichier** (`crinsa.py`) et couvre l'ensemble des besoins d'un serveur Discord moderne :

- 🛡️ Modération puissante
- ⚙️ Panneau de configuration interactif
- 📈 Système de niveaux avec récompenses
- 🎫 Tickets de support avec panneau personnalisable
- 🎁 Giveaways avec tirage automatique
- 📜 Logs d'audit complets
- 🤖 Auto-modération intelligente
- 👋 Accueil / départ / autorole
- 🔊 Vocal temporaire

> 💡 **Philosophie :** un seul fichier, une configuration par panneau, des performances optimales (cache RAM + SQLite WAL).

---

## ✨ Fonctionnalités

### 🛡️ Modération
| Commande | Description |
|---|---|
| `ban`, `unban`, `tempban`, `softban`, `massban` | Bannissements complets |
| `kick` | Expulsion |
| `mute`, `unmute` | Timeout Discord natif |
| `warn`, `warnings`, `unwarn`, `clearwarns` | Avertissements persistants |
| `purge` / `clear` | Suppression en masse avec filtres (bots, images, liens) |
| `nuke`, `slowmode`, `lock`/`unlock`, `hide`/`unhide` | Gestion des salons |
| `role add\|remove\|all\|info`, `temprole`, `rename` | Gestion des rôles |

### ⚙️ Configuration interactive
Un panneau complet (`.config`) avec **9 modules** : Général, Arrivées/Départs, Logs, Auto-mod, Niveaux, Tickets, Giveaways, Vocal temporaire.
- Sélecteurs de salons et rôles
- Modales pour les textes longs
- Toggles pour les options
- Aperçu en direct, réinitialisation par module

### 📈 Niveaux
- XP par message avec cooldown anti-spam
- Courbe paramétrable : `5·L² + 50·L + 100`
- Récompenses automatiques (rôle à un niveau donné)
- `rank`, `leaderboard`, `setxp`, `resetxp`, `reward`

### 🎫 Tickets
- Panneau public personnalisable (texte, image, description)
- Salons privés avec permissions staff
- `add`, `remove`, `rename`, `claim`, `close`
- Logs d'archives et suppression automatique

### 🎁 Giveaways
- `.gwstart <durée> <gagnants> <prix>`
- Bouton **Participer** (toggle)
- Tirage automatique toutes les 15 s
- `gwend`, `gwreroll`, `gwlist`

### 📜 Logs d'audit
Journalisation par catégorie : messages, membres, rôles, salons, vocal, sanctions.

### 🤖 Auto-modération
Filtres : invitations Discord, liens externes, majuscules, spam, mentions massives, mots interdits.
Immunité automatique des modérateurs.

### 👋 Accueil & départ
Messages personnalisables avec variables `{user}`, `{mention}`, `{guild}`, `{count}`.
Autorole distinct pour humains et bots.

### 🔊 Vocal temporaire
Rejoindre un salon hub crée automatiquement un vocal perso (supprimé quand vide).

### 🎉 Fun & utilitaires
`8ball`, `dice`, `coinflip`, `choose`, `rps`, `ship`, `hug`, `slap`, `pat`, `joke`, `slots`, `trivia`,
`ping`, `uptime`, `userinfo`, `serverinfo`, `avatar`, `banner`, `membercount`, `roles`, `channelinfo`, `emoji`, `steal`,
`snipe`, `editsnipe`, `poll`, `remind`, `afk`, `calc`, `invite`, **tags personnalisés**.

---

## 📋 Aperçu des commandes

🛡️ Modération
.ban .unban .tempban .softban .massban .kick
.mute .unmute .warn .warnings .unwarn .clearwarns
.purge .nuke .slowmode .lock .unlock .hide .unhide
.role .temprole .rename

⚙️ Configuration
.config .prefix .resetconfig

📈 Niveaux
.rank .leaderboard .setxp .resetxp .reward

🎫 Tickets
.ticket panel .ticket setup .ticket add .ticket close

🎁 Giveaways
.gwstart .gwend .gwreroll .gwlist

🔧 Utilitaires
.ping .uptime .userinfo .serverinfo .avatar
.snipe .editsnipe .poll .remind .afk .calc .invite .tag

🎉 Fun
.8ball .dice .coinflip .choose .rps .ship
.hug .slap .pat .joke .slots .trivia


> ℹ️ Toutes les commandes principales sont **hybrides** : utilisables avec le préfixe **ou** en slash command.
> Utilise `.help` pour l'aide interactive (menu déroulant + boutons).

---

## 🚀 Installation

### Prérequis

- **Python 3.12+**
- Un **token de bot Discord** ([portail développeur](https://discord.com/developers/applications))

### 1. Cloner le dépôt

```bash
git clone https://github.com/TON_PSEUDO/crinsabot.git
cd crinsabot
2. Installer les dépendances
pip install -r requirements.txt
Ou manuellement :
pip install "discord.py>=2.4.0" "aiosqlite>=0.20.0" "aiohttp>=3.9.5"
3. Configurer le bot
Ouvre crinsa.py et remplis les constantes en haut du fichier :
TOKEN = "TON_TOKEN_ICI"
PREFIX = "."
OWNER_IDS = [123456789012345678]   # ton ID Discord
DEV_GUILD = 0                       # ID de ton serveur de test (optionnel)
Ou crée un fichier .env à la racine (recommandé) :
DISCORD_TOKEN=TON_TOKEN_ICI
PREFIX=.
OWNER_IDS=123456789012345678
4. Activer les intents Discord
Sur discord.com/developers/applications → Bot → Privileged Gateway Intents, active :

✅ SERVER MEMBERS

✅ MESSAGE CONTENT
python crinsa.py
Le bot apparaît en ligne et affiche dans la console :Le bot apparaît en ligne et affiche dans la console :
[HH:MM:SS] INFO     base ouverte (data/crinsabot.db)
[HH:MM:SS] INFO     connecté : CrinsaBot#1234 — X serveurs
⚙️ Configuration
Une fois le bot en ligne sur ton serveur, ouvre le panneau :
.config
Tu accèdes à une interface interactive permettant de configurer tout le bot sans redémarrer.
Les réglages sont sauvegardés en SQLite (cache RAM + flush toutes les 30 s).
🐳 Déploiement
Docker
Un Dockerfile est fourni :

dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "crinsa.py"]
Build et lancement :

bash
docker build -t crinsabot .
docker run -d --name crinsabot \
  -e DISCORD_TOKEN=TON_TOKEN \
  -v $(pwd)/data:/app/data \
  crinsabot
Fly.io
Un fly.toml est fourni pour un déploiement en région cdg (Paris) :

bash
fly auth login
fly launch --no-deploy
fly secrets set DISCORD_TOKEN=TON_TOKEN
fly deploy
⚠️ Important : le volume data/ doit être persistant. Sur Fly.io, ajoute un volume attaché au chemin /app/data.

VPS / systemd
Exemple de service systemd (/etc/systemd/system/crinsabot.service) :

ini
[Unit]
Description=CrinsaBot Discord
After=network.target

[Service]
Type=simple
User=discord
WorkingDirectory=/opt/crinsabot
ExecStart=/usr/bin/python3 /opt/crinsabot/crinsa.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
bash
sudo systemctl enable --now crinsabot
🏗️ Architecture
text
crinsa.py
├── Configuration (token, préfixe, owners)
├── Style (Palette, helpers d'embeds)
├── Outils (durées, permissions, Paginator)
├── Base de données (Database + Settings avec cache)
├── Cogs :
│   ├── Help       → aide interactive
│   ├── Config     → panneau de configuration
│   ├── Moderation → sanctions & gestion salons
│   ├── Utility    → outils du quotidien
│   ├── Fun        → mini-jeux
│   ├── Levels     → XP & classement
│   ├── Logs       → audit
│   ├── Events     → accueil, automod, vocal temp
│   ├── Tickets    → support
│   ├── Giveaways  → concours
│   ├── Info       → stats & maintenance
│   └── Owner      → gestion des accès
└── VeniceBot (AutoShardedBot)
Points techniques clés :

⚡ Settings : lecture instantanée en RAM, écriture différée en SQLite (flush toutes les 30 s)

🧠 Gestion d'erreurs globale avec suggestions (difflib) pour les fautes de frappe

🔒 Vues persistantes (timeout=None) pour tickets et giveaways → fonctionnent après redémarrage

🌐 Présence rotative (3 activités en boucle)

🔄 AutoSharding activé

❓ FAQ
Le bot ne répond pas aux commandes préfixées ?
→ Vérifie que l'intent MESSAGE CONTENT est activé dans le portail développeur.

Les slash commands n'apparaissent pas ?
→ Utilise .sync (réservé au propriétaire). Pour un test rapide, renseigne DEV_GUILD dans la config.

Les données sont-elles persistantes ?
→ Oui, dans data/crinsabot.db (SQLite). Sauvegarde ce fichier régulièrement.

Comment ajouter un autre owner ?
→ .owner add @membre puis .ownerlist pour vérifier.

Le bot redémarre tout seul ?
→ Vérifie le gestionnaire de processus (systemd, Docker restart=always, Fly.io). Le bot ne s'arrête qu'avec Ctrl+C ou .shutdown.

🤝 Contribuer
Les contributions sont les bienvenues !

Fork le projet

Crée ta branche : git checkout -b feature/ma-fonctionnalite

Commit : git commit -m "Ajout de ma fonctionnalité"

Push : git push origin feature/ma-fonctionnalite

Ouvre une Pull Request

Idées d'amélioration :

Internationalisation complète (fr / en)

Persistance en base des récompenses de niveaux

Tests unitaires (parse_duration, Settings, Database)

Dashboard web

📄 Licence
Distribué sous licence MIT. Voir LICENSE pour plus d'informations.

<div align="center">
⭐ Si ce projet te plaît, n'hésite pas à laisser une étoile !

Fait avec ❤️ et beaucoup de ☕

</div> ```
✅ Ce que tu dois encore faire avant de publier
Créer le fichier LICENSE à la racine (MIT standard) — je peux te le fournir si tu veux.

Remplacer TON_PSEUDO dans l'URL de clonage par ton nom GitHub.

Vérifier ton Dockerfile : il pointe actuellement vers venicebot.py → doit être crinsa.py.

Ajouter un .gitignore — voici le minimum recommandé :

gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# Bot
.env
data/
*.db
*.db-shm
*.db-wal

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db







