"""
/harem : affiche la collection d'un membre avec paginator et détails intégrés.
"""
import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.helpers import (
    build_character_embed, get_rarity_info, source_emoji, source_label,
    error_embed, success_embed, warning_embed, info_embed,
)
from utils.showcase import generate_showcase_image, PIL_AVAILABLE


class HaremView(discord.ui.View):
    def __init__(self, bot, user_id: int, guild_id: int,
                 viewer_id: int, sort_by: str = "value"):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.guild_id = guild_id
        self.viewer_id = viewer_id
        self.sort_by = sort_by
        self.page = 0
        self.per_page = 10
        self.characters_cache = []  # page courante en mémoire

    async def build_list_embed(self, guild):
        self.characters_cache = await self.bot.db.get_user_characters(
            self.user_id, self.guild_id,
            limit=self.per_page, offset=self.page * self.per_page,
            sort_by=self.sort_by,
        )
        total = await self.bot.db.count_user_characters(self.user_id, self.guild_id)

        member = guild.get_member(self.user_id)
        name = member.display_name if member else "Utilisateur"

        total_value = 0
        for c in await self.bot.db.get_user_characters(
            self.user_id, self.guild_id, limit=10000, sort_by="value"
        ):
            total_value += c["value"]

        max_page = max(1, (total - 1) // self.per_page + 1) if total else 1

        embed = discord.Embed(
            title=f"💖  Collection de {name}",
            description=f"**{total}** personnages · valeur totale **{total_value}** {config.CURRENCY_NAME}",
            color=config.BOT_COLOR,
        )
        if member:
            embed.set_thumbnail(url=member.display_avatar.url)

        if not self.characters_cache:
            embed.add_field(
                name="\u200b",
                value="*Aucun personnage sur cette page.*",
                inline=False,
            )
        else:
            lines = []
            for i, c in enumerate(self.characters_cache, start=self.page * self.per_page + 1):
                info = get_rarity_info(c["rarity"])
                lines.append(
                    f"`{i:>2}`  {info['emoji']} {source_emoji(c['source_type'])}  "
                    f"**{c['character_name']}**\n"
                    f"     ↳ *{c['character_source']}* · {c['value']} {config.CURRENCY_NAME}"
                )
            embed.add_field(name="\u200b", value="\n".join(lines), inline=False)

        embed.set_footer(
            text=f"Page {self.page + 1}/{max_page} · Tri : {self.sort_by} · {config.BOT_NAME}"
        )
        return embed

    async def update(self, interaction: discord.Interaction):
        embed = await self.build_list_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, _):
        if self.page > 0:
            self.page -= 1
        await self.update(interaction)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, row=0)
    async def next_btn(self, interaction: discord.Interaction, _):
        total = await self.bot.db.count_user_characters(self.user_id, self.guild_id)
        if (self.page + 1) * self.per_page < total:
            self.page += 1
        await self.update(interaction)

    @discord.ui.button(label="Par valeur", style=discord.ButtonStyle.primary, row=1)
    async def sort_value(self, interaction: discord.Interaction, _):
        self.sort_by = "value"
        self.page = 0
        await self.update(interaction)

    @discord.ui.button(label="Par récence", style=discord.ButtonStyle.primary, row=1)
    async def sort_recent(self, interaction: discord.Interaction, _):
        self.sort_by = "recent"
        self.page = 0
        await self.update(interaction)

    @discord.ui.button(label="Par nom", style=discord.ButtonStyle.primary, row=1)
    async def sort_name(self, interaction: discord.Interaction, _):
        self.sort_by = "name"
        self.page = 0
        await self.update(interaction)


class CollectionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="harem",
        description="Affiche ta collection (ou celle d'un autre membre)"
    )
    @app_commands.describe(
        membre="Membre dont on veut voir la collection",
        personnage="Affiche directement les détails d'un personnage (par nom)",
    )
    async def harem(self, interaction: discord.Interaction,
                    membre: discord.Member = None,
                    personnage: str = None):
        target = membre or interaction.user

        # Si un nom de personnage est fourni → on affiche sa fiche direct
        if personnage:
            char = await self.bot.db.find_user_character(
                target.id, interaction.guild.id, personnage
            )
            if not char:
                await interaction.response.send_message(
                    embed=error_embed(
                        f"Aucun personnage correspondant à `{personnage}` "
                        f"dans la collection de {target.display_name}."
                    ),
                    ephemeral=True,
                )
                return

            char_dict = {
                "id": char["character_id"],
                "name": char["character_name"],
                "source": char["character_source"],
                "source_type": char["source_type"],
                "image_url": char["image_url"],
                "source_image_url": char.get("source_image_url"),
                "rarity": char["rarity"],
                "value": char["value"],
                "popularity_score": char["popularity_score"],
            }
            embed = build_character_embed(
                char_dict,
                owner_name=target.display_name,
                show_owner=True,
                footer_text=f"Fiche · {config.BOT_NAME}",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Sinon : liste paginée
        view = HaremView(self.bot, target.id, interaction.guild.id, interaction.user.id)
        embed = await view.build_list_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(
        name="showcase",
        description="Génère une image de ta collection (top 9) à partager"
    )
    @app_commands.describe(
        membre="Membre dont on veut la showcase",
        global_view="Inclure les persos de tous les serveurs (si opt-in)",
    )
    async def showcase(self, interaction: discord.Interaction,
                        membre: discord.Member = None,
                        global_view: bool = False):
        target = membre or interaction.user

        if not PIL_AVAILABLE:
            await interaction.response.send_message(
                embed=error_embed(
                    "La génération d'image nécessite **Pillow**. "
                    "Installe-le avec `pip install Pillow`."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        # Choisir la source des persos : guild actuel ou global
        if global_view:
            gp = await self.bot.db.get_global_profile(target.id)
            if not gp or not gp.get("enabled"):
                await interaction.followup.send(
                    embed=warning_embed(
                        f"**{target.display_name}** n'a pas activé le profil global.\n"
                        f"*Active-le avec `/global enable`.*"
                    ),
                    ephemeral=True,
                )
                return
            chars = await self.bot.db.get_all_user_characters_cross_guilds(
                target.id, limit=config.SHOWCASE_GRID_SIZE ** 2
            )
            total_count = len(chars)
            total_value = sum(c.get("value", 0) for c in chars)
            title_suffix = " · Global"
        else:
            chars = await self.bot.db.get_user_characters(
                target.id, interaction.guild.id,
                limit=config.SHOWCASE_GRID_SIZE ** 2,
                sort_by="value",
            )
            all_chars = await self.bot.db.get_user_characters(
                target.id, interaction.guild.id, limit=10000, sort_by="value"
            )
            total_count = len(all_chars)
            total_value = sum(c.get("value", 0) for c in all_chars)
            title_suffix = f" · {interaction.guild.name[:25]}"

        if not chars:
            await interaction.followup.send(
                embed=info_embed(
                    "Collection vide",
                    f"**{target.display_name}** n'a encore aucun personnage.",
                ),
            )
            return

        # Utiliser la session aiohttp existante du fetcher
        if not self.bot.fetcher.session or self.bot.fetcher.session.closed:
            await self.bot.fetcher.start()
        session = self.bot.fetcher.session

        try:
            png_bytes = await generate_showcase_image(
                chars, target.display_name + title_suffix,
                total_value, total_count, session,
            )
        except Exception as e:
            await interaction.followup.send(
                embed=error_embed(f"Erreur lors de la génération de l'image : {e}"),
                ephemeral=True,
            )
            return

        if not png_bytes:
            await interaction.followup.send(
                embed=error_embed("La génération a échoué."),
                ephemeral=True,
            )
            return

        import io
        file = discord.File(io.BytesIO(png_bytes), filename="showcase.png")
        await interaction.followup.send(
            content=f"🖼️  Showcase de **{target.display_name}**",
            file=file,
        )


class GlobalProfileCog(commands.GroupCog, name="global"):
    """Profil global cross-serveur (opt-in)."""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="enable",
        description="Active ton profil global (visible sur tous les serveurs)"
    )
    async def enable(self, interaction: discord.Interaction):
        await self.bot.db.set_global_profile_optin(
            interaction.user.id, True,
            favorite_guild_id=interaction.guild.id,
        )
        await interaction.response.send_message(
            embed=success_embed(
                "🌐  Ton profil est désormais **global**.\n"
                "N'importe qui peut maintenant voir ta collection cross-serveur "
                "via `/showcase global_view:True` ou `/global view`."
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="disable",
        description="Désactive ton profil global"
    )
    async def disable(self, interaction: discord.Interaction):
        await self.bot.db.set_global_profile_optin(interaction.user.id, False)
        await interaction.response.send_message(
            embed=success_embed("🔒  Ton profil global a été **désactivé**."),
            ephemeral=True,
        )

    @app_commands.command(
        name="view",
        description="Voir la collection globale d'un utilisateur (opt-in requis)"
    )
    @app_commands.describe(membre="Membre dont on veut voir la collection globale")
    async def view(self, interaction: discord.Interaction, membre: discord.Member):
        gp = await self.bot.db.get_global_profile(membre.id)
        if not gp or not gp.get("enabled"):
            await interaction.response.send_message(
                embed=warning_embed(
                    f"**{membre.display_name}** n'a pas activé son profil global."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        chars = await self.bot.db.get_all_user_characters_cross_guilds(membre.id, limit=15)

        embed = discord.Embed(
            title=f"🌐  Profil global de {membre.display_name}",
            description=f"*Top persos à travers tous les serveurs.*",
            color=config.BOT_ACCENT_COLOR,
        )
        embed.set_thumbnail(url=membre.display_avatar.url)

        if not chars:
            embed.description = "*Aucun personnage encore.*"
        else:
            total_value = sum(c.get("value", 0) for c in chars)
            lines = []
            for i, c in enumerate(chars[:10], 1):
                info = get_rarity_info(c["rarity"])
                lines.append(
                    f"`{i:>2}`  {info['emoji']} **{c['character_name']}** · "
                    f"{c['value']} {config.CURRENCY_NAME}"
                )
            embed.add_field(name="\u200b", value="\n".join(lines), inline=False)
            embed.add_field(
                name="Valeur totale (top 15)",
                value=f"**{total_value}** {config.CURRENCY_NAME}",
                inline=True,
            )
        embed.set_footer(text=f"{config.BOT_NAME} · Profil global opt-in")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CollectionCog(bot))
    await bot.add_cog(GlobalProfileCog(bot))
