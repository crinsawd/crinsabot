"""
CrinsaBot — bot Discord complet, préfixe ".", en un seul fichier.

INSTALLATION
  1. pip install discord.py aiosqlite python-dotenv
  2. colle ton token dans la ligne TOKEN ci-dessous (ou dans un fichier .env)
  3. python crinsa.py

INTENTS À ACTIVER sur https://discord.com/developers/applications
  → Bot → Privileged Gateway Intents : SERVER MEMBERS + MESSAGE CONTENT
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import platform
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Literal, Optional

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks

# ══════════════════════════════════════════════════════════════
#  1. CONFIGURATION — modifie uniquement cette section
# ══════════════════════════════════════════════════════════════

TOKEN = "ENTRE TON TOKEN"                       # ← colle ton token ici, ou laisse vide et utilise .env
PREFIX = "METS LE PREFIX QUE TU VEUX"                     # préfixe des commandes
BOT_NAME = "crinsabot"
OWNER_IDS: list[int] = [METS CE QUE TU VEUX ]        # ex. [123456789012345678] (ton ID, clic droit → copier l'ID)
DEV_GUILD = 0                    # ID d'un serveur pour synchroniser les slash instantanément (0 = global)
DB_PATH = "data/crinsabot.db"

BASE_DIR = Path(__file__).resolve().parent

# .env optionnel (priorité au fichier, puis à la variable TOKEN du haut)
env_file = BASE_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

TOKEN = TOKEN or os.getenv("DISCORD_TOKEN", "")
PREFIX = os.getenv("PREFIX", PREFIX)
BOT_NAME = os.getenv("BOT_NAME", BOT_NAME)
if os.getenv("OWNER_IDS"):
    OWNER_IDS = [int(x) for x in os.getenv("OWNER_IDS").replace(" ", "").split(",") if x.isdigit()]

logging.basicConfig(
    level=logging.INFO,
    format="\033[90m%(asctime)s\033[0m \033[36m%(levelname)-8s\033[0m %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("crinsabot")

# ══════════════════════════════════════════════════════════════
#  2. STYLE — palette et fabriques d'embeds
# ══════════════════════════════════════════════════════════════


class Palette:
    PRIMARY = 0x7B68EE
    ACCENT = 0x00D4FF
    SUCCESS = 0x2ECC71
    WARNING = 0xF1C40F
    DANGER = 0xE74C3C
    NEUTRAL = 0x2F3136
    FOG = 0x99AAB5


DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


def embed(*, title=None, description=None, color=Palette.PRIMARY, footer=None,
          thumbnail=None, image=None, timestamp=True) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color,
                      timestamp=datetime.now(timezone.utc) if timestamp else None)
    if footer:
        e.set_footer(text=footer)
    if thumbnail:
        e.set_thumbnail(url=thumbnail)
    if image:
        e.set_image(url=image)
    return e


def ok(description: str, *, title: str = "Succès") -> discord.Embed:
    return embed(title=f"✅ {title}", description=description, color=Palette.SUCCESS, footer=BOT_NAME)


def err(description: str, *, title: str = "Erreur") -> discord.Embed:
    return embed(title=f"⛔ {title}", description=description, color=Palette.DANGER, footer=BOT_NAME)


def warn(description: str, *, title: str = "Attention") -> discord.Embed:
    return embed(title=f"⚠️ {title}", description=description, color=Palette.WARNING, footer=BOT_NAME)


def info(description: str, *, title: Optional[str] = None) -> discord.Embed:
    return embed(title=title, description=description, color=Palette.PRIMARY, footer=BOT_NAME)


# ══════════════════════════════════════════════════════════════
#  3. OUTILS — durées, permissions, pagination
# ══════════════════════════════════════════════════════════════

_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "mo": 2_592_000, "y": 31_536_000}
_DUR_RE = re.compile(r"(\d+)\s*(mo|[smhdwy])", re.IGNORECASE)


def parse_duration(raw: str) -> Optional[int]:
    raw = raw.strip().lower().replace(" ", "")
    if raw.isdigit():
        return int(raw)
    total = sum(int(v) * _UNITS[u] for v, u in _DUR_RE.findall(raw))
    return total or None


def humanize(seconds: int) -> str:
    parts = []
    for unit, size in (("j", 86400), ("h", 3600), ("min", 60), ("s", 1)):
        if seconds >= size:
            qty, seconds = divmod(seconds, size)
            parts.append(f"{qty}{unit}")
    return " ".join(parts[:3]) or "0s"


class Duration(commands.Converter):
    async def convert(self, ctx, argument: str) -> int:
        seconds = parse_duration(argument)
        if seconds is None:
            raise commands.BadArgument(f"durée invalide : `{argument}` (ex. `10m`, `1h30m`, `7d`)")
        return seconds


def mod_only():
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            return True
        if ctx.author.id in (ctx.bot.owner_ids or set()) or ctx.author.guild_permissions.administrator:
            return True
        p = ctx.channel.permissions_for(ctx.author)
        return any((p.manage_messages, p.kick_members, p.ban_members, p.manage_roles))
    return commands.check(predicate)


class Paginator(discord.ui.View):
    def __init__(self, pages: list[discord.Embed], author: discord.abc.User, timeout: float = 180) -> None:
        super().__init__(timeout=timeout)
        self.pages, self.author, self.index = pages, author, 0
        self._sync()

    def _sync(self) -> None:
        self.first.disabled = self.prev.disabled = self.index == 0
        self.last.disabled = self.next.disabled = self.index == len(self.pages) - 1
        for page in self.pages:
            page.set_footer(text=f"Page {self.index + 1}/{len(self.pages)}")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author.id

    async def _show(self, i: discord.Interaction) -> None:
        self._sync()
        await i.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="⏮", style=discord.ButtonStyle.secondary)
    async def first(self, i: discord.Interaction, _):
        self.index = 0
        await self._show(i)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def prev(self, i: discord.Interaction, _):
        self.index -= 1
        await self._show(i)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next(self, i: discord.Interaction, _):
        self.index += 1
        await self._show(i)

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary)
    async def last(self, i: discord.Interaction, _):
        self.index = len(self.pages) - 1
        await self._show(i)

    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close(self, i: discord.Interaction, _):
        await i.message.delete()

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True


def build_pages(lines: list[str], per_page: int, title: str, color: int = Palette.PRIMARY) -> list[discord.Embed]:
    chunks = [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [["*vide*"]]
    return [discord.Embed(title=title, description="\n".join(c), color=color) for c in chunks]


# ══════════════════════════════════════════════════════════════
#  4. BASE DE DONNÉES
# ══════════════════════════════════════════════════════════════

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
CREATE TABLE IF NOT EXISTS guild_settings (guild_id INTEGER PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS members (
    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 0, messages INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id));
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    mod_id INTEGER NOT NULL, reason TEXT, created INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_warn ON warnings (guild_id, user_id);
CREATE TABLE IF NOT EXISTS tags (
    guild_id INTEGER NOT NULL, name TEXT NOT NULL, content TEXT NOT NULL,
    author INTEGER NOT NULL, uses INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (guild_id, name));
CREATE TABLE IF NOT EXISTS giveaways (
    message_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL, guild_id INTEGER NOT NULL,
    prize TEXT NOT NULL, winners INTEGER NOT NULL, host INTEGER NOT NULL,
    ends_at INTEGER NOT NULL, ended INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS gw_entries (message_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    PRIMARY KEY (message_id, user_id));
CREATE TABLE IF NOT EXISTS tickets (
    channel_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, author_id INTEGER NOT NULL,
    claimed_by INTEGER, opened_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS bot_owners (user_id INTEGER PRIMARY KEY);
"""

DEFAULT_SETTINGS: dict[str, Any] = {
    "prefix": PREFIX, "locale": "fr", "color": Palette.PRIMARY, "dm_on_action": 1,
    "welcome_enabled": 0, "welcome_channel": None,
    "welcome_message": "Bienvenue {user} sur **{guild}** ! Tu es le {count}e membre.",
    "welcome_embed": 1,
    "goodbye_enabled": 0, "goodbye_channel": None,
    "goodbye_message": "**{user}** vient de quitter le serveur…",
    "autorole_enabled": 0, "autorole_id": None, "botrole_id": None,
    "logs_enabled": 0, "logs_channel": None, "logs_messages": 1, "logs_members": 1,
    "logs_roles": 1, "logs_channels": 1, "logs_voice": 1, "logs_mod": 1,
    "automod_enabled": 0, "automod_invites": 1, "automod_links": 0, "automod_caps": 1,
    "automod_spam": 1, "automod_mentions": 1, "automod_badwords": "",
    "mod_log_channel": None, "mute_role": None,
    "levels_enabled": 0, "levels_channel": None, "levels_xp_min": 15, "levels_xp_max": 25,
    "levels_cooldown": 60, "levels_message": "🎉 {user} passe au niveau **{level}** !",
    "tickets_enabled": 0, "tickets_category": None, "tickets_logs": None, "tickets_staff": None,
    "tickets_panel_message": "Clique sur le bouton ci-dessous pour ouvrir un ticket.",
    "tickets_panel_image": None,
    "tickets_panel_description": "Besoin d'aide ? Clique sur le bouton 🎫 ci-dessous pour ouvrir un ticket privé avec l'équipe de modération.",
    "giveaways_enabled": 0, "giveaways_channel": None,
    "starboard_enabled": 0, "starboard_channel": None, "starboard_threshold": 3,
    "tempvoice_enabled": 0, "tempvoice_hub": None,
}


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        log.info("base ouverte (%s)", self.path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.commit()
            await self._conn.close()
            self._conn = None

    async def execute(self, query: str, params: Iterable[Any] = ()) -> None:
        async with self._lock:
            await self._conn.execute(query, tuple(params))

    async def executemany(self, query: str, seq) -> None:
        async with self._lock:
            await self._conn.executemany(query, [tuple(p) for p in seq])

    async def commit(self) -> None:
        async with self._lock:
            await self._conn.commit()

    async def fetchone(self, query: str, params: Iterable[Any] = ()):
        async with self._conn.execute(query, tuple(params)) as cur:
            return await cur.fetchone()

    async def fetchall(self, query: str, params: Iterable[Any] = ()):
        async with self._conn.execute(query, tuple(params)) as cur:
            return await cur.fetchall()


class Settings:
    """Lecture instantanée en RAM, écriture différée en base."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._cache: dict[int, dict[str, Any]] = {}
        self._dirty: set[int] = set()

    async def load_all(self) -> None:
        for row in await self.db.fetchall("SELECT guild_id, data FROM guild_settings"):
            self._cache[row["guild_id"]] = {**DEFAULT_SETTINGS, **json.loads(row["data"])}

    def peek(self, guild_id: Optional[int]) -> dict[str, Any]:
        if guild_id is None:
            return DEFAULT_SETTINGS
        return self._cache.get(guild_id) or DEFAULT_SETTINGS

    async def get(self, guild_id: int) -> dict[str, Any]:
        if guild_id not in self._cache:
            row = await self.db.fetchone("SELECT data FROM guild_settings WHERE guild_id = ?", (guild_id,))
            self._cache[guild_id] = {**DEFAULT_SETTINGS, **(json.loads(row["data"]) if row else {})}
        return self._cache[guild_id]

    def raw(self, guild_id: int, key: str, default: Any = None) -> Any:
        return self.peek(guild_id).get(key, DEFAULT_SETTINGS.get(key, default))

    async def set(self, guild_id: int, key: str, value: Any) -> None:
        data = await self.get(guild_id)
        data[key] = value
        self._dirty.add(guild_id)

    async def reset(self, guild_id: int, keys: Optional[Iterable[str]] = None) -> None:
        data = await self.get(guild_id)
        if keys is None:
            self._cache[guild_id] = dict(DEFAULT_SETTINGS)
        else:
            for k in keys:
                data[k] = DEFAULT_SETTINGS.get(k)
        self._dirty.add(guild_id)

    async def flush(self) -> None:
        if not self._dirty:
            return
        payload = [(gid, json.dumps(self._cache[gid], ensure_ascii=False)) for gid in self._dirty]
        self._dirty.clear()
        await self.db.executemany(
            "INSERT INTO guild_settings (guild_id, data) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET data = excluded.data", payload)
        await self.db.commit()


# ══════════════════════════════════════════════════════════════
#  5. COG — AIDE
# ══════════════════════════════════════════════════════════════

CATEGORIES: dict[str, tuple[str, int]] = {
    "Modération": ("🛡️", Palette.DANGER),
    "Utilitaires": ("🔧", Palette.ACCENT),
    "Fun": ("🎉", Palette.WARNING),
    "Niveaux": ("📈", Palette.SUCCESS),
    "Tickets": ("🎫", Palette.PRIMARY),
    "Giveaways": ("🎁", Palette.WARNING),
    "Logs": ("📜", Palette.NEUTRAL),
    "Info": ("ℹ️", Palette.FOG),
    "Configuration": ("⚙️", Palette.ACCENT),
}
CATEGORY_OF_COG = {
    "Moderation": "Modération", "Utility": "Utilitaires", "Fun": "Fun", "Levels": "Niveaux",
    "Tickets": "Tickets", "Giveaways": "Giveaways", "Logs": "Logs", "Info": "Info", "Config": "Configuration",
}


class HelpView(discord.ui.View):
    def __init__(self, bot, author, prefix: str) -> None:
        super().__init__(timeout=240)
        self.bot, self.author, self.prefix = bot, author, prefix
        self.pages = self._build_pages()
        self.keys = list(self.pages)
        self.index = 0
        
        # 1. On construit la liste des options
        options_list = [
            discord.SelectOption(label=name, emoji=emoji, description=f"{self._count(name)} commandes", value=name)
            for name, (emoji, color) in CATEGORIES.items()
            if self._count(name) > 0
        ][:25]
        
        # 2. On crée le menu et on l'ajoute à la vue
        self.menu_select = discord.ui.Select(
            placeholder=f"Parcourir — {self._count('__all__')} commandes",
            options=options_list,
            row=0
        )
        self.add_item(self.menu_select)
        
        # 3. On relie le menu à la fonction qui gère le clic
        self.menu_select.callback = self.on_select_choice
        
        self._render() 

    def _commands_for(self, category: str):
        out = []
        for cog_name, cog in self.bot.cogs.items():
            if CATEGORY_OF_COG.get(cog_name) == category:
                out.extend(c for c in cog.get_commands() if not c.hidden)
        return sorted(out, key=lambda c: c.name)

    def _count(self, category: str) -> int:
        if category == "__all__":
            return sum(len(self._commands_for(c)) for c in CATEGORIES)
        return len(self._commands_for(category))

    def _build_pages(self):
        pages = {"Accueil": self._home()}
        for name in CATEGORIES:
            cmds = self._commands_for(name)
            if not cmds:
                continue
            emoji, color = CATEGORIES[name]
            lines = [f"`{self.prefix}{c.name}{f' {c.signature}' if c.signature else ''}`\n"
                     f"　└ {c.description}" for c in cmds[:15]]
            pages[f"{emoji} {name}"] = embed(
                title=f"{emoji}  {name}",
                description=f"`{len(cmds)}` commande(s) — préfixe `{self.prefix}`\n{DIVIDER}\n" + "\n".join(lines),
                color=color, footer=f"{BOT_NAME} • {name}")
        return pages

    def _home(self) -> discord.Embed:
        e = embed(title="📖  Centre d'aide",
                  description=(f"Préfixe : `{self.prefix}`\n"
                               f"Commandes : `{self._count('__all__')}`\n"
                               f"Latence : `{round(self.bot.latency * 1000)} ms`\n{DIVIDER}\n"
                               "Navigue avec le **menu déroulant** ou les **flèches**.\n"
                               f"Détail d'une commande : `{self.prefix}help <commande>`"),
                  color=Palette.PRIMARY, footer=f"{BOT_NAME} • Aide interactive")
        
        e.add_field(name="Catégories", inline=False, value="Utilise le menu déroulant ci-dessous pour naviguer.")
        return e

    def _render(self) -> None:
        self.index %= len(self.keys)
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.label in ("Accueil", "Précédent"):
                    item.disabled = (self.index == 0)
                elif item.label in ("Suivant",):
                    item.disabled = (self.index == len(self.keys) - 1)
        self.menu_select.placeholder = f"Catégorie : {self.keys[self.index]}"

    async def on_select_choice(self, i: discord.Interaction):
        choix = self.menu_select.values[0]
        for key in self.keys:
            if choix in key:
                self.index = self.keys.index(key)
                break
        await self._show(i)

    async def _show(self, i: discord.Interaction) -> None:
        self._render()
        await i.response.edit_message(embed=self.pages[self.keys[self.index]], view=self)

    @discord.ui.button(label="Accueil", emoji="🏠", style=discord.ButtonStyle.primary, row=1)
    async def home(self, i: discord.Interaction, _):
        self.index = 0
        await self._show(i)

    @discord.ui.button(label="Précédent", emoji="◀", style=discord.ButtonStyle.secondary, row=1)
    async def prev(self, i: discord.Interaction, _):
        self.index -= 1
        await self._show(i)

    @discord.ui.button(label="Suivant", emoji="▶", style=discord.ButtonStyle.secondary, row=1)
    async def next(self, i: discord.Interaction, _):
        self.index += 1
        await self._show(i)

    @discord.ui.button(label="Configuration", emoji="⚙️", style=discord.ButtonStyle.success, row=1)
    async def config(self, i: discord.Interaction, _):
        cog = self.bot.get_cog("Config")
        if cog:
            await cog.open_panel(i)

    @discord.ui.button(label="Fermer", emoji="✖", style=discord.ButtonStyle.danger, row=1)
    async def close(self, i: discord.Interaction, _):
        await i.message.delete()

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True


class Help(commands.Cog):
    """Aide interactive et détaillée."""

    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="help", aliases=["h", "aide"], description="Affiche la liste de toutes les commandes du bot, classées par catégorie.")
    @commands.cooldown(2, 5, commands.BucketType.user)
    async def help(self, ctx: commands.Context, *, command_name: str = None):
        if ctx.interaction:
            await ctx.defer()
            
        if command_name:
            cmd = self.bot.get_command(command_name.lower())
            if cmd is None:
                return await ctx.reply(embed=err(f"Aucune commande `{command_name}`. Essaie `{ctx.clean_prefix}help`."),
                                       mention_author=False)
            e = embed(title=f"📘  {ctx.clean_prefix}{cmd.qualified_name}",
                      description=cmd.description or "Aucune description fournie.",
                      color=Palette.PRIMARY, footer="<> obligatoire　·　[] optionnel")
            e.add_field(name="Usage", inline=False, value=f"`{ctx.clean_prefix}{cmd.qualified_name} {cmd.signature}`")
            if cmd.aliases:
                e.add_field(name="Alias", inline=False, value=", ".join(f"`{a}`" for a in cmd.aliases))
            if isinstance(cmd, commands.Group):
                e.add_field(name="Sous-commandes", inline=False,
                            value=", ".join(f"`{s.name}`" for s in cmd.commands) or "*aucune*")
            return await ctx.reply(embed=e, mention_author=False)

        view = HelpView(self.bot, ctx.author, ctx.clean_prefix if ctx.guild else PREFIX)
        view._render()
        try:
            await ctx.send(embed=view.pages["Accueil"], view=view)
        except discord.HTTPException as e:
            print(f"ERREUR HTTP : {e}")
            await ctx.send("Erreur lors de l'affichage de l'aide. Vérifie la console.")

# ══════════════════════════════════════════════════════════════
#  6. COG — CONFIGURATION (panneau)
# ══════════════════════════════════════════════════════════════

Kind = Literal["toggle", "channel", "role", "text", "number", "choice"]


@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    kind: Kind
    hint: str = ""
    choices: tuple[str, ...] = ()
    max_len: int = 400
    channel_types: tuple[discord.ChannelType, ...] = (discord.ChannelType.text,)


@dataclass(frozen=True)
class Module:
    key: str
    label: str
    emoji: str
    color: int
    summary: str
    settings: tuple[Setting, ...] = field(default_factory=tuple)


TEXT_CHANNEL = (discord.ChannelType.text, discord.ChannelType.news)
VOICE = (discord.ChannelType.voice, discord.ChannelType.stage_voice)
CATEGORY = (discord.ChannelType.category,)

MODULES: tuple[Module, ...] = (
    Module("general", "Général", "🧩", Palette.PRIMARY, "Préfixe, langue et comportement global.", (
        Setting("prefix", "Préfixe", "text", "Préfixe des commandes (1 à 5 caractères).", max_len=5),
        Setting("locale", "Langue", "choice", "Langue des réponses.", choices=("fr", "en")),
        Setting("dm_on_action", "MP de sanction", "toggle", "Prévient le membre en MP lors d'une sanction."),
    )),
    Module("welcome", "Arrivées & départs", "👋", Palette.SUCCESS, "Messages d'accueil et de départ.", (
        Setting("welcome_enabled", "Accueil", "toggle", "Active le message de bienvenue."),
        Setting("welcome_channel", "Salon d'accueil", "channel", "Où envoyer les arrivées.", channel_types=TEXT_CHANNEL),
        Setting("welcome_message", "Message d'accueil", "text",
                "Variables : {user} {mention} {guild} {count}", max_len=1500),
        Setting("welcome_embed", "Style embed", "toggle", "Affiche le message sous forme d'embed."),
        Setting("goodbye_enabled", "Départs", "toggle", "Active le message de départ."),
        Setting("goodbye_channel", "Salon de départs", "channel", "Où envoyer les départs.", channel_types=TEXT_CHANNEL),
        Setting("goodbye_message", "Message de départ", "text", "Variables : {user} {guild} {count}", max_len=1500),
        Setting("autorole_enabled", "Rôle automatique", "toggle", "Attribue un rôle à l'arrivée."),
        Setting("autorole_id", "Rôle membres", "role", "Rôle donné aux humains."),
        Setting("botrole_id", "Rôle bots", "role", "Rôle donné aux bots."),
    )),
    Module("logs", "Logs", "📜", Palette.NEUTRAL, "Journalisation des événements.", (
        Setting("logs_enabled", "Logs", "toggle", "Active le système de logs."),
        Setting("logs_channel", "Salon de logs", "channel", "Salon de destination.", channel_types=TEXT_CHANNEL),
        Setting("logs_messages", "Messages", "toggle", "Éditions et suppressions."),
        Setting("logs_members", "Membres", "toggle", "Arrivées, départs, pseudos, rôles."),
        Setting("logs_roles", "Rôles", "toggle", "Création et suppression de rôles."),
        Setting("logs_channels", "Salons", "toggle", "Création et suppression de salons."),
        Setting("logs_voice", "Vocal", "toggle", "Connexions et déplacements vocaux."),
        Setting("logs_mod", "Sanctions", "toggle", "Bans, kicks, timeouts, warns."),
    )),
    Module("automod", "Auto-modération", "🤖", Palette.DANGER, "Filtrage automatique des messages.", (
        Setting("automod_enabled", "Auto-mod", "toggle", "Active le filtrage."),
        Setting("automod_invites", "Invitations", "toggle", "Supprime les liens discord.gg."),
        Setting("automod_links", "Liens externes", "toggle", "Supprime les liens http(s)."),
        Setting("automod_caps", "Majuscules", "toggle", "Supprime les messages en majuscules."),
        Setting("automod_spam", "Spam", "toggle", "Limite 5 messages / 5 secondes."),
        Setting("automod_mentions", "Mentions massives", "toggle", "Limite à 5 mentions par message."),
        Setting("automod_badwords", "Mots interdits", "text", "Séparés par des virgules.", max_len=2000),
        Setting("mod_log_channel", "Salon de sanction", "channel", "Où publier les sanctions.", channel_types=TEXT_CHANNEL),
        Setting("mute_role", "Rôle mute", "role", "Rôle utilisé par !mute."),
    )),
    Module("levels", "Niveaux", "📈", Palette.SUCCESS, "XP par message et récompenses.", (
        Setting("levels_enabled", "Niveaux", "toggle", "Active le gain d'XP."),
        Setting("levels_channel", "Salon d'annonce", "channel", "Où annoncer les niveaux.", channel_types=TEXT_CHANNEL),
        Setting("levels_xp_min", "XP min", "number", "XP minimum par message."),
        Setting("levels_xp_max", "XP max", "number", "XP maximum par message."),
        Setting("levels_cooldown", "Cooldown (s)", "number", "Délai anti-spam."),
        Setting("levels_message", "Message de niveau", "text", "Variables : {user} {level} {guild}", max_len=800),
    )),
    Module("tickets", "Tickets", "🎫", Palette.PRIMARY, "Support par tickets privés.", (
        Setting("tickets_enabled", "Tickets", "toggle", "Active le module."),
        Setting("tickets_category", "Catégorie", "channel", "Catégorie des tickets.", channel_types=CATEGORY),
        Setting("tickets_logs", "Salon de logs", "channel", "Archives des tickets.", channel_types=TEXT_CHANNEL),
        Setting("tickets_staff", "Rôle staff", "role", "Rôle autorisé sur les tickets."),
        Setting("tickets_panel_message", "Texte du panneau", "text", "Description du panneau.", max_len=1000),
        Setting("tickets_panel_image", "Image (URL)", "text", "Lien de l'image pour la bannière du panneau.", max_len=500),
        Setting("tickets_panel_description", "Description", "text", "Texte explicatif sous le titre du panneau.", max_len=2000),
    )),
    Module("giveaways", "Giveaways", "🎁", Palette.WARNING, "Concours avec tirage automatique.", (
        Setting("giveaways_enabled", "Giveaways", "toggle", "Active le module."),
        Setting("giveaways_channel", "Salon par défaut", "channel", "Salon de publication.", channel_types=TEXT_CHANNEL),
        Setting("starboard_enabled", "Starboard", "toggle", "Met en avant les messages réagis."),
        Setting("starboard_channel", "Salon starboard", "channel", "Destination des mises en avant.",
                channel_types=TEXT_CHANNEL),
        Setting("starboard_threshold", "Seuil d'étoiles", "number", "Nombre de ⭐ nécessaires."),
    )),
    Module("voice", "Vocal temporaire", "🔊", Palette.ACCENT, "Salons vocaux jetables.", (
        Setting("tempvoice_enabled", "Vocal temp", "toggle", "Active la création automatique."),
        Setting("tempvoice_hub", "Salon hub", "channel", "Rejoindre ce salon crée un vocal perso.", channel_types=VOICE),
    )),
)
MODULE_BY_KEY = {m.key: m for m in MODULES}


class BasePanel(discord.ui.View):
    def __init__(self, author, timeout: float = 300) -> None:
        super().__init__(timeout=timeout)
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Panneau verrouillé — lance le tien avec `.config`.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True


class TextModal(discord.ui.Modal):
    def __init__(self, panel: "ConfigView", setting: Setting, current: str) -> None:
        super().__init__(title=setting.label[:45])
        self.panel, self.setting = panel, setting
        self.value_input = discord.ui.TextInput(
            label=setting.label[:45], default=str(current)[:setting.max_len],
            placeholder=setting.hint[:100] or None,
            style=discord.TextStyle.paragraph if setting.max_len > 200 else discord.TextStyle.short,
            max_length=setting.max_len, required=False)
        self.add_item(self.value_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.value_input.value.strip()
        value = raw or None
        if self.setting.kind == "number" and raw.isdigit():
            value = int(raw)
        await self.panel.bot.settings.set(interaction.guild_id, self.setting.key, value)
        await self.panel.refresh(interaction)


class Picker(BasePanel):
    def __init__(self, panel: "ConfigView", setting: Setting) -> None:
        super().__init__(panel.author)
        self.panel, self.setting = panel, setting
        if setting.kind == "channel":
            self.picker = discord.ui.ChannelSelect(placeholder=setting.hint or "Choisis un salon…",
                                                   channel_types=list(setting.channel_types),
                                                   min_values=0, max_values=1, row=0)
        else:
            self.picker = discord.ui.RoleSelect(placeholder=setting.hint or "Choisis un rôle…",
                                                min_values=0, max_values=1, row=0)
        self.picker.callback = self._on_pick
        self.add_item(self.picker)

    async def _on_pick(self, i: discord.Interaction) -> None:
        values = self.picker.values
        await self.panel.bot.settings.set(i.guild_id, self.setting.key, values[0].id if values else None)
        await self.panel.refresh(i)

    @discord.ui.button(label="Retour", emoji="↩", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, i: discord.Interaction, _):
        await self.panel.refresh(i)


class ChoicePicker(BasePanel):
    def __init__(self, panel: "ConfigView", setting: Setting) -> None:
        super().__init__(panel.author)
        self.panel, self.setting = panel, setting
        self.select = discord.ui.Select(placeholder=setting.hint or "Choisis une valeur…",
                                        options=[discord.SelectOption(label=c, value=c) for c in setting.choices], row=0)
        self.select.callback = self._on_pick
        self.add_item(self.select)

    async def _on_pick(self, i: discord.Interaction) -> None:
        await self.panel.bot.settings.set(i.guild_id, self.setting.key, self.select.values[0])
        await self.panel.refresh(i)

    @discord.ui.button(label="Retour", emoji="↩", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, i: discord.Interaction, _):
        await self.panel.refresh(i)


class OptionButton(discord.ui.Button):
    def __init__(self, panel: "ConfigView", setting: Setting, row: int) -> None:
        self.panel, self.setting = panel, setting
        super().__init__(row=row)
        self.sync()

    def sync(self) -> None:
        value = self.panel.values.get(self.setting.key)
        if self.setting.kind == "toggle":
            self.style = discord.ButtonStyle.success if value else discord.ButtonStyle.secondary
            self.label = f"{self.setting.label} · {'on' if value else 'off'}"
        else:
            self.style = discord.ButtonStyle.primary
            self.label = f"{self.setting.label}…"
        self.label = self.label[:78]

    async def callback(self, i: discord.Interaction) -> None:
        s = self.setting
        if s.kind == "toggle":
            await self.panel.bot.settings.set(i.guild_id, s.key, 0 if self.panel.values.get(s.key) else 1)
            return await self.panel.refresh(i)
        if s.kind in ("text", "number"):
            return await i.response.send_modal(TextModal(self.panel, s, str(self.panel.values.get(s.key) or "")))
        if s.kind == "choice":
            return await i.response.edit_message(embed=self.panel.module_embed(self.panel.module, s.hint),
                                                 view=ChoicePicker(self.panel, s))
        await i.response.edit_message(embed=self.panel.module_embed(self.panel.module, s.hint), view=Picker(self.panel, s))


class ConfigView(BasePanel):
    def __init__(self, bot, author, guild, module: Optional[Module] = None) -> None:
        super().__init__(author)
        self.bot, self.guild = bot, guild
        self.module = module or MODULES[0]
        self.values = bot.settings.peek(guild.id)
        self.module_select = discord.ui.Select(
            placeholder=f"Module : {self.module.label}",
            options=[discord.SelectOption(label=m.label, value=m.key, emoji=m.emoji, description=m.summary[:95])
                     for m in MODULES], row=3)
        self.module_select.callback = self._switch_module
        self.add_item(self.module_select)
        self.rebuild_options()

    def rebuild_options(self) -> None:
        for item in list(self.children):
            if isinstance(item, OptionButton):
                self.remove_item(item)
        for i, setting in enumerate(self.module.settings[:10]):
            self.add_item(OptionButton(self, setting, row=i // 5))
        for item in self.children:
            if isinstance(item, OptionButton):
                item.sync()

    def module_embed(self, module: Module, hint: str = "") -> discord.Embed:
        lines = []
        for s in module.settings:
            raw = self.values.get(s.key)
            if s.kind == "toggle":
                shown = "`activé`" if raw else "`désactivé`"
            elif s.kind == "channel":
                shown = f"<#{raw}>" if raw and self.guild.get_channel(raw) else "`non défini`"
            elif s.kind == "role":
                r = self.guild.get_role(raw) if raw else None
                shown = r.mention if r else "`non défini`"
            elif raw in (None, ""):
                shown = "`non défini`"
            else:
                text = str(raw).replace("\n", " ")
                shown = f"`{text[:70]}{'…' if len(text) > 70 else ''}`"
            lines.append(f"{module.emoji} **{s.label}** — {shown}")
        e = embed(title=f"{module.emoji}  Module — {module.label}",
                  description=f"{module.summary}\n{DIVIDER}\n" + "\n".join(lines),
                  color=module.color, footer=f"{BOT_NAME} • .config — panneau verrouillé sur toi")
        if hint:
            e.add_field(name="💡 Action", inline=False, value=hint)
        return e

    async def refresh(self, i: discord.Interaction) -> None:
        self.values = await self.bot.settings.get(self.guild.id)
        self.module_select.placeholder = f"Module : {self.module.label}"
        self.rebuild_options()
        await i.response.edit_message(embed=self.module_embed(self.module), view=self)

    async def _switch_module(self, i: discord.Interaction) -> None:
        self.module = MODULE_BY_KEY[self.module_select.values[0]]
        await self.refresh(i)

    @discord.ui.button(label="Rafraîchir", emoji="🔄", style=discord.ButtonStyle.secondary, row=4)
    async def refresh_btn(self, i: discord.Interaction, _):
        await self.refresh(i)

    @discord.ui.button(label="Réinitialiser", emoji="♻️", style=discord.ButtonStyle.danger, row=4)
    async def reset_btn(self, i: discord.Interaction, _):
        await self.bot.settings.reset(self.guild.id, [s.key for s in self.module.settings])
        await self.refresh(i)

    @discord.ui.button(label="Aperçu", emoji="👁", style=discord.ButtonStyle.primary, row=4)
    async def preview_btn(self, i: discord.Interaction, _):
        await i.response.send_message(embed=self.module_embed(self.module), ephemeral=True)

    @discord.ui.button(label="Fermer", emoji="✖", style=discord.ButtonStyle.danger, row=4)
    async def close_btn(self, i: discord.Interaction, _):
        await i.message.delete()


class Config(commands.Cog):
    """Configuration complète du serveur via un panneau interactif."""

    def __init__(self, bot) -> None:
        self.bot = bot

    async def open_panel(self, i: discord.Interaction, edit: bool = False) -> None:
        view = ConfigView(self.bot, i.user, i.guild)
        e = view.module_embed(view.module)
        if edit:
            await i.response.edit_message(embed=e, view=view)
        else:
            await i.response.send_message(embed=e, view=view, ephemeral=True)

    @commands.hybrid_command(name="config", aliases=["conf", "setup", "parametres"],
                             description="Ouvre le panneau interactif de configuration du serveur (nécessite la permission Gérer le serveur).")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_permissions(embed_links=True)
    async def config(self, ctx: commands.Context):
        view = ConfigView(self.bot, ctx.author, ctx.guild)
        await ctx.send(embed=view.module_embed(view.module), view=view)

    @commands.hybrid_command(name="prefix", description="Change le préfixe des commandes pour ce serveur (maximum 5 caractères).")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def prefix(self, ctx: commands.Context, nouveau: str = None):
        if nouveau is None:
            return await ctx.reply(embed=embed(title="🔧 Préfixe actuel",
                                               description=f"`{self.bot.settings.raw(ctx.guild.id, 'prefix')}`",
                                               color=Palette.PRIMARY), mention_author=False)
        if len(nouveau) > 5:
            return await ctx.reply("5 caractères maximum.", mention_author=False)
        await self.bot.settings.set(ctx.guild.id, "prefix", nouveau)
        await ctx.reply(embed=ok(f"Nouveau préfixe : `{nouveau}`"), mention_author=False)

    @commands.hybrid_command(name="resetconfig", description="Réinitialise tous les paramètres de configuration du serveur à leurs valeurs par défaut.")
    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    async def resetconfig(self, ctx: commands.Context):
        await self.bot.settings.reset(ctx.guild.id)
        await ctx.reply(embed=warn(f"{len(DEFAULT_SETTINGS)} réglages remis à zéro.", title="Configuration réinitialisée"),
                        mention_author=False)


# ══════════════════════════════════════════════════════════════
#  7. COG — MODÉRATION
# ══════════════════════════════════════════════════════════════

class Moderation(commands.Cog):
    """Boîte à outils de modération."""

    def __init__(self, bot) -> None:
        self.bot = bot

    async def log_mod(self, guild: discord.Guild, text: str) -> None:
        cid = self.bot.settings.raw(guild.id, "mod_log_channel")
        channel = guild.get_channel(cid) if cid else None
        if channel:
            try:
                await channel.send(embed=embed(description=text, color=Palette.WARNING, footer="Journal de modération"))
            except discord.HTTPException:
                pass

    async def dm(self, member: discord.Member, text: str) -> bool:
        if not self.bot.settings.raw(member.guild.id, "dm_on_action"):
            return False
        try:
            await member.send(embed=embed(title="Sanction", description=text, color=Palette.DANGER,
                                          footer=member.guild.name))
            return True
        except discord.Forbidden:
            return False

    @commands.hybrid_command(name="ban", description="Bannit définitivement un membre du serveur.")
    @commands.guild_only()
    @commands.bot_has_permissions(ban_members=True)
    @mod_only()
    @app_commands.describe(membre="Membre à bannir", jours="Jours de messages à supprimer", raison="Motif")
    async def ban(self, ctx: commands.Context, membre: discord.Member, jours: Optional[int] = 0,
                  raison: str = "Aucune raison"):
        if membre.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.reply(embed=warn("Ce membre a un rôle supérieur ou égal au tien."), mention_author=False)
        await self.dm(membre, f"Tu as été **banni** de **{ctx.guild.name}**\n**Motif :** {raison}")
        await membre.ban(reason=f"{ctx.author} — {raison}", delete_message_days=max(0, min(jours, 7)))
        await ctx.reply(embed=ok(f"**{membre}** a été banni.\n**Motif :** {raison}"), mention_author=False)
        await self.log_mod(ctx.guild, f"🔨 **Ban** — {membre.mention} par {ctx.author.mention}\n> {raison}")

    @commands.hybrid_command(name="unban", description="Débannit un utilisateur en utilisant son ID Discord.")
    @commands.guild_only()
    @commands.bot_has_permissions(ban_members=True)
    @mod_only()
    async def unban(self, ctx: commands.Context, user_id: int, raison: str = "Aucune raison"):
        try:
            await ctx.guild.unban(discord.Object(id=user_id), reason=f"{ctx.author} — {raison}")
        except discord.NotFound:
            return await ctx.reply(embed=err("Cet utilisateur n'est pas banni."), mention_author=False)
        await ctx.reply(embed=ok(f"`{user_id}` a été débanni."), mention_author=False)

    @commands.hybrid_command(name="softban", description="Bannit puis débannit immédiatement un membre pour supprimer ses messages récents (purge 7 jours).")
    @commands.guild_only()
    @commands.bot_has_permissions(ban_members=True)
    @mod_only()
    async def softban(self, ctx: commands.Context, membre: discord.Member, raison: str = "Aucune raison"):
        await membre.ban(reason=f"softban — {raison}", delete_message_days=7)
        await ctx.guild.unban(membre, reason="softban")
        await ctx.reply(embed=ok(f"**{membre}** a été softban."), mention_author=False)

    @commands.hybrid_command(name="tempban", description="Bannit un membre pour une durée déterminée (ex: 10m, 1h, 7d).")
    @commands.guild_only()
    @commands.bot_has_permissions(ban_members=True)
    @mod_only()
    async def tempban(self, ctx: commands.Context, membre: discord.Member, duree: Duration,
                      raison: str = "Aucune raison"):
        await self.dm(membre, f"Tu es **banni {humanize(duree)}** de **{ctx.guild.name}**\n**Motif :** {raison}")
        await membre.ban(reason=f"tempban {humanize(duree)} — {raison}")
        await ctx.reply(embed=ok(f"**{membre}** banni pour **{humanize(duree)}**."), mention_author=False)
        await asyncio.sleep(duree)
        try:
            await ctx.guild.unban(discord.Object(id=membre.id), reason="fin du tempban")
        except discord.NotFound:
            pass

    @commands.hybrid_command(name="massban", description="Bannit plusieurs utilisateurs d'un coup en fournissant leurs IDs séparés par des espaces.")
    @commands.guild_only()
    @commands.bot_has_permissions(ban_members=True)
    @mod_only()
    async def massban(self, ctx: commands.Context, ids: str):
        liste_ids = ids.split()
        done = 0
        for uid in liste_ids[:50]:
            try:
                await ctx.guild.ban(discord.Object(id=int(uid)), reason=f"massban par {ctx.author}")
                done += 1
            except (discord.HTTPException, ValueError):
                continue
        await ctx.reply(embed=ok(f"`{done}` membre(s) banni(s)."), mention_author=False)

    @commands.hybrid_command(name="kick", description="Expulse un membre du serveur (il pourra revenir avec une invitation).")
    @commands.guild_only()
    @commands.bot_has_permissions(kick_members=True)
    @mod_only()
    async def kick(self, ctx: commands.Context, membre: discord.Member, raison: str = "Aucune raison"):
        await self.dm(membre, f"Tu as été **expulsé** de **{ctx.guild.name}**\n**Motif :** {raison}")
        await membre.kick(reason=f"{ctx.author} — {raison}")
        await ctx.reply(embed=ok(f"**{membre}** a été expulsé."), mention_author=False)
        await self.log_mod(ctx.guild, f"👢 **Kick** — {membre.mention} par {ctx.author.mention}")

    @commands.hybrid_command(name="mute", aliases=["timeout"], description="Rend un membre muet (timeout) pour une durée définie.")
    @commands.guild_only()
    @commands.bot_has_permissions(moderate_members=True)
    @mod_only()
    async def mute(self, ctx: commands.Context, membre: discord.Member, duree: Duration = 3600,
                   raison: str = "Aucune raison"):
        await membre.timeout(discord.utils.utcnow() + timedelta(seconds=duree), reason=f"{ctx.author} — {raison}")
        await self.dm(membre, f"Tu es **muet {humanize(duree)}** sur **{ctx.guild.name}**\n**Motif :** {raison}")
        await ctx.reply(embed=ok(f"**{membre}** muet pour **{humanize(duree)}**."), mention_author=False)

    @commands.hybrid_command(name="unmute", description="Retire le timeout (rend la parole) à un membre.")
    @commands.guild_only()
    @commands.bot_has_permissions(moderate_members=True)
    @mod_only()
    async def unmute(self, ctx: commands.Context, membre: discord.Member):
        await membre.timeout(None, reason=f"unmute par {ctx.author}")
        await ctx.reply(embed=ok(f"**{membre}** n'est plus muet."), mention_author=False)

    @commands.hybrid_command(name="warn", description="Avertit un membre. Les avertissements sont enregistrés dans la base de données.")
    @commands.guild_only()
    @mod_only()
    async def warn(self, ctx: commands.Context, membre: discord.Member, raison: str = "Aucune raison"):
        await self.bot.db.execute(
            "INSERT INTO warnings (guild_id, user_id, mod_id, reason, created) VALUES (?, ?, ?, ?, ?)",
            (ctx.guild.id, membre.id, ctx.author.id, raison, int(time.time())))
        await self.bot.db.commit()
        row = await self.bot.db.fetchone("SELECT COUNT(*) AS c FROM warnings WHERE guild_id = ? AND user_id = ?",
                                         (ctx.guild.id, membre.id))
        await self.dm(membre, f"Tu as reçu un **avertissement** sur **{ctx.guild.name}**\n**Motif :** {raison}")
        await ctx.reply(embed=warn(f"**{membre}** averti ({row['c']} au total).\n**Motif :** {raison}",
                                   title="Avertissement"), mention_author=False)

    @commands.hybrid_command(name="warnings", aliases=["infractions"], description="Affiche la liste des avertissements d'un membre.")
    @commands.guild_only()
    async def warnings(self, ctx: commands.Context, membre: discord.Member = None):
        membre = membre or ctx.author
        rows = await self.bot.db.fetchall(
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT 20",
            (ctx.guild.id, membre.id))
        if not rows:
            return await ctx.reply(embed=ok(f"**{membre}** n'a aucun avertissement."), mention_author=False)
        lines = [f"`#{r['id']}` <t:{r['created']}:R> — {r['reason'][:60]}" for r in rows]
        await ctx.reply(embed=embed(title=f"⚠️ Avertissements de {membre}", description="\n".join(lines),
                                    color=Palette.WARNING), mention_author=False)

    @commands.hybrid_command(name="unwarn", description="Supprime un avertissement spécifique en utilisant son ID.")
    @commands.guild_only()
    @mod_only()
    async def unwarn(self, ctx: commands.Context, warn_id: int):
        if not await self.bot.db.fetchone("SELECT 1 FROM warnings WHERE id = ? AND guild_id = ?", (warn_id, ctx.guild.id)):
            return await ctx.reply(embed=err(f"Avertissement `#{warn_id}` introuvable."), mention_author=False)
        await self.bot.db.execute("DELETE FROM warnings WHERE id = ?", (warn_id,))
        await self.bot.db.commit()
        await ctx.reply(embed=ok(f"Avertissement `#{warn_id}` supprimé."), mention_author=False)

    @commands.hybrid_command(name="clearwarns", description="Efface tous les avertissements d'un membre.")
    @commands.guild_only()
    @mod_only()
    async def clearwarns(self, ctx: commands.Context, membre: discord.Member):
        await self.bot.db.execute("DELETE FROM warnings WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, membre.id))
        await self.bot.db.commit()
        await ctx.reply(embed=ok(f"Avertissements de **{membre}** effacés."), mention_author=False)

    @commands.hybrid_command(name="purge", aliases=["clear"], description="Supprime en masse les messages récents du salon (max 500).")
    @commands.guild_only()
    @commands.bot_has_permissions(manage_messages=True)
    @mod_only()
    async def purge(self, ctx: commands.Context, quantite: int = 10, membre: discord.Member = None, filtre: str = None):
        quantite = max(1, min(quantite, 500))
        check = None
        
        if membre:
            check = lambda m: m.author.id == membre.id
        if filtre == "bots":
            check = lambda m: m.author.bot
        elif filtre == "images":
            check = lambda m: bool(m.attachments)
        elif filtre == "liens":
            check = lambda m: "http" in m.content
            
        await ctx.defer()
        
        # On récupère la liste des messages supprimés
        if check:
            deleted = await ctx.channel.purge(limit=quantite, check=check, before=ctx.message)
        else:
            deleted = await ctx.channel.purge(limit=quantite, before=ctx.message)
            
        # On sécurise l'affichage (si deleted est None, on met 0)
        count = len(deleted) if deleted else 0
        
        try:
            await ctx.send(embed=ok(f"`{count}` message(s) supprimé(s).", title="Purge"), delete_after=6)
        except discord.HTTPException:
            pass 

    @commands.hybrid_command(name="nuke", description="Recrée le salon à l'identique (supprime et recrée le salon, utile pour nettoyer).")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def nuke(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        try:
            pos = ctx.channel.position
            clone = await ctx.channel.clone(reason=f"nuke par {ctx.author}")
            await ctx.channel.delete(reason="nuke")
            await clone.edit(position=pos)
            await clone.send(embed=ok(f"💥 Salon recréé par {ctx.author.mention}.", title="Nuke"))
        except discord.HTTPException as e:
            await ctx.followup.send(f"Le clonage a échoué (Erreur: {e.status}). Le salon n'a pas été supprimé.", ephemeral=True)

    @commands.hybrid_command(name="slowmode", description="Définit le mode lent dans le salon (délai en secondes entre chaque message).")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, secondes: int = 0):
        await ctx.channel.edit(slowmode_delay=max(0, min(secondes, 21600)))
        await ctx.reply(embed=ok(f"Mode lent : **{secondes}s**."), mention_author=False)

    @commands.hybrid_command(name="lock", description="Verrouille le salon (empêche les membres d'envoyer des messages).")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context, raison: str = "Aucune raison"):
        ow = ctx.channel.overwrites_for(ctx.guild.default_role)
        ow.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=ow, reason=raison)
        await ctx.reply(embed=ok(f"🔒 Salon verrouillé.\n**Motif :** {raison}"), mention_author=False)

    @commands.hybrid_command(name="unlock", description="Déverrouille le salon (rétablit l'envoi de messages).")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context):
        ow = ctx.channel.overwrites_for(ctx.guild.default_role)
        ow.send_messages = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=ow)
        await ctx.reply(embed=ok("🔓 Salon déverrouillé."), mention_author=False)

    @commands.hybrid_command(name="hide", description="Cache le salon pour tout le monde (sauf les administrateurs).")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def hide(self, ctx: commands.Context):
        ow = ctx.channel.overwrites_for(ctx.guild.default_role)
        ow.view_channel = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=ow)
        await ctx.reply(embed=ok("🙈 Salon masqué."), mention_author=False)

    @commands.hybrid_command(name="unhide", description="Rend le salon visible pour tout le monde.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def unhide(self, ctx: commands.Context):
        ow = ctx.channel.overwrites_for(ctx.guild.default_role)
        ow.view_channel = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=ow)
        await ctx.reply(embed=ok("👀 Salon visible."), mention_author=False)

    @commands.hybrid_group(name="role", description="Gestion des rôles", invoke_without_command=True)
    @commands.guild_only()
    async def role(self, ctx: commands.Context):
        await ctx.reply(embed=embed(title="🎭 Gestion des rôles",
                                    description="`.role add <membre> <rôle>`\n`!role remove <membre> <rôle>`\n"
                                                "`.role all <rôle>`\n`!role info <rôle>`",
                                    color=Palette.PRIMARY), mention_author=False)

    @role.command(name="add", description="Ajoute un rôle à un membre.")
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_add(self, ctx: commands.Context, membre: discord.Member, role: discord.Role):
        await membre.add_roles(role, reason=f"par {ctx.author}")
        await ctx.reply(embed=ok(f"{role.mention} ajouté à {membre.mention}."), mention_author=False)

    @role.command(name="remove", description="Retire un rôle à un membre.")
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_remove(self, ctx: commands.Context, membre: discord.Member, role: discord.Role):
        await membre.remove_roles(role, reason=f"par {ctx.author}")
        await ctx.reply(embed=ok(f"{role.mention} retiré à {membre.mention}."), mention_author=False)

    @role.command(name="all", description="Donne un rôle à tous les membres humains du serveur.")
    @commands.has_guild_permissions(manage_roles=True)
    async def role_all(self, ctx: commands.Context, role: discord.Role):
        await ctx.defer()
        count = 0
        for member in ctx.guild.members:
            if role not in member.roles and not member.bot:
                try:
                    await member.add_roles(role, reason="role all")
                    count += 1
                except discord.HTTPException:
                    pass
        await ctx.reply(embed=ok(f"{role.mention} donné à `{count}` membre(s)."), mention_author=False)

    @role.command(name="info", description="Affiche les informations détaillées sur un rôle.")
    async def role_info(self, ctx: commands.Context, role: discord.Role):
        e = embed(title=f"🎭 {role.name}", color=role.color)
        e.add_field(name="ID", value=f"`{role.id}`")
        e.add_field(name="Couleur", value=str(role.color))
        e.add_field(name="Membres", value=str(len(role.members)))
        e.add_field(name="Position", value=str(role.position))
        e.add_field(name="Mentionnable", value="oui" if role.mentionable else "non")
        e.add_field(name="Créé", value=discord.utils.format_dt(role.created_at, "R"))
        await ctx.reply(embed=e, mention_author=False)

    @commands.hybrid_command(name="temprole", description="Donne un rôle temporairement à un membre (ex: 1h, 1j).")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def temprole(self, ctx: commands.Context, membre: discord.Member, duree: Duration, role: discord.Role):
        await membre.add_roles(role, reason=f"temprole par {ctx.author}")
        await ctx.reply(embed=ok(f"{role.mention} donné à {membre.mention} pour **{humanize(duree)}**."),
                        mention_author=False)
        await asyncio.sleep(duree)
        if role in membre.roles:
            await membre.remove_roles(role, reason="fin du temprole")

    @commands.hybrid_command(name="rename", description="Change le surnom (pseudo) d'un membre sur le serveur.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_nicknames=True)
    async def rename(self, ctx: commands.Context, membre: discord.Member, pseudo: str):
        await membre.edit(nick=pseudo[:32], reason=f"par {ctx.author}")
        await ctx.reply(embed=ok(f"**{membre}** renommé en `{pseudo}`."), mention_author=False)


# ══════════════════════════════════════════════════════════════
#  8. COG — UTILITAIRES
# ══════════════════════════════════════════════════════════════

SNIPES: dict[int, tuple] = {}
EDIT_SNIPES: dict[int, tuple] = {}


class Utility(commands.Cog):
    """Outils du quotidien."""

    def __init__(self, bot) -> None:
        self.bot = bot
        self._afk: dict[int, str] = {}

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.guild and not message.author.bot:
            SNIPES[message.channel.id] = (message.author, message.content,
                                          message.created_at, [a.url for a in message.attachments])

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.guild and not before.author.bot and before.content != after.content:
            EDIT_SNIPES[before.channel.id] = (before.author, before.content, after.content)

    @commands.hybrid_command(name="ping", description="Affiche la latence du bot (en millisecondes).")
    async def ping(self, ctx: commands.Context):
        t0 = time.perf_counter()
        msg = await ctx.reply(embed=embed(description="Ping…"), mention_author=False)
        rest = round((time.perf_counter() - t0) * 1000)
        await msg.edit(embed=embed(title="🏓 Pong", description=f"Gateway : `{round(self.bot.latency * 1000)} ms`\n"
                                                               f"REST : `{rest} ms`", color=Palette.SUCCESS))

    @commands.hybrid_command(name="uptime", description="Affiche depuis combien de temps le bot est en ligne.")
    async def uptime(self, ctx: commands.Context):
        await ctx.reply(embed=embed(title="⏱️ Uptime", description=humanize(int(time.time() - self.bot.launch_time)),
                                    color=Palette.PRIMARY), mention_author=False)

    @commands.hybrid_command(name="userinfo", aliases=["ui", "whois"], description="Affiche les informations sur un membre (ID, rôles, dates, etc.).")
    @commands.guild_only()
    async def userinfo(self, ctx: commands.Context, membre: discord.Member = None):
        m = membre or ctx.author
        e = embed(title=f"👤 {m}", color=m.color or Palette.PRIMARY, thumbnail=m.display_avatar.url)
        e.add_field(name="ID", value=f"`{m.id}`", inline=True)
        e.add_field(name="Surnom", value=m.nick or "*aucun*", inline=True)
        e.add_field(name="Bot", value="oui" if m.bot else "non", inline=True)
        e.add_field(name="Compte créé", value=discord.utils.format_dt(m.created_at, "R"), inline=True)
        e.add_field(name="A rejoint", value=discord.utils.format_dt(m.joined_at, "R") if m.joined_at else "?", inline=True)
        roles = [r.mention for r in reversed(m.roles) if r != ctx.guild.default_role]
        e.add_field(name=f"Rôles ({len(roles)})", value=" ".join(roles[:20]) or "*aucun*", inline=False)
        await ctx.reply(embed=e, mention_author=False)

    @commands.hybrid_command(name="serverinfo", aliases=["si"], description="Affiche les informations générales sur le serveur.")
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context):
        g = ctx.guild
        humans = sum(1 for m in g.members if not m.bot)
        e = embed(title=f"🏠 {g.name}", color=Palette.PRIMARY, thumbnail=g.icon.url if g.icon else None)
        e.add_field(name="ID", value=f"`{g.id}`", inline=True)
        e.add_field(name="Propriétaire", value=g.owner.mention if g.owner else "?", inline=True)
        e.add_field(name="Créé", value=discord.utils.format_dt(g.created_at, "R"), inline=True)
        e.add_field(name="Membres", value=f"`{humans}` humains · `{g.member_count - humans}` bots", inline=True)
        e.add_field(name="Salons", value=f"`{len(g.text_channels)}` texte · `{len(g.voice_channels)}` vocal", inline=True)
        e.add_field(name="Rôles", value=f"`{len(g.roles)}`", inline=True)
        e.add_field(name="Boosts", value=f"niveau `{g.premium_tier}` · `{g.premium_subscription_count}` boosts", inline=True)
        e.add_field(name="Émojis", value=f"`{len(g.emojis)}`", inline=True)
        e.add_field(name="Vérification", value=str(g.verification_level), inline=True)
        await ctx.reply(embed=e, mention_author=False)

    @commands.hybrid_command(name="avatar", description="Affiche l'avatar d'un membre en grand format.")
    async def avatar(self, ctx: commands.Context, membre: discord.Member = None):
        m = membre or ctx.author
        await ctx.reply(embed=embed(title=f"🖼️ Avatar de {m}", color=Palette.PRIMARY,
                                    image=m.display_avatar.with_size(1024).url), mention_author=False)

    @commands.hybrid_command(name="banner", description="Affiche la bannière de profil d'un membre.")
    async def banner(self, ctx: commands.Context, membre: discord.Member = None):
        m = membre or ctx.author
        user = await self.bot.fetch_user(m.id)
        if not user.banner:
            return await ctx.reply(embed=err(f"**{m}** n'a pas de bannière."), mention_author=False)
        await ctx.reply(embed=embed(title=f"🎨 Bannière de {m}", color=Palette.PRIMARY,
                                    image=user.banner.with_size(1024).url), mention_author=False)

    @commands.hybrid_command(name="servericon", description="Affiche l'icône du serveur en grand format.")
    @commands.guild_only()
    async def servericon(self, ctx: commands.Context):
        if not ctx.guild.icon:
            return await ctx.reply(embed=err("Ce serveur n'a pas d'icône."), mention_author=False)
        await ctx.reply(embed=embed(title=ctx.guild.name, color=Palette.PRIMARY,
                                    image=ctx.guild.icon.with_size(1024).url), mention_author=False)

    @commands.hybrid_command(name="membercount", description="Affiche le nombre total de membres (humains et bots).")
    @commands.guild_only()
    async def membercount(self, ctx: commands.Context):
        g = ctx.guild
        bots = sum(1 for m in g.members if m.bot)
        await ctx.reply(embed=embed(title="👥 Membres",
                                    description=f"Total : `{g.member_count}`\nHumains : `{g.member_count - bots}`\n"
                                                f"Bots : `{bots}`", color=Palette.PRIMARY), mention_author=False)

    @commands.hybrid_command(name="roles", description="Affiche la liste de tous les rôles du serveur.")
    @commands.guild_only()
    async def roles(self, ctx: commands.Context):
        roles = [r for r in reversed(ctx.guild.roles) if r != ctx.guild.default_role]
        lines = [f"{r.mention} — `{r.id}` — `{len(r.members)}` membres" for r in roles]
        pages = build_pages(lines, 20, f"🎭 Rôles ({len(roles)})")
        await ctx.send(embed=pages[0], view=Paginator(pages, ctx.author))

    @commands.hybrid_command(name="channelinfo", description="Affiche les informations sur un salon (ID, catégorie, date de création, etc.).")
    @commands.guild_only()
    async def channelinfo(self, ctx: commands.Context, salon: discord.TextChannel = None):
        c = salon or ctx.channel
        e = embed(title=f"#️⃣ {c.name}", color=Palette.PRIMARY)
        e.add_field(name="ID", value=f"`{c.id}`", inline=True)
        e.add_field(name="Catégorie", value=c.category.name if c.category else "*aucune*", inline=True)
        e.add_field(name="Créé", value=discord.utils.format_dt(c.created_at, "R"), inline=True)
        e.add_field(name="Mode lent", value=f"`{c.slowmode_delay}s`", inline=True)
        e.add_field(name="NSFW", value="oui" if c.nsfw else "non", inline=True)
        e.add_field(name="Sujet", value=c.topic or "*aucun*", inline=False)
        await ctx.reply(embed=e, mention_author=False)

    @commands.hybrid_command(name="emoji", description="Affiche la liste des émojis personnalisés du serveur.")
    @commands.guild_only()
    async def emoji(self, ctx: commands.Context):
        if not ctx.guild.emojis:
            return await ctx.reply(embed=err("Aucun émoji sur ce serveur."), mention_author=False)
        lines = [f"{e} — `:{e.name}:` — `{e.id}`" for e in ctx.guild.emojis]
        pages = build_pages(lines, 25, f"😄 Émojis ({len(lines)})")
        await ctx.send(embed=pages[0], view=Paginator(pages, ctx.author))

    @commands.hybrid_command(name="steal", description="Ajoute un émoji d'un autre serveur à ce serveur (nécessite la permission Gérer les émojis).")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_emojis=True)
    @commands.bot_has_permissions(manage_emojis=True)
    async def steal(self, ctx: commands.Context, emoji: discord.PartialEmoji, nom: str = None):
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(emoji.url) as r:
                data = await r.read()
        try:
            created = await ctx.guild.create_custom_emoji(name=nom or emoji.name, image=data,
                                                          reason=f"volé par {ctx.author}")
        except discord.HTTPException as exc:
            return await ctx.reply(embed=err(f"Échec : {exc.text}"), mention_author=False)
        await ctx.reply(embed=ok(f"{created} `:{created.name}:` ajouté."), mention_author=False)

    @commands.hybrid_command(name="snipe", description="Affiche le dernier message supprimé dans ce salon.")
    @commands.guild_only()
    async def snipe(self, ctx: commands.Context):
        data = SNIPES.get(ctx.channel.id)
        if not data:
            return await ctx.reply(embed=err("Rien à sniper ici."), mention_author=False)
        author, content, created, files = data
        e = embed(title=f"🔍 Message de {author}", description=content or "*pièce jointe*",
                  color=Palette.WARNING, timestamp=False)
        e.set_footer(text=discord.utils.format_dt(created, "R"))
        if files:
            e.set_image(url=files[0])
        await ctx.reply(embed=e, mention_author=False)

    @commands.hybrid_command(name="editsnipe", description="Affiche le dernier message modifié dans ce salon.")
    @commands.guild_only()
    async def editsnipe(self, ctx: commands.Context):
        data = EDIT_SNIPES.get(ctx.channel.id)
        if not data:
            return await ctx.reply(embed=err("Rien à snipers ici."), mention_author=False)
        author, before, after = data
        e = embed(title=f"✏️ Édition de {author}", color=Palette.ACCENT, timestamp=False)
        e.add_field(name="Avant", value=before[:1000] or "*vide*", inline=False)
        e.add_field(name="Après", value=after[:1000] or "*vide*", inline=False)
        await ctx.reply(embed=e, mention_author=False)

    @commands.hybrid_command(name="poll", description="Crée un sondage à réactions. Sépare les options par des virgules.")
    @commands.guild_only()
    async def poll(self, ctx: commands.Context, question: str, options: str = None):
        opts_list = [o.strip() for o in options.split(",")] if options else []
        
        if len(opts_list) > 10:
            return await ctx.reply(embed=err("10 options maximum."), mention_author=False)
            
        letters = "🇦🇧🇨🇩🇪🇫🇬🇭🇮🇯"
        if opts_list:
            reac = letters[:len(opts_list)]
            desc = "\n".join(f"{letters[i]} {o}" for i, o in enumerate(opts_list))
        else:
            reac, desc = "✅❌", "✅ Pour\n❌ Contre"
            
        msg = await ctx.send(embed=embed(title=f"📊 {question}", description=desc, color=Palette.ACCENT,
                                         footer=f"Sondage de {ctx.author}"))
        for char in reac:
            await msg.add_reaction(char)
            
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.hybrid_command(name="remind", aliases=["rappel"], description="Programme un rappel privé que le bot t'enverra en message privé.")
    async def remind(self, ctx: commands.Context, duree: Duration, texte: str):
        await ctx.reply(embed=ok(f"Rappel dans **{humanize(duree)}**."), mention_author=False)
        await asyncio.sleep(duree)
        try:
            await ctx.author.send(embed=embed(title="⏰ Rappel",
                                              description=f"{texte}\n\n[Contexte]({ctx.message.jump_url})",
                                              color=Palette.ACCENT))
        except discord.Forbidden:
            await ctx.send(f"{ctx.author.mention} — ⏰ {texte}")

    @commands.hybrid_command(name="afk", description="Passe en mode AFK (Away From Keyboard). Les gens qui te mentionnent verront ton statut.")
    async def afk(self, ctx: commands.Context, raison: str = "AFK"):
        self._afk[ctx.author.id] = raison
        await ctx.reply(embed=ok(f"**{ctx.author.display_name}** est AFK : {raison}"), mention_author=False)

    @commands.hybrid_command(name="calc", aliases=["math"], description="Calcule une expression mathématique simple (ex: 2 + 2 * 5).")
    async def calc(self, ctx: commands.Context, expression: str):
        try:
            result = eval(expression.replace("^", "**"), {"__builtins__": {}}, {})
        except Exception as exc:
            return await ctx.reply(embed=err(f"Expression invalide : `{exc}`"), mention_author=False)
        await ctx.reply(embed=embed(title="🧮 Calcul", description=f"`{expression}` = **`{result}`**",
                                    color=Palette.SUCCESS), mention_author=False)

    @commands.hybrid_command(name="invite", description="Génère un lien d'invitation pour ajouter le bot sur un autre serveur.")
    async def invite(self, ctx: commands.Context):
        perms = discord.Permissions(manage_guild=True, manage_roles=True, manage_channels=True, kick_members=True,
                                    ban_members=True, manage_messages=True, moderate_members=True, embed_links=True,
                                    attach_files=True, read_message_history=True, add_reactions=True)
        url = discord.utils.oauth_url(self.bot.user.id, permissions=perms, scopes=("bot", "applications.commands"))
        await ctx.reply(embed=embed(title="📨 Inviter le bot", description=f"[Clique ici]({url})",
                                    color=Palette.PRIMARY), mention_author=False)

    @commands.hybrid_group(name="tag", description="Système de commandes personnalisées (tags).", invoke_without_command=True)
    @commands.guild_only()
    async def tag(self, ctx: commands.Context, nom: str = None):
        if nom is None:
            rows = await self.bot.db.fetchall("SELECT name FROM tags WHERE guild_id = ? ORDER BY name", (ctx.guild.id,))
            if not rows:
                return await ctx.reply(embed=info("Aucun tag. `.tag create <nom> <contenu>`"), mention_author=False)
            return await ctx.reply(embed=embed(title="🏷️ Tags", description=", ".join(f"`{r['name']}`" for r in rows),
                                               color=Palette.PRIMARY), mention_author=False)
        row = await self.bot.db.fetchone("SELECT content FROM tags WHERE guild_id = ? AND name = ?",
                                         (ctx.guild.id, nom.lower()))
        if not row:
            return await ctx.reply(embed=err(f"Tag `{nom}` introuvable."), mention_author=False)
        await self.bot.db.execute("UPDATE tags SET uses = uses + 1 WHERE guild_id = ? AND name = ?",
                                  (ctx.guild.id, nom.lower()))
        await self.bot.db.commit()
        await ctx.reply(row["content"], mention_author=False)

    @tag.command(name="create", description="Crée un nouveau tag avec un nom et un contenu.")
    @commands.has_guild_permissions(manage_messages=True)
    async def tag_create(self, ctx: commands.Context, nom: str, contenu: str):
        if await self.bot.db.fetchone("SELECT 1 FROM tags WHERE guild_id = ? AND name = ?", (ctx.guild.id, nom.lower())):
            return await ctx.reply(embed=err("Ce tag existe déjà."), mention_author=False)
        await self.bot.db.execute("INSERT INTO tags (guild_id, name, content, author) VALUES (?, ?, ?, ?)",
                                  (ctx.guild.id, nom.lower(), contenu, ctx.author.id))
        await self.bot.db.commit()
        await ctx.reply(embed=ok(f"Tag `{nom}` créé."), mention_author=False)

    @tag.command(name="delete", description="Supprime un tag existant.")
    @commands.has_guild_permissions(manage_messages=True)
    async def tag_delete(self, ctx: commands.Context, nom: str):
        await self.bot.db.execute("DELETE FROM tags WHERE guild_id = ? AND name = ?", (ctx.guild.id, nom.lower()))
        await self.bot.db.commit()
        await ctx.reply(embed=ok(f"Tag `{nom}` supprimé."), mention_author=False)


# ══════════════════════════════════════════════════════════════
#  9. COG — FUN
# ══════════════════════════════════════════════════════════════

HUG = ["serre fort", "câline", "étreint"]
SLAP = ["gifle", "claque", "tape"]
PAT = ["caresse", "tapote la tête de"]
JOKES = [
    "Pourquoi les plongeurs plongent-ils toujours en arrière ? Parce que sinon ils tombent dans le bateau.",
    "Que dit un informaticien quand il a froid ? « Il fait 0x10 degrés. »",
    "Un octet entre dans un bar. « Tu veux un verre ? » — « Non, j'attends mon bit. »",
]
TRIVIA = [
    ("Capitale de l'Australie ?", "canberra"),
    ("Combien de cordes a une guitare classique ?", "6"),
    ("Symbole chimique de l'or ?", "au"),
    ("Année de la chute du mur de Berlin ?", "1989"),
]


class Fun(commands.Cog):
    """Détente et jeux."""

    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="8ball", description="Pose une question à la boule magique et obtiens une réponse aléatoire.")
    async def ball8(self, ctx: commands.Context, question: str):
        answers = ["Oui.", "Non.", "Certainement.", "Probablement pas.", "Sans aucun doute.",
                   "Ça sent le non.", "Demande plus tard.", "Les astres sont flous.", "Évidemment."]
        await ctx.reply(embed=embed(title="🎱 " + question, description=f"**{random.choice(answers)}**",
                                    color=Palette.ACCENT), mention_author=False)

    @commands.hybrid_command(name="dice", aliases=["de"], description="Lance un ou plusieurs dés et affiche le résultat.")
    async def dice(self, ctx: commands.Context, faces: int = 6, quantite: int = 1):
        quantite = max(1, min(quantite, 20))
        rolls = [random.randint(1, max(2, faces)) for _ in range(quantite)]
        await ctx.reply(embed=embed(title="🎲 Lancers", description=" · ".join(f"`{r}`" for r in rolls),
                                    color=Palette.ACCENT, footer=f"Total : {sum(rolls)}"), mention_author=False)

    @commands.hybrid_command(name="coinflip", aliases=["flip"], description="Lance une pièce virtuelle (Pile ou Face).")
    async def coinflip(self, ctx: commands.Context):
        await ctx.reply(embed=embed(title="🪙", description=f"**{random.choice(['Pile', 'Face'])}**",
                                    color=Palette.ACCENT), mention_author=False)

    @commands.hybrid_command(name="choose", description="Choisit une option au hasard parmi celles que tu fournis (séparées par des virgules).")
    async def choose(self, ctx: commands.Context, options: str = None):
        opts_list = [o.strip() for o in options.split(",")] if options else []
        
        if len(opts_list) < 2:
            return await ctx.reply("Donne au moins deux options séparées par une virgule (ex: `pizza, burger`).", mention_author=False)
            
        await ctx.reply(embed=embed(title="🤔 Choix", description=f"**{random.choice(opts_list)}**",
                                    color=Palette.ACCENT), mention_author=False)

    @commands.hybrid_command(name="rps", description="Joue à Pierre-Feuille-Ciseaux contre le bot.")
    async def rps(self, ctx: commands.Context, choix: str):
        choix = choix.lower()
        mapping = {"pierre": "🪨", "feuille": "📄", "ciseaux": "✂️"}
        if choix not in mapping:
            return await ctx.reply("Choisis : pierre, feuille ou ciseaux.", mention_author=False)
        bot_choice = random.choice(list(mapping))
        beats = {"pierre": "ciseaux", "feuille": "pierre", "ciseaux": "feuille"}
        result = "Égalité !" if choix == bot_choice else ("Tu gagnes !" if beats[choix] == bot_choice else "Tu perds !")
        await ctx.reply(embed=embed(title="✂️ Pierre-feuille-ciseaux",
                                    description=f"Toi : {mapping[choix]}\nBot : {mapping[bot_choice]}\n\n**{result}**",
                                    color=Palette.ACCENT), mention_author=False)

    @commands.hybrid_command(name="ship", description="Calcule le pourcentage d'amour entre deux personnes (ou deux noms).")
    async def ship(self, ctx: commands.Context, premier: str, second: str = None):
        second = second or ctx.author.display_name
        pct = random.randint(0, 100)
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        await ctx.reply(embed=embed(title=f"💞 {premier} × {second}", description=f"`{bar}` **{pct}%**",
                                    color=Palette.PRIMARY), mention_author=False)

    @commands.hybrid_command(name="hug", description="Fais un câlin virtuel à quelqu'un (ou à toi-même).")
    async def hug(self, ctx: commands.Context, membre: discord.Member = None):
        await ctx.reply(f"{ctx.author.mention} **{random.choice(HUG)}** {(membre or ctx.author).mention} 🤗",
                        mention_author=False)

    @commands.hybrid_command(name="slap", description="Gifle virtuellement quelqu'un (ou toi-même).")
    async def slap(self, ctx: commands.Context, membre: discord.Member = None):
        await ctx.reply(f"{ctx.author.mention} **{random.choice(SLAP)}** {(membre or ctx.author).mention} 👋",
                        mention_author=False)

    @commands.hybrid_command(name="pat", description="Caresse la tête de quelqu'un (ou de toi-même).")
    async def pat(self, ctx: commands.Context, membre: discord.Member = None):
        await ctx.reply(f"{ctx.author.mention} **{random.choice(PAT)}** {(membre or ctx.author).mention} 🥰",
                        mention_author=False)

    @commands.hybrid_command(name="reverse", description="Inverse le texte que tu fournis (écrit à l'envers).")
    async def reverse(self, ctx: commands.Context, texte: str):
        await ctx.reply(texte[::-1], mention_author=False)

    @commands.hybrid_command(name="mock", description="Transforme ton texte en MoCkEy (mAjUsCuLeS eT mInUsCuLeS aLtErNéS).")
    async def mock(self, ctx: commands.Context, texte: str):
        await ctx.reply("".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(texte)), mention_author=False)

    @commands.hybrid_command(name="joke", aliases=["blague"], description="Raconte une blague aléatoire (parfois nulle, on prévient).")
    async def joke(self, ctx: commands.Context):
        await ctx.reply(embed=embed(title="😂 Blague", description=random.choice(JOKES), color=Palette.WARNING),
                        mention_author=False)

    @commands.hybrid_command(name="slots", description="Joue à la machine à sous (aucun argent réel, promis).")
    async def slots(self, ctx: commands.Context):
        symbols = ["🍒", "🍋", "🍊", "🔔", "💎", "7️⃣"]
        result = [random.choice(symbols) for _ in range(3)]
        gain = "🎉 **Jackpot !**" if len(set(result)) == 1 else (
            "💸 Petite victoire" if len(set(result)) == 2 else "😐 Rien")
        await ctx.reply(embed=embed(title="🎰 Machine à sous", description=f"## {' '.join(result)}\n{gain}",
                                    color=Palette.WARNING), mention_author=False)

    @commands.hybrid_command(name="trivia", description="Pose une question de culture générale avec la réponse cachée.")
    async def trivia(self, ctx: commands.Context):
        question, reponse = random.choice(TRIVIA)
        await ctx.reply(embed=embed(title="❓ Trivia", description=f"{question}\n\n||{reponse}||",
                                    color=Palette.ACCENT), mention_author=False)


# ══════════════════════════════════════════════════════════════
#  10. COG — NIVEAUX
# ══════════════════════════════════════════════════════════════

class Levels(commands.Cog):
    """Progression et classement."""

    def __init__(self, bot) -> None:
        self.bot = bot
        self._cooldowns: dict[tuple[int, int], float] = {}
        self.rewards: dict[int, dict[int, int]] = {}

    @staticmethod
    def xp_for(level: int) -> int:
        return 5 * (level ** 2) + 50 * level + 100

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot or not message.content:
            return
        s = self.bot.settings
        if not s.raw(message.guild.id, "levels_enabled"):
            return
        key = (message.guild.id, message.author.id)
        now = time.time()
        if now - self._cooldowns.get(key, 0) < s.raw(message.guild.id, "levels_cooldown", 60):
            return
        self._cooldowns[key] = now
        await self._add_xp(message.guild, message.author,
                           random.randint(s.raw(message.guild.id, "levels_xp_min", 15),
                                          s.raw(message.guild.id, "levels_xp_max", 25)))

    async def _add_xp(self, guild, member, amount: int) -> None:
        row = await self.bot.db.fetchone("SELECT xp, level FROM members WHERE guild_id = ? AND user_id = ?",
                                         (guild.id, member.id))
        xp, level = (row["xp"], row["level"]) if row else (0, 0)
        xp += amount
        await self.bot.db.execute(
            "INSERT INTO members (guild_id, user_id, xp, level, messages) VALUES (?, ?, ?, ?, 1) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = ?, messages = messages + 1",
            (guild.id, member.id, xp, level, xp))
        new_level = level
        while xp >= self.xp_for(new_level):
            new_level += 1
        if new_level > level:
            await self.bot.db.execute("UPDATE members SET level = ? WHERE guild_id = ? AND user_id = ?",
                                      (new_level, guild.id, member.id))
        await self.bot.db.commit()
        if new_level > level:
            await self._level_up(guild, member, new_level)

    async def _level_up(self, guild, member, level: int) -> None:
        text = self.bot.settings.raw(guild.id, "levels_message").format(user=member.mention, level=level, guild=guild.name)
        cid = self.bot.settings.raw(guild.id, "levels_channel")
        channel = guild.get_channel(cid) if cid else None
        if channel:
            try:
                await channel.send(embed=embed(description=text, color=Palette.SUCCESS, footer="Progression"))
            except discord.HTTPException:
                pass
        role_id = self.rewards.get(guild.id, {}).get(level)
        if role_id and (role := guild.get_role(role_id)):
            try:
                await member.add_roles(role, reason=f"récompense niveau {level}")
            except discord.HTTPException:
                pass

    @commands.hybrid_command(name="rank", aliases=["niveau", "level"], description="Affiche ta progression (niveau, XP, messages) sur le serveur.")
    @commands.guild_only()
    async def rank(self, ctx: commands.Context, membre: discord.Member = None):
        m = membre or ctx.author
        row = await self.bot.db.fetchone("SELECT xp, level, messages FROM members WHERE guild_id = ? AND user_id = ?",
                                         (ctx.guild.id, m.id))
        if not row:
            return await ctx.reply(embed=err(f"**{m}** n'a pas encore d'XP."), mention_author=False)
        need = self.xp_for(row["level"])
        before = self.xp_for(row["level"] - 1) if row["level"] else 0
        progress = int(((row["xp"] - before) / max(1, need - before)) * 20)
        e = embed(title=f"📈 {m.display_name}", color=Palette.SUCCESS, thumbnail=m.display_avatar.url)
        e.description = f"`{'█' * progress}{'░' * (20 - progress)}`"
        e.add_field(name="Niveau", value=f"`{row['level']}`")
        e.add_field(name="XP", value=f"`{row['xp']}` / `{need}`")
        e.add_field(name="Messages", value=f"`{row['messages']}`")
        await ctx.reply(embed=e, mention_author=False)

    @commands.hybrid_command(name="leaderboard", aliases=["top", "classement"], description="Affiche le classement des membres les plus actifs (XP) du serveur.")
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.Context):
        rows = await self.bot.db.fetchall(
            "SELECT user_id, xp, level FROM members WHERE guild_id = ? ORDER BY xp DESC LIMIT 15", (ctx.guild.id,))
        if not rows:
            return await ctx.reply(embed=err("Aucune donnée."), mention_author=False)
        medals = ["🥇", "🥈", "🥉"]
        lines = [f"{medals[i] if i < 3 else f'`#{i + 1}`'} <@{r['user_id']}> — niveau `{r['level']}` · `{r['xp']} xp`"
                 for i, r in enumerate(rows)]
        await ctx.reply(embed=embed(title=f"🏆 Classement de {ctx.guild.name}", description="\n".join(lines),
                                    color=Palette.WARNING), mention_author=False)

    @commands.hybrid_command(name="setxp", description="Définit manuellement l'XP d'un membre (réservé aux administrateurs).")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def setxp(self, ctx: commands.Context, membre: discord.Member, xp: int):
        level = 0
        while xp >= self.xp_for(level):
            level += 1
        await self.bot.db.execute(
            "INSERT INTO members (guild_id, user_id, xp, level) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = ?, level = ?",
            (ctx.guild.id, membre.id, xp, level, xp, level))
        await self.bot.db.commit()
        await ctx.reply(embed=ok(f"XP de **{membre}** défini à `{xp}`."), mention_author=False)

    @commands.hybrid_command(name="resetxp", description="Réinitialise l'XP d'un membre (ou de tout le serveur si aucun membre n'est précisé).")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def resetxp(self, ctx: commands.Context, membre: discord.Member = None):
        if membre:
            await self.bot.db.execute("DELETE FROM members WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, membre.id))
        else:
            await self.bot.db.execute("DELETE FROM members WHERE guild_id = ?", (ctx.guild.id,))
        await self.bot.db.commit()
        await ctx.reply(embed=ok("XP réinitialisé."), mention_author=False)

    @commands.hybrid_command(name="reward", description="Lie un rôle à un niveau spécifique (récompense automatique).")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def reward(self, ctx: commands.Context, niveau: int, role: discord.Role = None):
        if role is None:
            self.rewards.setdefault(ctx.guild.id, {}).pop(niveau, None)
        else:
            self.rewards.setdefault(ctx.guild.id, {})[niveau] = role.id
        current = self.rewards.get(ctx.guild.id, {})
        desc = "\n".join(f"niveau `{l}` → <@&{r}>" for l, r in sorted(current.items())) or "*aucune*"
        await ctx.reply(embed=ok(f"Récompenses actuelles :\n{desc}"), mention_author=False)


# ══════════════════════════════════════════════════════════════
#  11. COG — LOGS
# ══════════════════════════════════════════════════════════════

class Logs(commands.Cog):
    """Logs d'audit dans un salon dédié."""

    def __init__(self, bot) -> None:
        self.bot = bot

    async def emit(self, guild, key: str, *, title: str, description: str, color: int = Palette.NEUTRAL) -> None:
        s = self.bot.settings
        if not s.raw(guild.id, "logs_enabled") or not s.raw(guild.id, key):
            return
        cid = s.raw(guild.id, "logs_channel")
        channel = guild.get_channel(cid) if cid else None
        if not channel:
            return
        try:
            await channel.send(embed=embed(title=title, description=description, color=color, footer="Logs"))
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        await self.emit(message.guild, "logs_messages", title="🗑️ Message supprimé",
                        description=f"**Auteur :** {message.author.mention}\n**Salon :** {message.channel.mention}\n"
                                    f"**Contenu :**\n{message.content[:1500] or '*vide*'}", color=Palette.DANGER)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if not before.guild or before.author.bot or before.content == after.content:
            return
        await self.emit(before.guild, "logs_messages", title="✏️ Message édité",
                        description=f"**Auteur :** {before.author.mention}\n**Avant :**\n{before.content[:700]}\n"
                                    f"**Après :**\n{after.content[:700]}", color=Palette.WARNING)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await self.emit(member.guild, "logs_members", title="📥 Arrivée",
                        description=f"{member.mention} (`{member.id}`)", color=Palette.SUCCESS)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await self.emit(member.guild, "logs_members", title="📤 Départ",
                        description=f"**{member}** (`{member.id}`)", color=Palette.DANGER)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if before.nick != after.nick:
            await self.emit(after.guild, "logs_members", title="📝 Pseudonyme",
                            description=f"{after.mention} : `{before.nick}` → `{after.nick}`")
        for role in set(after.roles) - set(before.roles):
            await self.emit(after.guild, "logs_members", title="➕ Rôle ajouté",
                            description=f"{after.mention} → {role.mention}", color=Palette.SUCCESS)
        for role in set(before.roles) - set(after.roles):
            await self.emit(after.guild, "logs_members", title="➖ Rôle retiré",
                            description=f"{after.mention} → {role.mention}", color=Palette.WARNING)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        await self.emit(role.guild, "logs_roles", title="🎭 Rôle créé", description=f"{role.mention} (`{role.id}`)")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        await self.emit(role.guild, "logs_roles", title="🎭 Rôle supprimé",
                        description=f"`{role.name}` (`{role.id}`)", color=Palette.DANGER)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        await self.emit(channel.guild, "logs_channels", title="📁 Salon créé", description=channel.mention)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        await self.emit(channel.guild, "logs_channels", title="📁 Salon supprimé",
                        description=f"`{channel.name}`", color=Palette.DANGER)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after) -> None:
        if before.channel == after.channel:
            return
        if after.channel and not before.channel:
            text = f"{member.mention} a rejoint `{after.channel.name}`"
        elif before.channel and not after.channel:
            text = f"{member.mention} a quitté `{before.channel.name}`"
        else:
            text = f"{member.mention} : `{before.channel.name}` → `{after.channel.name}`"
        await self.emit(member.guild, "logs_voice", title="🔊 Vocal", description=text)


# ══════════════════════════════════════════════════════════════
#  12. COG — ARRIVÉES / DÉPARTS / AUTOMOD / VOCAL TEMP
# ══════════════════════════════════════════════════════════════

class Events(commands.Cog):
    """Arrivées, départs, autorole, automod et vocal temporaire."""

    def __init__(self, bot) -> None:
        self.bot = bot
        self._spam: dict[tuple[int, int], list[float]] = {}
        self._tempvoice: set[int] = set()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        s = self.bot.settings
        gid = member.guild.id
        if s.raw(gid, "welcome_enabled"):
            cid = s.raw(gid, "welcome_channel")
            if cid and (channel := member.guild.get_channel(cid)):
                text = s.raw(gid, "welcome_message").format(user=member.mention, mention=member.mention,
                                                            guild=member.guild.name, count=member.guild.member_count)
                try:
                    if s.raw(gid, "welcome_embed"):
                        await channel.send(embed=embed(title="👋 Bienvenue", description=text,
                                                       color=Palette.SUCCESS, thumbnail=member.display_avatar.url))
                    else:
                        await channel.send(text)
                except discord.HTTPException:
                    pass
        if s.raw(gid, "autorole_enabled"):
            key = "botrole_id" if member.bot else "autorole_id"
            if (rid := s.raw(gid, key)) and (role := member.guild.get_role(rid)):
                try:
                    await member.add_roles(role, reason="autorole")
                except discord.HTTPException:
                    pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        s = self.bot.settings
        gid = member.guild.id
        if not s.raw(gid, "goodbye_enabled"):
            return
        cid = s.raw(gid, "goodbye_channel")
        if cid and (channel := member.guild.get_channel(cid)):
            text = s.raw(gid, "goodbye_message").format(user=str(member), mention=member.mention,
                                                        guild=member.guild.name, count=member.guild.member_count)
            try:
                await channel.send(embed=embed(title="👋 Départ", description=text, color=Palette.DANGER))
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        s = self.bot.settings
        gid = message.guild.id
        if not s.raw(gid, "automod_enabled"):
            return
        if message.channel.permissions_for(message.author).manage_messages:
            return

        content = message.content
        reason = None
        if s.raw(gid, "automod_invites") and "discord.gg/" in content:
            reason = "invitation Discord"
        elif s.raw(gid, "automod_links") and re.search(r"https?://", content):
            reason = "lien externe"
        elif s.raw(gid, "automod_caps") and len(content) > 8 and content.isupper():
            reason = "majuscules"
        elif s.raw(gid, "automod_mentions") and len(message.mentions) > 5:
            reason = "mentions massives"
        elif (bad := s.raw(gid, "automod_badwords")) and any(
                w.strip().lower() in content.lower() for w in bad.split(",") if w.strip()):
            reason = "mot interdit"
        elif s.raw(gid, "automod_spam"):
            key = (gid, message.author.id)
            now = time.time()
            stamps = [t for t in self._spam.get(key, []) if now - t < 5]
            stamps.append(now)
            self._spam[key] = stamps
            if len(stamps) >= 6:
                reason = "spam"

        if reason:
            try:
                await message.delete()
                notice = await message.channel.send(embed=warn(f"{message.author.mention} — `{reason}`",
                                                               title="Auto-modération"))
                await asyncio.sleep(4)
                await notice.delete()
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after) -> None:
        s = self.bot.settings
        gid = member.guild.id
        if not s.raw(gid, "tempvoice_enabled"):
            return
        hub = s.raw(gid, "tempvoice_hub")
        if after.channel and hub and after.channel.id == hub:
            try:
                channel = await member.guild.create_voice_channel(
                    f"🔊 {member.display_name}"[:100], category=after.channel.category,
                    reason="vocal temporaire")
                self._tempvoice.add(channel.id)
                await member.move_to(channel)
            except discord.HTTPException:
                pass
        if before.channel and before.channel.id in self._tempvoice and not before.channel.members:
            self._tempvoice.discard(before.channel.id)
            try:
                await before.channel.delete(reason="vocal temporaire vide")
            except discord.HTTPException:
                pass


# ══════════════════════════════════════════════════════════════
#  13. COG — TICKETS
# ══════════════════════════════════════════════════════════════

class TicketPanel(discord.ui.View):
    def __init__(self, bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Ouvrir un ticket", emoji="🎫", style=discord.ButtonStyle.success,
                       custom_id="ticket:open")
    async def open_ticket(self, i: discord.Interaction, _):
        guild, s = i.guild, i.client.settings
        existing = await i.client.db.fetchone(
            "SELECT channel_id FROM tickets WHERE guild_id = ? AND author_id = ?", (guild.id, i.user.id))
        if existing and (ch := guild.get_channel(existing["channel_id"])):
            return await i.response.send_message(f"Tu as déjà un ticket : {ch.mention}", ephemeral=True)
        await i.response.defer(ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            i.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }
        staff_id = s.raw(guild.id, "tickets_staff")
        if staff_id and (staff := guild.get_role(staff_id)):
            overwrites[staff] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        cat_id = s.raw(guild.id, "tickets_category")
        channel = await guild.create_text_channel(
            f"ticket-{i.user.name}"[:100], overwrites=overwrites,
            category=guild.get_channel(cat_id) if cat_id else None,
            topic=f"Ticket de {i.user} ({i.user.id})")
        await i.client.db.execute("INSERT INTO tickets (channel_id, guild_id, author_id, opened_at) VALUES (?, ?, ?, ?)",
                                  (channel.id, guild.id, i.user.id, int(time.time())))
        await i.client.db.commit()
        await channel.send(content=i.user.mention + (f" <@&{staff_id}>" if staff_id else ""),
                           embed=embed(title="🎫 Ticket ouvert",
                                       description="Décris ton problème. `.ticket close` pour fermer.",
                                       color=Palette.SUCCESS), view=TicketControl(self.bot))
        await i.followup.send(f"Ticket créé : {channel.mention}", ephemeral=True)


class TicketControl(discord.ui.View):
    def __init__(self, bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Fermer", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="ticket:close")
    async def close(self, i: discord.Interaction, _):
        await self.bot.get_cog("Tickets").close_ticket(i.channel, i.user)


class Tickets(commands.Cog):
    """Support par tickets privés."""

    def __init__(self, bot) -> None:
        self.bot = bot
        bot.add_view(TicketPanel(bot))
        bot.add_view(TicketControl(bot))

    @commands.hybrid_group(name="ticket", description="Gestion des tickets", invoke_without_command=True)
    @commands.guild_only()
    async def ticket(self, ctx: commands.Context):
        await ctx.reply(embed=embed(title="🎫 Tickets",
                                    description="`.ticket panel` · `!ticket add <membre>` · `!ticket close`",
                                    color=Palette.PRIMARY), mention_author=False)

    @ticket.command(name="panel", description="Publie le panneau de ticket personnalisé.")
    @commands.has_guild_permissions(manage_guild=True)
    async def panel(self, ctx: commands.Context):
        text = self.bot.settings.raw(ctx.guild.id, "tickets_panel_description")
        image_url = self.bot.settings.raw(ctx.guild.id, "tickets_panel_image")
        
        e = embed(
                title="🎫 Support",
                description=text,
                color=Palette.PRIMARY,
                footer=f"{BOT_NAME} • Tickets",
                image=image_url
            )
        
        await ctx.send(embed=e, view=TicketPanel(self.bot))
        
    @ticket.command(name="setup", description="Ouvre le panneau interactif pour configurer les tickets.")
    @commands.has_guild_permissions(manage_guild=True)
    async def setup(self, ctx: commands.Context):
        view = TicketSetupView(self.bot, ctx.author, ctx.guild)
        await ctx.send(embed=view.build_embed(), view=view, ephemeral=True)

    @ticket.command(name="add", description="Ajoute un membre au ticket")
    async def add(self, ctx: commands.Context, membre: discord.Member):
        await ctx.channel.set_permissions(membre, read_messages=True, send_messages=True)
        await ctx.reply(embed=ok(f"{membre.mention} ajouté au ticket."), mention_author=False)

    @ticket.command(name="remove", description="Retire un membre du ticket")
    async def remove(self, ctx: commands.Context, membre: discord.Member):
        await ctx.channel.set_permissions(membre, overwrite=None)
        await ctx.reply(embed=ok(f"{membre.mention} retiré du ticket."), mention_author=False)

    @ticket.command(name="rename", description="Renomme le ticket")
    async def rename(self, ctx: commands.Context, nom: str):
        await ctx.channel.edit(name=nom[:100])
        await ctx.reply(embed=ok("Ticket renommé."), mention_author=False)

    @ticket.command(name="claim", description="Réclame le ticket")
    async def claim(self, ctx: commands.Context):
        await self.bot.db.execute("UPDATE tickets SET claimed_by = ? WHERE channel_id = ?",
                                  (ctx.author.id, ctx.channel.id))
        await self.bot.db.commit()
        await ctx.reply(embed=ok(f"Ticket réclamé par {ctx.author.mention}."), mention_author=False)

    @ticket.command(name="close", description="Ferme le ticket")
    async def close(self, ctx: commands.Context):
        await self.close_ticket(ctx.channel, ctx.author)

    async def close_ticket(self, channel: discord.TextChannel, closer) -> None:
        row = await self.bot.db.fetchone("SELECT * FROM tickets WHERE channel_id = ?", (channel.id,))
        await channel.send(embed=embed(description=f"🔒 Ticket fermé par {closer.mention}. Suppression dans 5s…",
                                       color=Palette.DANGER))
        if row:
            log_id = self.bot.settings.raw(channel.guild.id, "tickets_logs")
            if log_id and (log := channel.guild.get_channel(log_id)):
                try:
                    await log.send(embed=embed(title=f"📄 Ticket {channel.name}",
                                               description=f"Auteur : <@{row['author_id']}>\n"
                                                           f"Fermé par : {closer.mention}", color=Palette.NEUTRAL))
                except discord.HTTPException:
                    pass
            await self.bot.db.execute("DELETE FROM tickets WHERE channel_id = ?", (channel.id,))
            await self.bot.db.commit()
        await asyncio.sleep(5)
        try:
            await channel.delete(reason="ticket fermé")
        except discord.HTTPException:
            pass


# ══════════════════════════════════════════════════════════════
#  14. COG — GIVEAWAYS
# ══════════════════════════════════════════════════════════════

class GiveawayButton(discord.ui.View):
    def __init__(self, bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Participer", emoji="🎉", style=discord.ButtonStyle.success, custom_id="gw:join")
    async def join(self, i: discord.Interaction, _):
        mid = i.message.id
        exists = await i.client.db.fetchone("SELECT 1 FROM gw_entries WHERE message_id = ? AND user_id = ?",
                                            (mid, i.user.id))
        if exists:
            await i.client.db.execute("DELETE FROM gw_entries WHERE message_id = ? AND user_id = ?", (mid, i.user.id))
            await i.client.db.commit()
            return await i.response.send_message("Participation retirée.", ephemeral=True)
        await i.client.db.execute("INSERT INTO gw_entries (message_id, user_id) VALUES (?, ?)", (mid, i.user.id))
        await i.client.db.commit()
        row = await i.client.db.fetchone("SELECT COUNT(*) AS c FROM gw_entries WHERE message_id = ?", (mid,))
        await i.response.send_message(f"Participation enregistrée ! ({row['c']} participants)", ephemeral=True)


class Giveaways(commands.Cog):
    """Concours automatiques."""

    def __init__(self, bot) -> None:
        self.bot = bot
        bot.add_view(GiveawayButton(bot))

    async def cog_load(self) -> None:
        self.checker.start()

    def cog_unload(self) -> None:
        self.checker.cancel()

    @tasks.loop(seconds=15)
    async def checker(self) -> None:
        rows = await self.bot.db.fetchall("SELECT message_id FROM giveaways WHERE ended = 0 AND ends_at <= ?",
                                          (int(time.time()),))
        for row in rows:
            await self.finish(row["message_id"])

    @checker.before_loop
    async def _before(self) -> None:
        await self.bot.wait_until_ready()

    async def finish(self, message_id: int) -> None:
        row = await self.bot.db.fetchone("SELECT * FROM giveaways WHERE message_id = ?", (message_id,))
        if not row or row["ended"]:
            return
        await self.bot.db.execute("UPDATE giveaways SET ended = 1 WHERE message_id = ?", (message_id,))
        await self.bot.db.commit()
        entries = await self.bot.db.fetchall("SELECT user_id FROM gw_entries WHERE message_id = ?", (message_id,))
        pool = [e["user_id"] for e in entries]
        winners = random.sample(pool, min(row["winners"], len(pool))) if pool else []
        text = f"**Gagnant(s) :** {' '.join(f'<@{w}>' for w in winners)}" if winners else "**Aucun participant.**"
        channel = self.bot.get_channel(row["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(message_id)
                await msg.edit(embed=embed(title=f"🎁 {row['prize']}", description=f"Terminé !\n{text}",
                                           color=Palette.SUCCESS, footer="Giveaway terminé"), view=None)
                if winners:
                    await channel.send(f"🎉 Félicitations {' '.join(f'<@{w}>' for w in winners)} — "
                                       f"tu gagnes **{row['prize']}** !")
            except discord.HTTPException:
                pass

    @commands.hybrid_command(name="gwstart", description="Lance un giveaway (concours) avec une durée, un nombre de gagnants et un prix.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def gwstart(self, ctx: commands.Context, duree: Duration, gagnants: int, prix: str):
        e = embed(title=f"🎁 {prix}",
                  description=f"Clique sur **Participer** !\n"
                              f"Fin : {discord.utils.format_dt(discord.utils.utcnow() + timedelta(seconds=duree), 'R')}\n"
                              f"Gagnants : `{gagnants}`", color=Palette.WARNING, footer=f"Organisé par {ctx.author}")
        msg = await ctx.send(embed=e, view=GiveawayButton(self.bot))
        await self.bot.db.execute(
            "INSERT INTO giveaways (message_id, channel_id, guild_id, prize, winners, host, ends_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg.id, ctx.channel.id, ctx.guild.id, prix, gagnants, ctx.author.id, int(time.time()) + duree))
        await self.bot.db.commit()
        await ctx.message.add_reaction("🎉")

    @commands.hybrid_command(name="gwend", description="Termine immédiatement un giveaway en cours avant sa date de fin.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def gwend(self, ctx: commands.Context, message_id: int):
        await self.finish(message_id)
        await ctx.reply(embed=ok("Giveaway terminé."), mention_author=False)

    @commands.hybrid_command(name="gwreroll", description="Tire un nouveau gagnant au hasard pour un giveaway déjà terminé.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def gwreroll(self, ctx: commands.Context, message_id: int):
        entries = await self.bot.db.fetchall("SELECT user_id FROM gw_entries WHERE message_id = ?", (message_id,))
        if not entries:
            return await ctx.reply(embed=err("Aucun participant."), mention_author=False)
        await ctx.reply(embed=ok(f"Nouveau gagnant : <@{random.choice([e['user_id'] for e in entries])}>"),
                        mention_author=False)

    @commands.hybrid_command(name="gwlist", description="Affiche la liste des giveaways actuellement en cours sur le serveur.")
    @commands.guild_only()
    async def gwlist(self, ctx: commands.Context):
        rows = await self.bot.db.fetchall("SELECT * FROM giveaways WHERE guild_id = ? AND ended = 0", (ctx.guild.id,))
        if not rows:
            return await ctx.reply(embed=err("Aucun giveaway actif."), mention_author=False)
        lines = [f"`{r['message_id']}` — **{r['prize']}** — fin <t:{r['ends_at']}:R>" for r in rows]
        await ctx.reply(embed=embed(title="🎁 Giveaways actifs", description="\n".join(lines),
                                    color=Palette.WARNING), mention_author=False)


# ══════════════════════════════════════════════════════════════
#  15. COG — INFO + PROPRIÉTAIRE
# ══════════════════════════════════════════════════════════════

class Info(commands.Cog):
    """État, statistiques et maintenance."""

    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="botinfo", aliases=["stats", "about"], description="Affiche les statistiques du bot (serveurs, membres, latence, uptime, etc.).")
    async def botinfo(self, ctx: commands.Context):
        e = embed(title=f"🤖 {BOT_NAME}", color=Palette.PRIMARY, thumbnail=self.bot.user.display_avatar.url)
        e.add_field(name="Serveurs", value=f"`{len(self.bot.guilds)}`")
        e.add_field(name="Membres", value=f"`{sum(g.member_count or 0 for g in self.bot.guilds)}`")
        e.add_field(name="Commandes", value=f"`{len(self.bot.commands)}`")
        e.add_field(name="Utilisées", value=f"`{self.bot.commands_used}`")
        e.add_field(name="Latence", value=f"`{round(self.bot.latency * 1000)} ms`")
        e.add_field(name="Uptime", value=f"<t:{int(self.bot.launch_time)}:R>")
        e.add_field(name="Python", value=f"`{platform.python_version()}`")
        e.add_field(name="discord.py", value=f"`{discord.__version__}`")
        await ctx.reply(embed=e, mention_author=False)

    @commands.hybrid_command(name="socials", description="Affiche les liens utiles (site web, documentation, etc.).")
    async def socials(self, ctx: commands.Context):
        await ctx.reply(embed=embed(title="🔗 Liens", color=Palette.PRIMARY, description=(
            "[Venice.ai](https://venice.ai)\n"
            "[Documentation discord.py](https://discordpy.readthedocs.io)\n"
            "[Portail développeur Discord](https://discord.com/developers/applications)")), mention_author=False)

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, scope: str = "global"):
        await ctx.typing()
        if scope == "global":
            await self.bot.tree.sync()
        else:
            self.bot.tree.copy_global_to(guild=ctx.guild)
            await self.bot.tree.sync(guild=ctx.guild)
        await ctx.reply(embed=ok(f"Slash commands synchronisées ({scope})."), mention_author=False)

    @commands.command(name="reload")
    @commands.is_owner()
    async def reload(self, ctx: commands.Context):
        for name in list(self.bot.cogs):
            await self.bot.remove_cog(name)
        await self.bot.load_cogs()
        await ctx.reply(embed=ok(f"{len(self.bot.cogs)} cogs rechargées."), mention_author=False)

    @commands.command(name="eval", aliases=["ev"])
    @commands.is_owner()
    async def eval_(self, ctx: commands.Context, *, code: str):
        code = code.strip("`").replace("py\n", "", 1)
        try:
            result = eval(code, {"bot": self.bot, "ctx": ctx, "discord": discord, "commands": commands, "sys": sys})
            if hasattr(result, "__await__"):
                result = await result
            await ctx.reply(embed=embed(title="🧠 Eval", description=f"```py\n{result}\n```", color=Palette.SUCCESS),
                            mention_author=False)
        except Exception as exc:
            await ctx.reply(embed=err(f"```py\n{type(exc).__name__}: {exc}\n```"), mention_author=False)

    @commands.command(name="shutdown", aliases=["stop"])
    @commands.is_owner()
    async def shutdown(self, ctx: commands.Context):
        await ctx.reply(embed=ok("Arrêt en cours…"), mention_author=False)
        await self.bot.close()


# ══════════════════════════════════════════════════════════════
#  16. COG — PROPRIÉTAIRE (OWNER)
# ══════════════════════════════════════════════════════════════

class Owner(commands.Cog):
    """Gestion des accès au bot."""

    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="owner", description="Ajoute ou retire un utilisateur de la liste des Owners du bot.")
    @commands.is_owner()
    async def owner(self, ctx: commands.Context, action: str = None, user: discord.User = None):
        if action is None or user is None:
            return await ctx.reply(embed=err("Usage: `.owner add <membre>` ou `.owner remove <membre>`"), mention_author=False)
        
        if action.lower() == "add":
            await self.bot.db.execute("INSERT OR IGNORE INTO bot_owners (user_id) VALUES (?)", (user.id,))
            await self.bot.db.commit()
            await ctx.reply(embed=ok(f"**{user}** a été ajouté aux Owners du bot."), mention_author=False)
        elif action.lower() == "remove":
            await self.bot.db.execute("DELETE FROM bot_owners WHERE user_id = ?", (user.id,))
            await self.bot.db.commit()
            await ctx.reply(embed=ok(f"**{user}** a été retiré des Owners du bot."), mention_author=False)
        else:
            await ctx.reply(embed=err("Action invalide. Utilise `add` ou `remove`."), mention_author=False)

    @commands.hybrid_command(name="ownerlist", description="Affiche la liste des Owners du bot.")
    @commands.is_owner()
    async def ownerlist(self, ctx: commands.Context):
        rows = await self.bot.db.fetchall("SELECT user_id FROM bot_owners")
        owners = [f"<@{r['user_id']}> (`{r['user_id']}`)" for r in rows]
        if not owners:
            return await ctx.reply(embed=info("Aucun Owner enregistré dans la base de données."), mention_author=False)
        
        e = embed(title="👑 Liste des Owners", description="\n".join(owners), color=Palette.WARNING)
        await ctx.reply(embed=e, mention_author=False)


# ══════════════════════════════════════════════════════════════
#  17. LE BOT
# ══════════════════════════════════════════════════════════════

COG_CLASSES = (Help, Config, Moderation, Utility, Fun, Levels, Logs, Events, Tickets, Giveaways, Info, Owner)

ACTIVITIES = [
    (f"{PREFIX}help — toutes les commandes", discord.ActivityType.listening),
    (f"{PREFIX}config — dashboard du serveur", discord.ActivityType.playing),
    ("{guilds} serveurs · {users} membres", discord.ActivityType.watching),
]


class VeniceBot(commands.AutoShardedBot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        intents.emojis_and_stickers = True
        intents.integrations = False
        intents.webhooks = False
        intents.invites = False
        intents.presences = False

        super().__init__(
            command_prefix=self.resolve_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True,
            strip_after_prefix=True,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True, replied_user=False),
            max_messages=750,
            chunk_guilds_at_startup=False,
            owner_ids=set(OWNER_IDS) or None,
            activity=discord.Game(name=f"{PREFIX}help"),
            status=discord.Status.online,
        )
        self.db = Database(BASE_DIR / DB_PATH)
        self.settings = Settings(self.db)
        self.launch_time = time.time()
        self.commands_used = 0
        self._activity_index = 0

    async def resolve_prefix(self, _bot, message: discord.Message):
        if message.guild is None:
            return commands.when_mentioned_or(PREFIX)(self, message)
        return commands.when_mentioned_or(self.settings.raw(message.guild.id, "prefix", PREFIX))(self, message)

    async def load_cogs(self) -> None:
        for cog in COG_CLASSES:
            try:
                await self.add_cog(cog(self))
            except Exception as exc:
                log.error("échec du chargement de %s : %r", cog.__name__, exc)

    async def setup_hook(self) -> None:
        await self.db.connect()
        await self.settings.load_all()
        await self.load_cogs()
        if DEV_GUILD:
            guild = discord.Object(id=DEV_GUILD)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("slash commands synchronisées sur le serveur de dev")

    async def on_ready(self) -> None:
        log.info("connecté : %s (%s) — %s serveurs", self.user, self.user.id, len(self.guilds))
        if not self.flush_settings.is_running():
            self.flush_settings.start()
        if not self.rotate_activity.is_running():
            self.rotate_activity.start()

    async def close(self) -> None:
        await self.settings.flush()
        await self.db.close()
        await super().close()

    @tasks.loop(seconds=30)
    async def flush_settings(self) -> None:
        await self.settings.flush()

    @tasks.loop(seconds=45)
    async def rotate_activity(self) -> None:
        label, kind = ACTIVITIES[self._activity_index % len(ACTIVITIES)]
        self._activity_index += 1
        label = label.format(guilds=len(self.guilds), users=sum(g.member_count or 0 for g in self.guilds))
        await self.change_presence(activity=discord.Activity(type=kind, name=label))

    async def on_command(self, _ctx) -> None:
        self.commands_used += 1

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        if isinstance(error, commands.CommandNotFound):
            close = difflib.get_close_matches((ctx.invoked_with or "").lower(), list(self.all_commands), n=3, cutoff=0.6)
            if close:
                await self._reply(ctx, err("Commande inconnue. Peut-être : " +
                                           ", ".join(f"`{ctx.clean_prefix}{c}`" for c in close)))
            return
        if isinstance(error, commands.MissingRequiredArgument):
            usage = f"{ctx.clean_prefix}{ctx.command.qualified_name} {ctx.command.signature}"
            return await self._reply(ctx, err(f"Argument manquant : `{error.param.name}`\n**Usage :** `{usage}`"))
        if isinstance(error, commands.BadArgument):
            return await self._reply(ctx, err(str(error)))
        if isinstance(error, commands.MissingPermissions):
            return await self._reply(ctx, err("Permissions requises : " +
                                              ", ".join(f"`{p}`" for p in error.missing_permissions)))
        if isinstance(error, commands.BotMissingPermissions):
            return await self._reply(ctx, err("Permissions manquantes au bot : " +
                                              ", ".join(f"`{p}`" for p in error.missing_permissions)))
        if isinstance(error, commands.CommandOnCooldown):
            return await self._reply(ctx, warn(f"Doucement ! Réessaie dans **{error.retry_after:.1f}s**."))
        if isinstance(error, commands.NotOwner):
            return await self._reply(ctx, err("Commande réservée au propriétaire du bot."))
        if isinstance(error, commands.NoPrivateMessage):
            return await self._reply(ctx, err("Commande utilisable uniquement sur un serveur."))
        if isinstance(error, commands.CheckFailure):
            return await self._reply(ctx, err("Tu n'as pas accès à cette commande."))
        if isinstance(error, discord.Forbidden):
            return await self._reply(ctx, err("Permission refusée par Discord. Vérifie la hiérarchie des rôles."))
        if isinstance(error, discord.HTTPException):
            return await self._reply(ctx, err(f"Erreur HTTP `{error.status}` — réessaie plus tard."))
        log.exception("erreur non gérée dans %s", ctx.command, exc_info=error)
        await self._reply(ctx, err(f"Erreur interne.\n```py\n{type(error).__name__}: {error}\n```"))

    async def _reply(self, ctx: commands.Context, e: discord.Embed) -> None:
        try:
            await ctx.reply(embed=e, mention_author=False, delete_after=15 if ctx.guild else None)
        except discord.HTTPException:
            pass


async def main() -> None:
    if not TOKEN or TOKEN.startswith("colle"):
        raise SystemExit("\n⛔ Aucun token.\n   Ouvre crinsa.py et remplis la ligne TOKEN = \"...\"\n")
    bot = VeniceBot()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("arrêt propre.")