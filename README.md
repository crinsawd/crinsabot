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


