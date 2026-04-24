"""
/event (admin uniquement) : déclenche des événements serveur
  - /event double_tokens durée_heures:X
  - /event limited_character durée_heures:X
  - /event stop id:X
  - /event list
"""
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import random

import config
from utils.helpers import (
    success_embed, error_embed, warning_embed, info_embed,
    build_character_embed, enrich_character, is_high_rarity,
)


class EventsCog(commands.GroupCog, name="event"):
    """Événements serveur."""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="double_tokens",
        description=f"Active un événement ×{config.EVENT_DOUBLE_TOKENS_MULTIPLIER:g} TetsuTokens"
    )
    @app_commands.describe(
        heures=f"Durée de l'événement en heures (max {config.EVENT_MAX_DURATION_HOURS})"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def double_tokens(self, interaction: discord.Interaction, heures: int):
        if heures <= 0 or heures > config.EVENT_MAX_DURATION_HOURS:
            await interaction.response.send_message(
                embed=error_embed(
                    f"La durée doit être entre 1 et {config.EVENT_MAX_DURATION_HOURS} heures."
                ),
                ephemeral=True,
            )
            return

        # Vérifier qu'il n'y a pas déjà un event double_tokens actif
        existing = await self.bot.db.get_active_event_by_type(
            interaction.guild.id, "double_tokens"
        )
        if existing:
            await interaction.response.send_message(
                embed=warning_embed(
                    f"Un événement **double tokens** est déjà actif (`#{existing['id']}`).\n"
                    f"Arrête-le d'abord avec `/event stop id:{existing['id']}`."
                ),
                ephemeral=True,
            )
            return

        ends_at = datetime.utcnow() + timedelta(hours=heures)
        eid = await self.bot.db.create_event(
            interaction.guild.id, "double_tokens",
            ends_at.isoformat(),
            data={"multiplier": config.EVENT_DOUBLE_TOKENS_MULTIPLIER},
        )

        embed = discord.Embed(
            title=f"🎉  Événement lancé  ·  Double TetsuTokens",
            description=(
                f"Tous les gains de {config.CURRENCY_NAME_LONG} sont "
                f"**×{config.EVENT_DOUBLE_TOKENS_MULTIPLIER:g}** pendant **{heures}h** !\n\n"
                f"*C'est le moment de farmer. Ramenez vos amis.*"
            ),
            color=config.BOT_ACCENT_COLOR,
        )
        embed.add_field(name="⏰ Fin", value=f"<t:{int(ends_at.timestamp())}:R>", inline=True)
        embed.add_field(name="🆔 ID", value=f"`#{eid}`", inline=True)
        embed.set_footer(text=f"{config.BOT_NAME} · Event lancé par {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="limited_character",
        description="Déclenche un event perso limité (chance boostée sur un perso rare)"
    )
    @app_commands.describe(
        heures=f"Durée en heures (max {config.EVENT_MAX_DURATION_HOURS})"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def limited_character(self, interaction: discord.Interaction, heures: int):
        if heures <= 0 or heures > config.EVENT_MAX_DURATION_HOURS:
            await interaction.response.send_message(
                embed=error_embed(
                    f"La durée doit être entre 1 et {config.EVENT_MAX_DURATION_HOURS} heures."
                ),
                ephemeral=True,
            )
            return

        existing = await self.bot.db.get_active_event_by_type(
            interaction.guild.id, "limited_character"
        )
        if existing:
            data = existing.get("data", {})
            char_name = data.get("character", {}).get("name", "?")
            await interaction.response.send_message(
                embed=warning_embed(
                    f"Un perso limité est déjà actif : **{char_name}** (`#{existing['id']}`).\n"
                    f"Arrête-le d'abord avec `/event stop id:{existing['id']}`."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        # Tirage aléatoire d'un perso RARE+ depuis AniList
        guild_cfg = await self.bot.db.get_guild_config(interaction.guild.id)
        mode = guild_cfg.get("active_mode", "all")

        chosen = None
        for _ in range(10):
            c = await self.bot.fetcher.get_random_character(mode=mode)
            if not c:
                continue
            c = enrich_character(c)
            if is_high_rarity(c["rarity"]):
                chosen = c
                break

        if not chosen:
            await interaction.followup.send(
                embed=error_embed(
                    "Impossible de trouver un perso suffisamment rare. Réessaie."
                ),
                ephemeral=True,
            )
            return

        # Vérifier qu'il n'est pas déjà claim
        already = await self.bot.db.is_character_claimed(
            interaction.guild.id, chosen["id"], chosen["source_type"]
        )
        if already:
            await interaction.followup.send(
                embed=warning_embed(
                    f"Le perso tiré (**{chosen['name']}**) est déjà revendiqué. "
                    f"Relance la commande."
                ),
                ephemeral=True,
            )
            return

        ends_at = datetime.utcnow() + timedelta(hours=heures)
        eid = await self.bot.db.create_event(
            interaction.guild.id, "limited_character",
            ends_at.isoformat(),
            data={
                "character": chosen,
                "boost_percent": config.EVENT_LIMITED_BOOST_PERCENT,
                "value_bonus": config.EVENT_LIMITED_VALUE_BONUS,
            },
        )

        embed = build_character_embed(
            chosen,
            footer_text=(
                f"⚡ LIMITED · +{config.EVENT_LIMITED_BOOST_PERCENT}% de chance par roll "
                f"· +{int(config.EVENT_LIMITED_VALUE_BONUS * 100)}% de valeur"
            ),
        )
        embed.title = f"⚡  PERSO LIMITÉ  ·  {chosen['name']}"
        embed.description = (
            f"🌟  **{chosen['source']}**\n\n"
            f"Ce personnage a **{config.EVENT_LIMITED_BOOST_PERCENT}% de chance** d'apparaître "
            f"à chaque roll pendant **{heures}h** !\n"
            f"*Sa valeur sera multipliée par "
            f"**{1 + config.EVENT_LIMITED_VALUE_BONUS:.1f}×** s'il est revendiqué.*\n\n"
            f"⏰ Fin : <t:{int(ends_at.timestamp())}:R>  ·  🆔 `#{eid}`"
        )
        embed.color = config.BOT_ACCENT_COLOR

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="stop", description="Arrête un événement actif")
    @app_commands.describe(id="ID de l'événement (voir /event list)")
    @app_commands.default_permissions(manage_guild=True)
    async def stop(self, interaction: discord.Interaction, id: int):
        events = await self.bot.db.get_active_events(interaction.guild.id)
        target = next((e for e in events if e["id"] == id), None)
        if not target:
            await interaction.response.send_message(
                embed=error_embed(f"Aucun événement actif avec l'ID `#{id}`."),
                ephemeral=True,
            )
            return
        await self.bot.db.stop_event(id)
        await interaction.response.send_message(
            embed=success_embed(f"Événement `#{id}` ({target['type']}) arrêté.")
        )

    @app_commands.command(name="list", description="Liste les événements actifs")
    async def list_events(self, interaction: discord.Interaction):
        events = await self.bot.db.get_active_events(interaction.guild.id)
        embed = discord.Embed(
            title="🎉  Événements actifs",
            color=config.BOT_ACCENT_COLOR,
        )
        if not events:
            embed.description = "*Aucun événement actif sur ce serveur.*"
        else:
            lines = []
            for ev in events:
                ends_ts = 0
                try:
                    ends_ts = int(datetime.fromisoformat(ev["ends_at"]).timestamp())
                except ValueError:
                    pass
                if ev["type"] == "double_tokens":
                    mult = ev.get("data", {}).get("multiplier", 2.0)
                    line = f"`#{ev['id']}`  💰  **Double Tokens** ×{mult:g}  ·  fin <t:{ends_ts}:R>"
                elif ev["type"] == "limited_character":
                    char = ev.get("data", {}).get("character", {})
                    line = (
                        f"`#{ev['id']}`  ⚡  **Limited** : {char.get('name', '?')}  "
                        f"*({char.get('source', '?')})*  ·  fin <t:{ends_ts}:R>"
                    )
                else:
                    line = f"`#{ev['id']}`  {ev['type']}  ·  fin <t:{ends_ts}:R>"
                lines.append(line)
            embed.description = "\n\n".join(lines)
        embed.set_footer(text=config.BOT_NAME)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(EventsCog(bot))
