"""
/profile, /daily, /leaderboard, /achievements, /awaken
"""
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta

import config
from utils.helpers import (
    format_duration, success_embed, warning_embed, error_embed,
    compute_streak, streak_daily_bonus, streak_milestone_reward,
    achievement_unlocked_embed,
)
from utils.achievements import check_achievements, ACHIEVEMENTS, get_achievement


class ProfileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Affiche ton profil (ou celui d'un autre membre)")
    @app_commands.describe(membre="Membre à afficher")
    async def profile(self, interaction: discord.Interaction, membre: discord.Member = None):
        target = membre or interaction.user
        user = await self.bot.db.get_or_create_user(target.id, interaction.guild.id)
        total = await self.bot.db.count_user_characters(target.id, interaction.guild.id)
        wishlist_count = await self.bot.db.count_wishlist(target.id, interaction.guild.id)
        all_chars = await self.bot.db.get_user_characters(
            target.id, interaction.guild.id, limit=10000, sort_by="value"
        )
        total_value = sum(c["value"] for c in all_chars)

        top = all_chars[:3]
        ach_count = len(user.get("achievements", []))
        ach_total = len(ACHIEVEMENTS)

        embed = discord.Embed(
            title=f"👤  Profil de {target.display_name}",
            color=config.BOT_COLOR,
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        # Ligne 1
        embed.add_field(
            name=f"{config.CURRENCY_NAME} Solde",
            value=f"**{user['currency']}** {config.CURRENCY_NAME_LONG}",
            inline=True,
        )
        embed.add_field(name="💖 Collection", value=f"**{total}** persos", inline=True)
        embed.add_field(
            name="📊 Valeur totale",
            value=f"**{total_value}** {config.CURRENCY_NAME}",
            inline=True,
        )

        # Ligne 2
        streak = user.get("current_streak", 0)
        max_streak = user.get("max_streak", 0)
        streak_emoji = "🔥" if streak >= 7 else "📅"
        embed.add_field(
            name=f"{streak_emoji} Streak",
            value=f"**{streak}** jours · max **{max_streak}**",
            inline=True,
        )
        pity = user.get("pity_counter", 0)
        embed.add_field(
            name="⭐ Pity",
            value=f"**{pity}** / {config.PITY_THRESHOLD}",
            inline=True,
        )
        embed.add_field(
            name="🏆 Succès",
            value=f"**{ach_count}** / {ach_total}",
            inline=True,
        )

        # Ligne 3
        embed.add_field(
            name="📋 Wishlist",
            value=f"**{wishlist_count}**/{config.MAX_WISHLIST_SIZE}",
            inline=True,
        )
        embed.add_field(
            name="🎲 Rolls totaux",
            value=f"**{user.get('total_rolls', 0)}**",
            inline=True,
        )
        mult = user.get("earn_multiplier", 0.0)
        embed.add_field(
            name="✨ Bonus gains",
            value=f"**+{int(mult * 100)}%**",
            inline=True,
        )

        if top:
            top_lines = [
                f"`{i+1}.`  **{c['character_name']}** · {c['value']} {config.CURRENCY_NAME}"
                for i, c in enumerate(top)
            ]
            embed.add_field(name="🥇  Top 3", value="\n".join(top_lines), inline=False)

        embed.set_footer(text=config.BOT_NAME)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Récupère ta récompense quotidienne (streak bonus)")
    async def daily(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        user = await self.bot.db.get_or_create_user(user_id, guild_id)
        now = datetime.utcnow()

        if user.get("last_daily"):
            last = datetime.fromisoformat(user["last_daily"])
            next_daily = last + timedelta(hours=24)
            if now < next_daily:
                remaining = int((next_daily - now).total_seconds())
                await interaction.response.send_message(
                    embed=warning_embed(
                        f"Tu as déjà réclamé ta récompense. Reviens dans **{format_duration(remaining)}**."
                    ),
                    ephemeral=True,
                )
                return

        # Streak
        old_streak = user.get("current_streak", 0)
        new_streak, reason = compute_streak(user.get("last_daily"), old_streak, now)
        max_streak = max(user.get("max_streak", 0), new_streak)
        bonus_tokens = streak_daily_bonus(new_streak)
        rolls_reward = streak_milestone_reward(old_streak, new_streak)

        total_tokens = config.DAILY_REWARD + bonus_tokens
        await self.bot.db.update_user_currency(user_id, guild_id, total_tokens)
        await self.bot.db.set_user_field(user_id, guild_id, "last_daily", now.isoformat())
        await self.bot.db.set_user_field(user_id, guild_id, "current_streak", new_streak)
        await self.bot.db.set_user_field(user_id, guild_id, "max_streak", max_streak)
        if rolls_reward:
            await self.bot.db.increment_user_field(
                user_id, guild_id, "bonus_rolls", rolls_reward
            )

        # Achievements
        user_updated = await self.bot.db.get_or_create_user(user_id, guild_id)
        newly = check_achievements(user_updated, user_updated.get("achievements", []))
        for ach in newly:
            await self.bot.db.add_achievement(user_id, guild_id, ach.id)
            if ach.reward_tokens:
                await self.bot.db.update_user_currency(user_id, guild_id, ach.reward_tokens)
            if ach.reward_rolls:
                await self.bot.db.increment_user_field(
                    user_id, guild_id, "bonus_rolls", ach.reward_rolls
                )
            if ach.reward_multiplier:
                await self.bot.db.add_earn_multiplier(
                    user_id, guild_id, ach.reward_multiplier
                )

        reason_text = {
            "started": "🌱  Début d'un nouveau streak !",
            "continued": f"🔥  Streak de **{new_streak}** jours !",
            "reset": "😴  Ton streak a été reset (+48h d'absence), on repart à 1.",
        }.get(reason, "")

        embed = discord.Embed(
            title="🎁  Récompense quotidienne",
            description=reason_text,
            color=config.BOT_ACCENT_COLOR,
        )
        embed.add_field(name="Base", value=f"+{config.DAILY_REWARD} {config.CURRENCY_NAME}", inline=True)
        if bonus_tokens:
            embed.add_field(
                name="Bonus streak",
                value=f"+{bonus_tokens} {config.CURRENCY_NAME}",
                inline=True,
            )
        embed.add_field(
            name="Total",
            value=f"**+{total_tokens}** {config.CURRENCY_NAME}",
            inline=True,
        )
        if rolls_reward:
            embed.add_field(
                name="🎉  Palier atteint !",
                value=f"**+{rolls_reward}** rolls bonus permanents",
                inline=False,
            )

        new_user = await self.bot.db.get_or_create_user(user_id, guild_id)
        embed.set_footer(
            text=f"Solde : {new_user['currency']} {config.CURRENCY_NAME}  ·  Streak {new_streak}"
        )
        await interaction.response.send_message(embed=embed)

        for ach in newly:
            await interaction.followup.send(embed=achievement_unlocked_embed(ach))

    @app_commands.command(name="leaderboard", description="Classement du serveur")
    async def leaderboard(self, interaction: discord.Interaction):
        top = await self.bot.db.get_leaderboard(interaction.guild.id, limit=10)
        embed = discord.Embed(
            title=f"🏆  Classement de {interaction.guild.name}",
            description="*Classement par valeur totale de la collection.*",
            color=config.BOT_ACCENT_COLOR,
        )
        if not top:
            embed.description = "Personne n'a encore de collection. Lance-toi avec `/roll` !"
        else:
            medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 10
            lines = []
            for i, entry in enumerate(top):
                member = interaction.guild.get_member(entry["user_id"])
                name = member.display_name if member else f"Utilisateur {entry['user_id']}"
                lines.append(
                    f"{medals[i]}  **{name}**\n"
                    f"        ↳ {entry['total']} persos · "
                    f"**{entry['total_value']}** {config.CURRENCY_NAME}"
                )
            embed.add_field(name="\u200b", value="\n\n".join(lines), inline=False)
        embed.set_footer(text=config.BOT_NAME)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="achievements",
        description="Affiche tes succès (débloqués ou non)"
    )
    @app_commands.describe(membre="Membre dont on veut voir les succès")
    async def achievements(self, interaction: discord.Interaction,
                            membre: discord.Member = None):
        target = membre or interaction.user
        user = await self.bot.db.get_or_create_user(target.id, interaction.guild.id)
        unlocked_ids = set(user.get("achievements", []))

        embed = discord.Embed(
            title=f"🏆  Succès de {target.display_name}",
            description=f"**{len(unlocked_ids)}** / {len(ACHIEVEMENTS)} débloqués",
            color=config.BOT_ACCENT_COLOR,
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        unlocked_txt = []
        locked_txt = []
        for aid, ach in ACHIEVEMENTS.items():
            if aid in unlocked_ids:
                unlocked_txt.append(f"{ach.emoji}  **{ach.name}** · *{ach.description}*")
            else:
                locked_txt.append(f"⬜  *{ach.name}* · {ach.description}")

        if unlocked_txt:
            val = "\n".join(unlocked_txt)[:1024]
            embed.add_field(name="✅  Débloqués", value=val, inline=False)
        if locked_txt:
            val = "\n".join(locked_txt)[:1024]
            embed.add_field(name="🔒  À débloquer", value=val, inline=False)

        embed.set_footer(text=config.BOT_NAME)
        await interaction.response.send_message(embed=embed, ephemeral=(membre is None))

    # ============================================================
    # AWAKEN : éveille un perso contre des tokens
    # ============================================================
    @app_commands.command(
        name="awaken",
        description=f"Éveille un personnage (+valeur, marque ✨) · coût {config.AWAKEN_COST} {config.CURRENCY_NAME}"
    )
    @app_commands.describe(nom="Nom du personnage à éveiller")
    async def awaken(self, interaction: discord.Interaction, nom: str):
        user_id = interaction.user.id
        guild_id = interaction.guild.id

        char = await self.bot.db.find_user_character(user_id, guild_id, nom)
        if not char:
            await interaction.response.send_message(
                embed=error_embed(f"Aucun personnage nommé `{nom}` dans ta collection."),
                ephemeral=True,
            )
            return

        if char.get("awakened"):
            await interaction.response.send_message(
                embed=warning_embed(
                    f"**{char['character_name']}** est déjà éveillé. "
                    f"(*fonctionnalité multi-niveaux à venir*)"
                ),
                ephemeral=True,
            )
            return

        user = await self.bot.db.get_or_create_user(user_id, guild_id)
        if user["currency"] < config.AWAKEN_COST:
            await interaction.response.send_message(
                embed=error_embed(
                    f"Il te faut **{config.AWAKEN_COST}** {config.CURRENCY_NAME} "
                    f"(tu en as **{user['currency']}**)."
                ),
                ephemeral=True,
            )
            return

        # Calcul nouvelle valeur
        new_value = int(char["value"] * (1 + config.AWAKEN_VALUE_BONUS))

        # Paiement + éveil
        await self.bot.db.update_user_currency(user_id, guild_id, -config.AWAKEN_COST)
        updated = await self.bot.db.awaken_character(char["id"], new_value)

        embed = discord.Embed(
            title=f"✨  Éveil réussi !",
            description=(
                f"**{char['character_name']}** brille maintenant d'une aura nouvelle.\n\n"
                f"Valeur : **{char['value']}** → **{new_value}** {config.CURRENCY_NAME}\n"
                f"Statut : ✨ **Éveillé** (niveau 1)"
            ),
            color=config.BOT_ACCENT_COLOR,
        )
        if char.get("image_url"):
            embed.set_thumbnail(url=char["image_url"])
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(ProfileCog(bot))
