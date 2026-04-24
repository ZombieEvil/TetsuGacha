"""
/wishlist : add, remove, view, wanted, holders, autoclaim
"""
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio

import config
from utils.helpers import success_embed, error_embed, warning_embed, info_embed


ANILIST_SEARCH = """
query ($search: String) {
  Page(page: 1, perPage: 5) {
    characters(search: $search, sort: FAVOURITES_DESC) {
      id
      name { full }
      image { medium }
      media(perPage: 1, sort: POPULARITY_DESC) {
        nodes { title { romaji english } type }
      }
    }
  }
}
"""


class WishlistCog(commands.GroupCog, name="wishlist"):
    """Gestion de la liste de souhaits."""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def _search_anilist(self, name: str):
        if not self.bot.fetcher.session or self.bot.fetcher.session.closed:
            await self.bot.fetcher.start()
        session = self.bot.fetcher.session
        try:
            async with session.post(
                "https://graphql.anilist.co",
                json={"query": ANILIST_SEARCH, "variables": {"search": name}},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("data", {}).get("Page", {}).get("characters", [])
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return []

    # ============================================================
    # ADD
    # ============================================================
    @app_commands.command(name="add", description="Ajoute un personnage à ta wishlist")
    @app_commands.describe(nom="Nom du personnage (anime/manga)")
    async def add(self, interaction: discord.Interaction, nom: str):
        await interaction.response.defer(ephemeral=True)

        count = await self.bot.db.count_wishlist(interaction.user.id, interaction.guild.id)
        if count >= config.MAX_WISHLIST_SIZE:
            await interaction.followup.send(
                embed=error_embed(
                    f"Ta wishlist est pleine ({config.MAX_WISHLIST_SIZE} max). "
                    f"Utilise `/wishlist remove` pour libérer une place."
                ),
                ephemeral=True,
            )
            return

        results = await self._search_anilist(nom)
        if not results:
            await interaction.followup.send(
                embed=error_embed(f"Aucun personnage trouvé pour `{nom}`."),
                ephemeral=True,
            )
            return

        options = []
        for c in results[:5]:
            media = c["media"]["nodes"][0] if c["media"]["nodes"] else {}
            source = (media.get("title", {}).get("english")
                      or media.get("title", {}).get("romaji") or "Inconnu")
            options.append(discord.SelectOption(
                label=c["name"]["full"][:100],
                description=f"de {source}"[:100],
                value=f"al_{c['id']}|{c['name']['full']}|anime",
            ))

        select = discord.ui.Select(placeholder="Choisis le bon personnage…", options=options)

        async def select_callback(inter: discord.Interaction):
            char_id, char_name, source_type = select.values[0].split("|", 2)
            ok = await self.bot.db.add_to_wishlist(
                interaction.user.id, interaction.guild.id,
                char_id, char_name, source_type,
            )
            if ok:
                await inter.response.edit_message(
                    content=None,
                    embed=success_embed(f"**{char_name}** ajouté à ta wishlist."),
                    view=None,
                )
            else:
                await inter.response.edit_message(
                    content=None,
                    embed=warning_embed(f"**{char_name}** est déjà dans ta wishlist."),
                    view=None,
                )

        select.callback = select_callback
        view = discord.ui.View(timeout=60)
        view.add_item(select)
        await interaction.followup.send(
            content="🔍  Sélectionne le bon personnage :",
            view=view, ephemeral=True,
        )

    @app_commands.command(name="remove", description="Retire un personnage de ta wishlist")
    @app_commands.describe(nom="Nom du personnage à retirer")
    async def remove(self, interaction: discord.Interaction, nom: str):
        removed = await self.bot.db.remove_from_wishlist(
            interaction.user.id, interaction.guild.id, nom
        )
        if removed:
            await interaction.response.send_message(
                embed=success_embed(f"**{removed}** retiré de ta wishlist."),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=error_embed(f"Aucun perso correspondant à `{nom}`."),
                ephemeral=True,
            )

    @app_commands.command(name="view", description="Affiche une wishlist")
    @app_commands.describe(membre="Membre dont on veut voir la wishlist")
    async def view(self, interaction: discord.Interaction, membre: discord.Member = None):
        target = membre or interaction.user
        items = await self.bot.db.get_wishlist(target.id, interaction.guild.id)

        embed = discord.Embed(
            title=f"📋  Wishlist de {target.display_name}",
            color=config.BOT_COLOR,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        if not items:
            embed.description = "*Wishlist vide.*\nAjoute des persos avec `/wishlist add <nom>`."
        else:
            lines = [f"`{i:>2}`  💖  **{w['character_name']}**" for i, w in enumerate(items, 1)]
            embed.description = "\n".join(lines)
            embed.set_footer(
                text=f"{len(items)}/{config.MAX_WISHLIST_SIZE}  ·  {config.BOT_NAME}"
            )
        await interaction.response.send_message(embed=embed)

    # ============================================================
    # WANTED : qui veut les persos que JE possède
    # ============================================================
    @app_commands.command(
        name="wanted",
        description="Qui veut les personnages que tu possèdes ?"
    )
    async def wanted(self, interaction: discord.Interaction):
        await interaction.response.defer()
        matches = await self.bot.db.find_wishlist_matches_for_user_chars(
            interaction.user.id, interaction.guild.id
        )

        embed = discord.Embed(
            title=f"🎯  Tes persos convoités",
            description=(
                "Ces personnages de ta collection sont sur la wishlist d'autres membres. "
                "Propose-leur un échange avec `/trade` !"
            ),
            color=config.BOT_ACCENT_COLOR,
        )
        if not matches:
            embed.description = "*Aucun de tes personnages n'est sur la wishlist de quelqu'un.*"
        else:
            lines = []
            for m in matches[:12]:
                c = m["character"]
                wishers = m["wishers"]
                names = []
                for uid in wishers[:5]:
                    member = interaction.guild.get_member(uid)
                    names.append(member.display_name if member else f"<@{uid}>")
                extra = f" +{len(wishers) - 5}" if len(wishers) > 5 else ""
                lines.append(
                    f"**{c['character_name']}** *({c['character_source']})*\n"
                    f"      ↳ 🎯 {', '.join(names)}{extra}"
                )
            embed.add_field(name="\u200b", value="\n\n".join(lines), inline=False)
        embed.set_footer(text=config.BOT_NAME)
        await interaction.followup.send(embed=embed)

    # ============================================================
    # HOLDERS : qui a les persos de MA wishlist
    # ============================================================
    @app_commands.command(
        name="holders",
        description="Qui possède les personnages de ta wishlist ?"
    )
    async def holders(self, interaction: discord.Interaction):
        await interaction.response.defer()
        results = await self.bot.db.find_holders_for_user_wishlist(
            interaction.user.id, interaction.guild.id
        )

        embed = discord.Embed(
            title="🔍  Possesseurs de ta wishlist",
            description=(
                "Ces personnages de ta wishlist sont déjà possédés par quelqu'un. "
                "Propose-leur un échange avec `/trade` !"
            ),
            color=config.BOT_COLOR,
        )
        if not results:
            embed.description = "*Personne ne possède encore de perso de ta wishlist.*"
        else:
            lines = []
            for r in results[:15]:
                c = r["character"]
                owner = interaction.guild.get_member(r["owner_id"])
                owner_name = owner.display_name if owner else f"<@{r['owner_id']}>"
                lines.append(
                    f"💖  **{c['character_name']}** *({c['character_source']})*\n"
                    f"      ↳ appartient à **{owner_name}**"
                )
            embed.add_field(name="\u200b", value="\n\n".join(lines), inline=False)
        embed.set_footer(text=config.BOT_NAME)
        await interaction.followup.send(embed=embed)

    # ============================================================
    # AUTO-CLAIM
    # ============================================================
    @app_commands.command(
        name="autoclaim",
        description=f"Active un auto-claim (coût {config.AUTO_CLAIM_COST} {config.CURRENCY_NAME})"
    )
    @app_commands.describe(
        nom="Nom du personnage à auto-claim (doit être en wishlist)"
    )
    async def autoclaim(self, interaction: discord.Interaction, nom: str):
        user_id = interaction.user.id
        guild_id = interaction.guild.id

        # Vérif cap max
        current_count = await self.bot.db.count_user_auto_claims(user_id, guild_id)
        if current_count >= config.MAX_AUTO_CLAIMS:
            await interaction.response.send_message(
                embed=error_embed(
                    f"Tu as déjà {config.MAX_AUTO_CLAIMS} auto-claims actifs. "
                    f"Utilise `/wishlist autoclaim-list` pour voir ou retirer."
                ),
                ephemeral=True,
            )
            return

        # Le perso doit être dans la wishlist
        wl = await self.bot.db.get_wishlist(user_id, guild_id)
        needle = nom.lower().strip()
        match = next((w for w in wl if needle in w["character_name"].lower()), None)
        if not match:
            await interaction.response.send_message(
                embed=error_embed(
                    f"`{nom}` n'est pas dans ta wishlist. Ajoute-le avec `/wishlist add` d'abord."
                ),
                ephemeral=True,
            )
            return

        # Vérif solde
        user = await self.bot.db.get_or_create_user(user_id, guild_id)
        if user["currency"] < config.AUTO_CLAIM_COST:
            await interaction.response.send_message(
                embed=error_embed(
                    f"Il te faut **{config.AUTO_CLAIM_COST}** {config.CURRENCY_NAME} "
                    f"(tu en as **{user['currency']}**)."
                ),
                ephemeral=True,
            )
            return

        # Déjà en auto-claim ?
        existing = await self.bot.db.get_user_auto_claims(user_id, guild_id)
        if any(ac["character_id"] == match["character_id"]
               and ac["source_type"] == match["source_type"] for ac in existing):
            await interaction.response.send_message(
                embed=warning_embed(
                    f"**{match['character_name']}** est déjà en auto-claim."
                ),
                ephemeral=True,
            )
            return

        # Paiement + création
        await self.bot.db.update_user_currency(
            user_id, guild_id, -config.AUTO_CLAIM_COST
        )
        await self.bot.db.add_auto_claim(
            user_id, guild_id,
            match["character_id"], match["character_name"], match["source_type"],
        )

        await interaction.response.send_message(
            embed=success_embed(
                f"🤖  Auto-claim activé pour **{match['character_name']}**.\n"
                f"Coût : {config.AUTO_CLAIM_COST} {config.CURRENCY_NAME} · "
                f"Cooldown : {config.AUTO_CLAIM_COOLDOWN_HOURS}h entre déclenchements.\n"
                f"*Si le perso est rollé par quelqu'un, il sera claim automatiquement pour toi* "
                f"(respect du cooldown de claim classique)."
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="autoclaim-list",
        description="Liste tes auto-claims actifs"
    )
    async def autoclaim_list(self, interaction: discord.Interaction):
        acs = await self.bot.db.get_user_auto_claims(
            interaction.user.id, interaction.guild.id
        )
        embed = discord.Embed(
            title="🤖  Tes auto-claims",
            color=config.BOT_COLOR,
        )
        if not acs:
            embed.description = (
                "*Aucun auto-claim actif.*\n"
                f"Active-en avec `/wishlist autoclaim <nom>` "
                f"(coût {config.AUTO_CLAIM_COST} {config.CURRENCY_NAME})."
            )
        else:
            lines = []
            for ac in acs:
                trig = "*jamais déclenché*"
                if ac.get("last_triggered"):
                    trig = f"dernier : <t:{_iso_to_ts(ac['last_triggered'])}:R>"
                lines.append(
                    f"`#{ac['id']}`  🤖  **{ac['character_name']}** · {trig}"
                )
            embed.description = "\n".join(lines)
            embed.set_footer(
                text=f"{len(acs)}/{config.MAX_AUTO_CLAIMS}  ·  /wishlist autoclaim-remove <id>"
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="autoclaim-remove",
        description="Désactive un auto-claim (pas de remboursement)"
    )
    @app_commands.describe(id="L'identifiant de l'auto-claim (voir /wishlist autoclaim-list)")
    async def autoclaim_remove(self, interaction: discord.Interaction, id: int):
        # Vérifier que ça t'appartient
        acs = await self.bot.db.get_user_auto_claims(
            interaction.user.id, interaction.guild.id
        )
        target = next((ac for ac in acs if ac["id"] == id), None)
        if not target:
            await interaction.response.send_message(
                embed=error_embed(f"Auto-claim `#{id}` introuvable dans tes actifs."),
                ephemeral=True,
            )
            return
        await self.bot.db.remove_auto_claim(id)
        await interaction.response.send_message(
            embed=success_embed(
                f"Auto-claim sur **{target['character_name']}** désactivé."
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="notifs",
        description="Active/désactive les notifications wishlist en DM uniquement"
    )
    async def notifs(self, interaction: discord.Interaction):
        u = await self.bot.db.get_or_create_user(interaction.user.id, interaction.guild.id)
        current = u.get("dm_only_notifs", False)
        new_val = not current
        await self.bot.db.set_user_field(
            interaction.user.id, interaction.guild.id, "dm_only_notifs", new_val
        )
        if new_val:
            msg = "🔕  Notifications wishlist : **DM uniquement** (silencieux public)."
        else:
            msg = "🔔  Notifications wishlist : **selon la configuration du serveur**."
        await interaction.response.send_message(embed=success_embed(msg), ephemeral=True)


def _iso_to_ts(iso: str) -> int:
    from datetime import datetime
    try:
        return int(datetime.fromisoformat(iso).timestamp())
    except Exception:
        return 0


async def setup(bot):
    await bot.add_cog(WishlistCog(bot))
