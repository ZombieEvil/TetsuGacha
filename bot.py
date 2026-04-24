"""
TetsuGacha - bot Discord de gacha multi-sources.
Point d'entrée principal.

Lancement :
  python bot.py           → avec dashboard temps réel (défaut)
  python bot.py --no-ui   → logs classiques en ligne de commande
"""
import asyncio
import logging
import os
import sys
import os
import argparse

import discord
from discord.ext import commands, tasks

try:
    import config
except ImportError:
    print("❌  Fichier config.py introuvable.")
    print("    Renomme 'config.example.py' en 'config.py' et remplis ton token Discord.")
    sys.exit(1)

# Token sécurisé (lit d'abord la variable d'environnement Koyeb)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or config.DISCORD_TOKEN

from utils.storage import JSONStorage
from utils.api_fetchers import CharacterFetcher
from utils.dashboard import dashboard


# ============================================================
# LOGGING
# ============================================================
class DashboardLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            if record.levelno >= logging.ERROR:
                dashboard.log_error(msg)
            elif record.levelno >= logging.WARNING:
                dashboard.log_warn(msg)
            else:
                dashboard.log_info(msg)
        except Exception:
            pass


def setup_logging(use_dashboard: bool):
    root = logging.getLogger()
    root.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
    for h in list(root.handlers):
        root.removeHandler(h)

    if use_dashboard:
        handler = DashboardLogHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(handler)
    else:
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(stream)

    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)


log = logging.getLogger(config.BOT_NAME.lower())


# ============================================================
# BOT
# ============================================================
class TetsuGachaBot(commands.Bot):
    def __init__(self, use_dashboard: bool = True):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix=config.BOT_PREFIX, intents=intents,
                         help_command=None)

        self.use_dashboard = use_dashboard
        self.dashboard = dashboard

        self.db = JSONStorage(config.DATABASE_PATH)
        self.fetcher = CharacterFetcher(
            tmdb_key=getattr(config, "TMDB_API_KEY", "") or "",
            igdb_id=getattr(config, "IGDB_CLIENT_ID", "") or "",
            igdb_secret=getattr(config, "IGDB_CLIENT_SECRET", "") or "",
            comicvine_key=getattr(config, "COMICVINE_API_KEY", "") or "",
        )

    async def setup_hook(self):
        os.makedirs("data", exist_ok=True)

        log.info("Initialisation de la base de données…")
        await self.db.init()

        log.info("Démarrage des fetchers API…")
        await self.fetcher.start()

        cogs = [
            "cogs.config", "cogs.rolls", "cogs.collection",
            "cogs.wishlist", "cogs.trade", "cogs.profile", "cogs.help",
            "cogs.events", "cogs.shop",
        ]
        for ext in cogs:
            try:
                await self.load_extension(ext)
                log.info(f"Cog chargé · {ext}")
            except Exception as e:
                log.exception(f"Erreur chargement {ext} : {e}")

        log.info("Synchronisation des slash commands…")
        try:
            synced = await self.tree.sync()
            log.info(f"{len(synced)} slash commands synchronisées.")
        except Exception as e:
            log.exception(f"Erreur sync slash commands : {e}")

        if self.use_dashboard:
            self._dashboard_refresher.start()

    @tasks.loop(seconds=1.0)
    async def _dashboard_refresher(self):
        try:
            users = sum((g.member_count or 0) for g in self.guilds)
            self.dashboard.update_bot_info(
                name=str(self.user) if self.user else "…",
                latency_ms=int(self.latency * 1000) if self.latency and self.latency < 10 else 0,
                guilds=len(self.guilds),
                users=users,
            )
            for g in self.guilds:
                cfg = await self.db.get_guild_config(g.id)
                self.dashboard.update_mode(g.id, g.name, cfg.get("active_mode", "all"))
            self.dashboard.refresh()
        except Exception:
            pass

    async def on_ready(self):
        log.info(f"{config.BOT_NAME} connecté : {self.user}")
        log.info(f"Présent sur {len(self.guilds)} serveur(s)")
        await self.change_presence(activity=discord.Game(name="/roll · /help"))

    async def close(self):
        log.info("Fermeture…")
        if self._dashboard_refresher.is_running():
            self._dashboard_refresher.cancel()
        await self.fetcher.close()
        try:
            await self.db.close()
        except Exception:
            pass
        await super().close()


# ============================================================
# MAIN
# ============================================================
async def run_bot(use_dashboard: bool):
    bot = TetsuGachaBot(use_dashboard=use_dashboard)
    try:
        await bot.start(DISCORD_TOKEN)
    except discord.LoginFailure:
        log.error("Token Discord invalide.")
    finally:
        if not bot.is_closed():
            await bot.close()


def main():
    parser = argparse.ArgumentParser(description=f"{config.BOT_NAME} · bot Discord")
    parser.add_argument("--no-ui", action="store_true",
                        help="Désactive le dashboard temps réel")
    args = parser.parse_args()
    use_dashboard = not args.no_ui

    setup_logging(use_dashboard)

    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "METS_TON_TOKEN_DISCORD_ICI":
        print("❌  Token Discord manquant dans config.py")
        print("    Récupère ton token sur https://discord.com/developers/applications")
        return

    if use_dashboard:
        dashboard.start()
        dashboard.log_info(f"{config.BOT_NAME} démarre…")

    try:
        asyncio.run(run_bot(use_dashboard))
    except KeyboardInterrupt:
        pass
    finally:
        if use_dashboard:
            dashboard.stop()
            dashboard.print_farewell()


if __name__ == "__main__":
    main()
