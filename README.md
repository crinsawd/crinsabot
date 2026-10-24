CrinsaBot est un bot Discord complet, autonome et open-source, écrit en Python 3.12 avec discord.py 2.x. Il tient dans un seul fichier (crinsa.py) et couvre l'ensemble des besoins d'un serveur Discord moderne : modération, configuration interactive, niveaux, tickets, giveaways, logs, automod, accueil, vocal temporaire, etc.

⚙️ Préfixe configurable (par défaut .)

🧩 Commandes hybrides (préfixe et slash commands)

💾 Base SQLite (aiosqlite) avec cache en RAM pour des performances optimales

🎨 Interface entièrement en embeds avec une palette cohérente

🐳 Déployable en Docker / Fly.io

🎯 Philosophie du projet
Principe	Application
Tout-en-un	Un seul fichier, aucune dépendance à des cogs externes
Zéro friction	Installation en 3 commandes, configuration par panneau interactif
Rapide	Lecture des settings en RAM, écriture différée (flush toutes les 30 s)
Robuste	Gestion centralisée des erreurs (permissions, cooldowns, arguments…)
Modulaire	12 cogs indépendants, rechargement à chaud possible
🛠️ Fonctionnalités détaillées
🛡️ 1. Modération complète
ban, unban, tempban, softban, massban

kick, mute / timeout, unmute

warn, warnings, unwarn, clearwarns (avec historique en base)

purge / clear avec filtres (membre, bots, images, liens) — jusqu'à 500 messages

nuke, slowmode, lock / unlock, hide / unhide

Gestion des rôles : role add|remove|all|info, temprole, rename

MP automatique au membre sanctionné (activable)

Journal de modération dédié

⚙️ 2. Configuration interactive (le point fort)
Un panneau Discord complet (.config) avec :

9 modules : Général, Arrivées/Départs, Logs, Auto-mod, Niveaux, Tickets, Giveaways, Vocal temp

Sélecteurs de salons / rôles, modales pour les textes, toggles pour les options

Aperçu en direct, réinitialisation par module, verrouillage sur l'auteur

.prefix et .resetconfig en complément

📈 3. Système de niveaux
XP par message avec cooldown anti-spam configurable

Courbe d'XP paramétrable (5·L² + 50·L + 100)

Annonces de level-up personnalisables

Récompenses automatiques : rôle attribué à un niveau donné (.reward)

rank, leaderboard, setxp, resetxp

🎫 4. Tickets de support
Panneau public avec bouton d'ouverture (personnalisable : texte, image, description)

Création d'un salon privé avec permissions staff + auteur

Contrôles : add, remove, rename, claim, close

Logs d'archives et suppression automatique après fermeture

Un seul ticket ouvert par utilisateur (anti-abus)

🎁 5. Giveaways
Lancement via .gwstart <durée> <gagnants> <prix>

Bouton Participer (toggle : on peut se retirer)

Tirage automatique (boucle de vérification toutes les 15 s)

gwend, gwreroll, gwlist

Résultats affichés dans le message d'origine + annonce des gagnants

📜 6. Logs d'audit
Journalisation fine dans un salon dédié, activable par catégorie :

Messages (édition/suppression)

Membres (arrivée, départ, pseudo, rôles)

Rôles et salons (création/suppression)

Vocal (connexions, déplacements)

Sanctions

🤖 7. Auto-modération
Filtres invitations Discord, liens externes, majuscules, spam (5 msg/5 s), mentions massives (>5), mots interdits (liste personnalisable)

Immunité automatique des modérateurs

Message d'avertissement temporaire auto-supprimé

👋 8. Arrivées / départs / autorole
Messages d'accueil et de départ personnalisables avec variables {user}, {mention}, {guild}, {count}

Style embed ou texte brut

Autorole distinct pour humains et bots

🔊 9. Vocal temporaire
Rejoindre un salon hub crée automatiquement un vocal perso

Suppression automatique quand vide

🎉 10. Fun & utilitaires
Fun : 8ball, dice, coinflip, choose, rps, ship, hug, slap, pat, reverse, mock, joke, slots, trivia

Utilitaires : ping, uptime, userinfo, serverinfo, avatar, banner, servericon, membercount, roles, channelinfo, emoji, steal

snipe / editsnipe, poll, remind, afk, calc, invite

Système de tags personnalisés (.tag create/delete/<nom>)

Pagination intégrée (Paginator) pour les longues listes

👑 11. Commandes propriétaire
owner add|remove|ownerlist (owners stockés en base)

sync, reload, eval, shutdown

🏗️ Architecture technique
text
crinsa.py
├── Configuration (token, préfixe, owners)
├── Style (Palette, embeds helpers)
├── Outils (durées, permissions, Paginator)
├── Base de données (Database + Settings avec cache)
├── Cogs :
│   ├── Help       → aide interactive (menu déroulant + boutons)
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
Points techniques notables :

Settings : lecture instantanée en RAM, écriture différée en SQLite (flush toutes les 30 s)

Gestion d'erreurs globale dans on_command_error avec suggestions (difflib) pour les fautes de frappe

Vues persistantes (timeout=None) pour tickets et giveaways → fonctionnent après redémarrage

Présence rotative (3 activités en boucle)

AutoSharding activé

🐳 Déploiement
Installation locale
bash
pip install discord.py aiosqlite aiohttp
# renseigner TOKEN dans crinsa.py (ou fichier .env)
python crinsa.py
Docker
dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "crinsa.py"]   # ⚠️ à corriger : le CMD pointe vers venicebot.py
Fly.io
Un fly.toml est déjà prêt (région cdg, 1 Go RAM, 1 machine toujours active).

⚠️ Deux incohérences à corriger avant déploiement :

Le Dockerfile.txt lance venicebot.py → doit être crinsa.py

Le fly.toml utilise paketobuildpacks/builder:base alors qu'un Dockerfile existe → préférer [build] dockerfile = "Dockerfile"

✅ Points forts
🚀 Rapidité : cache RAM + SQLite WAL

🧠 UX soignée : embeds cohérents, panneaux interactifs, aide navigable

🔒 Sécurité : vérification hiérarchie des rôles, permissions bot vérifiées avant exécution

♻️ Maintenable : un seul fichier, cogs séparés, rechargement à chaud

🌍 Prêt pour le public : préfixe par serveur, langue configurable (fr/en)

🔮 Pistes d'amélioration
Internationalisation complète (actuellement locale est déclaré mais peu utilisé)

Persistance des récompenses de niveaux (actuellement en RAM → perdues au redémarrage)

Ajout d'un README.md + licence

Tests unitaires sur parse_duration, Settings, Database

Migration vers un stockage JSON → SQLite des rewards

📝 Slogan proposé
CrinsaBot — Le bot Discord qui fait tout, sans que tu aies à installer dix autres bots.

Souhaites-tu que je te prépare :

un README.md propre prêt à publier sur GitHub,

un post de présentation formaté pour un serveur Discord (avec emojis, sections),

la correction du Dockerfile + fly.toml pour un déploiement fonctionnel ?

