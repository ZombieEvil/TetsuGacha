"""
Configuration admin du serveur.
Une seule commande : /config avec sous-commandes groupées.

Actions :
- /config channel      → définit le salon de rolls
- /config mode         → change le mode (all, anime, movie, game, comic)
- /config role         → définit un auto-rôle (donné aux membres qui rejoignent)
- /config apply-role   → applique le rôle à tous les membres actuels
- /config show         → affiche la config actuelle
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import asyncio

import config
from utils.helpers import success_embed, error_embed, warning_embed, info_embed


MODE_CHOICES = [
    app_commands.Choice(name="🌐 Tout (toutes sources)", value="all"),
    app_commands.Choice(name="📖 Anime / Manga", value="anime"),
    app_commands.Choice(name="🎬 Films / Séries", value="movie"),
    app_commands.Choice(name="🎮 Jeux vidéo", value="game"),
    app_commands.Choice(name="💥 Comics", value="comic"),
]


class ConfigCog(commands.GroupCog, name="config"):
    """Administration du bot sur le serveur (modérateurs uniquement)."""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="show", description="Affiche la configuration actuelle du serveur")
    @app_commands.default_permissions(manage_guild=True)
    async def show(self, interaction: discord.Interaction):
        cfg = await self.bot.db.get_guild_config(interaction.guild.id)

        channel_mention = "❌ *Non défini*"
        if cfg.get("roll_channel_id"):
            ch = interaction.guild.get_channel(cfg["roll_channel_id"])
            channel_mention = ch.mention if ch else f"*(salon introuvable : {cfg['roll_channel_id']})*"

        role_mention = "❌ *Non défini*"
        if cfg.get("member_role_id"):
            r = interaction.guild.get_role(cfg["member_role_id"])
            role_mention = r.mention if r else f"*(rôle introuvable : {cfg['member_role_id']})*"

        mode_labels = {
            "all": "🌐 Tout", "anime": "📖 Anime/Manga", "movie": "🎬 Films/Séries",
            "game": "🎮 Jeux vidéo", "comic": "💥 Comics",
        }
        mode_label = mode_labels.get(cfg.get("active_mode", "all"), "🌐 Tout")

        notif_labels = {
            "dm": "📬 DM uniquement",
            "channel": "📢 Salon uniquement",
            "both": "📬📢 DM + salon",
        }
        notif_label = notif_labels.get(cfg.get("notif_mode", "dm"), "📬 DM uniquement")

        embed = discord.Embed(
            title="⚙️  Configuration du serveur",
            color=config.BOT_COLOR,
        )
        embed.add_field(name="🎲 Salon de rolls", value=channel_mention, inline=False)
        embed.add_field(name="📡 Mode actif", value=mode_label, inline=True)
        embed.add_field(name="👥 Rôle auto", value=role_mention, inline=True)
        embed.add_field(name="🔔 Notifications wishlist", value=notif_label, inline=True)
        embed.set_footer(text=f"{config.BOT_NAME} · Utilise les sous-commandes /config pour modifier")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="channel", description="Définit le salon actuel comme salon de rolls")
    @app_commands.default_permissions(manage_guild=True)
    async def channel(self, interaction: discord.Interaction):
        await self.bot.db.set_guild_field(
            interaction.guild.id, "roll_channel_id", interaction.channel.id
        )
        await interaction.response.send_message(
            embed=success_embed(
                f"Ce salon ({interaction.channel.mention}) est désormais le salon de rolls officiel."
            ),
            ephemeral=True
        )

    @app_commands.command(name="mode", description="Change le type de personnages piochés")
    @app_commands.describe(source="Le type de source pour les rolls")
    @app_commands.choices(source=MODE_CHOICES)
    @app_commands.default_permissions(manage_guild=True)
    async def mode(self, interaction: discord.Interaction, source: app_commands.Choice[str]):
        await self.bot.db.set_guild_field(interaction.guild.id, "active_mode", source.value)
        await interaction.response.send_message(
            embed=success_embed(f"Mode changé : **{source.name}**"),
            ephemeral=False,
        )

    @app_commands.command(name="role", description="Définit le rôle auto-attribué aux membres")
    @app_commands.describe(role="Le rôle à donner automatiquement. Laisse vide pour désactiver.")
    @app_commands.default_permissions(manage_guild=True)
    async def role(self, interaction: discord.Interaction, role: Optional[discord.Role] = None):
        if role is None:
            await self.bot.db.set_guild_field(interaction.guild.id, "member_role_id", None)
            await interaction.response.send_message(
                embed=success_embed("Auto-rôle désactivé."),
                ephemeral=True,
            )
            return

        # Check hiérarchie : le bot doit être au-dessus du rôle
        me = interaction.guild.me
        if role >= me.top_role:
            await interaction.response.send_message(
                embed=error_embed(
                    f"Le rôle {role.mention} est au-dessus du bot dans la hiérarchie. "
                    f"Déplace le rôle du bot plus haut pour qu'il puisse l'attribuer."
                ),
                ephemeral=True,
            )
            return

        if role.managed or role.is_bot_managed():
            await interaction.response.send_message(
                embed=error_embed("Ce rôle est géré par une intégration, je ne peux pas l'attribuer."),
                ephemeral=True,
            )
            return

        await self.bot.db.set_guild_field(interaction.guild.id, "member_role_id", role.id)
        await interaction.response.send_message(
            embed=success_embed(
                f"Rôle auto-attribué défini : {role.mention}\n"
                f"Il sera donné automatiquement aux nouveaux membres.\n"
                f"Pour l'appliquer aux membres déjà présents, utilise `/config apply-role`."
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="apply-role",
        description="Donne le rôle auto-attribué à tous les membres actuels du serveur"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def apply_role(self, interaction: discord.Interaction):
        cfg = await self.bot.db.get_guild_config(interaction.guild.id)
        role_id = cfg.get("member_role_id")
        if not role_id:
            await interaction.response.send_message(
                embed=error_embed("Aucun rôle auto-attribué défini. Utilise `/config role` d'abord."),
                ephemeral=True,
            )
            return

        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(
                embed=error_embed("Le rôle configuré n'existe plus. Redéfinis-le avec `/config role`."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        # Sécurité : on ne met pas le rôle aux bots ni à ceux qui l'ont déjà
        targets = [m for m in interaction.guild.members
                   if not m.bot and role not in m.roles]
        total = len(targets)

        if total == 0:
            await interaction.followup.send(
                embed=info_embed("Rien à faire", "Tous les membres ont déjà ce rôle."),
                ephemeral=True,
            )
            return

        success = 0
        errors = 0
        for i, member in enumerate(targets):
            try:
                await member.add_roles(role, reason=f"{config.BOT_NAME} auto-role bulk apply")
                success += 1
            except (discord.Forbidden, discord.HTTPException):
                errors += 1
            # Throttle pour éviter le rate limit : petite pause tous les 10 membres
            if (i + 1) % 10 == 0:
                await asyncio.sleep(1)

        embed = success_embed(
            f"**{success}** membres ont reçu le rôle {role.mention}.\n"
            f"{'⚠️ ' + str(errors) + ' erreur(s).' if errors else '✨ Aucune erreur.'}"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="notifs",
        description="Définit le mode des notifications wishlist (DM / salon / les deux)"
    )
    @app_commands.describe(mode="Où envoyer les notifications quand un perso wishlisté est claim")
    @app_commands.choices(mode=[
        app_commands.Choice(name="📬 DM uniquement (recommandé, pas de spam)", value="dm"),
        app_commands.Choice(name="📢 Salon uniquement", value="channel"),
        app_commands.Choice(name="📬📢 DM + salon", value="both"),
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def notifs(self, interaction: discord.Interaction,
                     mode: app_commands.Choice[str]):
        await self.bot.db.set_guild_field(interaction.guild.id, "notif_mode", mode.value)
        await interaction.response.send_message(
            embed=success_embed(f"Notifications wishlist : **{mode.name}**"),
            ephemeral=True,
        )

    # ==== Event listener pour auto-rôle sur nouveau membre ====
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        cfg = await self.bot.db.get_guild_config(member.guild.id)
        role_id = cfg.get("member_role_id")
        if not role_id:
            return
        role = member.guild.get_role(role_id)
        if not role:
            return
        try:
            await member.add_roles(role, reason=f"{config.BOT_NAME} auto-role on join")
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot):
    await bot.add_cog(ConfigCog(bot))
