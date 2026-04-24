"""
/help : guide des commandes.
"""
import discord
from discord import app_commands
from discord.ext import commands

import config


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description=f"Guide des commandes de {__import__('config').BOT_NAME}")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"📚  {config.BOT_NAME} · Guide",
            description=f"*{config.BOT_TAGLINE}*\n\nToutes les commandes sont en slash (`/`).",
            color=config.BOT_COLOR,
        )

        embed.add_field(
            name="🎲  Jeu",
            value=(
                "`/roll` · Pioche un perso (gagne des TetsuTokens même sans claim)\n"
                "`/harem` · Ta collection\n"
                "`/harem personnage:<nom>` · Détails d'un perso\n"
                f"*{config.ROLLS_PER_HOUR} rolls/h · 1 claim / {config.CLAIM_COOLDOWN_MINUTES} min*\n"
                f"*Pity : perso rare garanti après {config.PITY_THRESHOLD} rolls sans rareté*"
            ),
            inline=False,
        )

        embed.add_field(
            name="📋  Wishlist",
            value=(
                "`/wishlist add <nom>` · Ajoute à la wishlist\n"
                "`/wishlist remove <nom>` · Retire\n"
                "`/wishlist view` · Affiche\n"
                "`/wishlist wanted` · Qui veut tes persos ?\n"
                "`/wishlist holders` · Qui a les persos de ta wishlist ?\n"
                f"`/wishlist autoclaim <nom>` · Auto-claim "
                f"({config.AUTO_CLAIM_COST} {config.CURRENCY_NAME})\n"
                "`/wishlist autoclaim-list` · Liste tes auto-claims\n"
                "`/wishlist autoclaim-remove <id>` · Désactive un auto-claim\n"
                "`/wishlist notifs` · Basculer notifs DM uniquement"
            ),
            inline=False,
        )

        embed.add_field(
            name=f"{config.CURRENCY_NAME}  Économie & Progression",
            value=(
                "`/profile [membre]` · Ton profil complet\n"
                "`/daily` · Récompense quotidienne (streak bonus)\n"
                "`/achievements` · Succès débloqués\n"
                f"`/awaken <nom>` · Éveille un perso ({config.AWAKEN_COST} "
                f"{config.CURRENCY_NAME} · +50 % valeur)\n"
                "`/leaderboard` · Classement du serveur\n"
                "`/shop` · Acheter items (Protection Rareté, packs rolls)"
            ),
            inline=False,
        )

        embed.add_field(
            name="🖼️  Showcase & Global",
            value=(
                "`/showcase` · Génère une image top 9 de ta collection\n"
                "`/showcase global_view:True` · Version cross-serveur\n"
                "`/global enable` · Active ton profil global (opt-in)\n"
                "`/global disable` · Désactive\n"
                "`/global view <membre>` · Voir le profil global de quelqu'un"
            ),
            inline=False,
        )

        embed.add_field(
            name="🤝  Social",
            value=(
                "`/trade <membre> <mon_perso> <son_perso>` · Proposer un échange\n"
                "`/divorce <nom>` · Libérer un perso (50 % remboursé)"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎉  Événements (admin)",
            value=(
                "`/event double_tokens <heures>` · Double tokens pendant X h\n"
                "`/event limited_character <heures>` · Perso rare boosté\n"
                "`/event list` · Événements actifs\n"
                "`/event stop <id>` · Arrêter un événement"
            ),
            inline=False,
        )

        embed.add_field(
            name="⚙️  Admin serveur",
            value=(
                "`/config show` · Configuration actuelle\n"
                "`/config channel` · Salon de rolls\n"
                "`/config mode <source>` · Tout / Anime / Film / Jeu / Comic\n"
                "`/config role <rôle>` · Rôle auto-attribué\n"
                "`/config apply-role` · Appliquer le rôle à tout le monde\n"
                "`/config notifs <mode>` · DM / salon / les deux"
            ),
            inline=False,
        )

        embed.set_footer(
            text=f"{config.BOT_NAME} · {config.CURRENCY_NAME_LONG} = {config.CURRENCY_NAME}"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
