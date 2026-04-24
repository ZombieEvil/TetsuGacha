"""
/roll avec :
- Gains TetsuToken automatiques (même sans claim)
- Pity system (garanti RARE+ après X rolls)
- Auto-claim trigger si le perso correspond à un auto-claim
- Notifications wishlist intelligentes (DM ou channel selon config)
- Achievements déclenchés sur roll/claim
"""
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import random

import config
from utils.helpers import (
    enrich_character, build_character_embed, format_duration,
    error_embed, warning_embed, success_embed, is_high_rarity,
    compute_roll_reward, compute_claim_reward, rarity_stars,
    achievement_unlocked_embed, send_notification,
)
from utils.achievements import check_achievements


async def grant_rewards_for_claim(bot, user_id: int, guild_id: int,
                                    character: dict, was_wishlisted: bool,
                                    interaction_channel=None):
    """
    Applique tous les effets d'un claim :
    - Tokens gagnés (selon rareté + wishlist + multiplicateur user + event double_tokens)
    - Compteurs augmentés
    - Achievements vérifiés
    Retourne (tokens_gagnes, breakdown, achievements_debloques)
    """
    user = await bot.db.get_or_create_user(user_id, guild_id)
    multiplier = user.get("earn_multiplier", 0.0)
    tokens, breakdown = compute_claim_reward(character, was_wishlisted, multiplier)

    # Event double tokens ?
    event = await bot.db.get_active_event_by_type(guild_id, "double_tokens")
    if event:
        mult = event.get("data", {}).get("multiplier", config.EVENT_DOUBLE_TOKENS_MULTIPLIER)
        tokens = int(tokens * mult)
        breakdown["event_double_tokens"] = mult

    await bot.db.update_user_currency(user_id, guild_id, tokens)
    await bot.db.increment_user_field(user_id, guild_id, "total_claims", 1)

    if character.get("rarity") == "LEGENDARY":
        await bot.db.increment_user_field(user_id, guild_id, "legendary_count", 1)
    elif character.get("rarity") == "EPIC":
        await bot.db.increment_user_field(user_id, guild_id, "epic_count", 1)

    if was_wishlisted:
        await bot.db.increment_user_field(user_id, guild_id, "total_wishlist_hits", 1)

    # Achievements
    user_updated = await bot.db.get_or_create_user(user_id, guild_id)
    newly = check_achievements(user_updated, user_updated.get("achievements", []), character)
    for ach in newly:
        await bot.db.add_achievement(user_id, guild_id, ach.id)
        if ach.reward_tokens:
            await bot.db.update_user_currency(user_id, guild_id, ach.reward_tokens)
        if ach.reward_rolls:
            await bot.db.increment_user_field(user_id, guild_id, "bonus_rolls", ach.reward_rolls)
        if ach.reward_multiplier:
            await bot.db.add_earn_multiplier(user_id, guild_id, ach.reward_multiplier)

    return tokens, breakdown, newly


class ClaimView(discord.ui.View):
    def __init__(self, bot, character: dict, guild_id: int,
                 was_wishlisted_for: list = None,
                 timeout: int = None):
        super().__init__(timeout=timeout or config.CLAIM_REACT_TIME_SECONDS)
        self.bot = bot
        self.character = character
        self.guild_id = guild_id
        self.was_wishlisted_for = was_wishlisted_for or []  # user ids
        self.claimed = False
        self.message = None

    @discord.ui.button(label="Claim", emoji="💖", style=discord.ButtonStyle.danger)
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed:
            await interaction.response.send_message(
                embed=warning_embed("Trop tard, ce personnage a déjà été revendiqué."),
                ephemeral=True,
            )
            return

        user_id = interaction.user.id
        guild_id = self.guild_id

        user = await self.bot.db.get_or_create_user(user_id, guild_id)
        now = datetime.utcnow()
        if user.get("last_claim"):
            last_claim = datetime.fromisoformat(user["last_claim"])
            cd_end = last_claim + timedelta(minutes=config.CLAIM_COOLDOWN_MINUTES)
            if now < cd_end:
                remaining = int((cd_end - now).total_seconds())
                await interaction.response.send_message(
                    embed=warning_embed(
                        f"Tu dois attendre **{format_duration(remaining)}** avant de pouvoir claim à nouveau."
                    ),
                    ephemeral=True,
                )
                return

        existing = await self.bot.db.is_character_claimed(
            guild_id, self.character["id"], self.character["source_type"]
        )
        if existing:
            owner = interaction.guild.get_member(existing["user_id"])
            owner_name = owner.display_name if owner else "quelqu'un"
            await interaction.response.send_message(
                embed=warning_embed(
                    f"**{self.character['name']}** appartient déjà à **{owner_name}**."
                ),
                ephemeral=True,
            )
            return

        self.claimed = True
        await self.bot.db.add_character(user_id, guild_id, self.character)
        await self.bot.db.set_user_field(user_id, guild_id, "last_claim", now.isoformat())

        was_wishlisted = user_id in self.was_wishlisted_for
        tokens_gained, breakdown, new_achievements = await grant_rewards_for_claim(
            self.bot, user_id, guild_id, self.character, was_wishlisted,
            interaction.channel,
        )

        if hasattr(self.bot, "dashboard"):
            self.bot.dashboard.log_claim(
                interaction.user.display_name,
                self.character["name"],
                self.character["source"],
                self.character.get("rarity", "COMMON"),
            )

        button.disabled = True
        button.label = f"Revendiqué par {interaction.user.display_name}"
        button.style = discord.ButtonStyle.success
        await interaction.response.edit_message(view=self)

        # Message de claim avec gains détaillés
        reward_text = f"**+{tokens_gained}** {config.CURRENCY_NAME_LONG} {config.CURRENCY_NAME}"
        if was_wishlisted:
            reward_text += f"  ·  🎯 *bonus wishlist ×{config.TOKENS_WISHLIST_MULTIPLIER:g}*"

        await interaction.followup.send(
            f"💖  **{interaction.user.mention}** a revendiqué **{self.character['name']}** "
            f"de *{self.character['source']}*  ·  {rarity_stars(self.character['rarity'])}\n"
            f"{reward_text}"
        )

        # Achievements débloqués
        for ach in new_achievements:
            await interaction.followup.send(embed=achievement_unlocked_embed(ach))

        # Notifier les wishers (sauf le claimer) → DM ou channel selon config
        for wl_id in self.was_wishlisted_for:
            if wl_id == user_id:
                continue
            member = interaction.guild.get_member(wl_id)
            if member:
                if hasattr(self.bot, "dashboard"):
                    self.bot.dashboard.log_wishlist_hit(
                        interaction.user.display_name, self.character["name"]
                    )
                await send_notification(
                    self.bot, member, interaction.guild,
                    f"🔔  **{self.character['name']}** (de ta wishlist) vient d'être "
                    f"revendiqué par **{interaction.user.display_name}** "
                    f"sur *{interaction.guild.name}*.",
                    fallback_channel=interaction.channel,
                )

        self.stop()

    async def on_timeout(self):
        if not self.claimed:
            for child in self.children:
                child.disabled = True
            try:
                if self.message:
                    await self.message.edit(view=self)
            except discord.NotFound:
                pass


class RollsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="roll", description="Pioche un personnage aléatoire")
    async def roll(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        guild_id = interaction.guild.id

        user = await self.bot.db.get_or_create_user(user_id, guild_id)
        now = datetime.utcnow()
        rolls_used = user.get("rolls_used", 0)
        bonus_rolls = user.get("bonus_rolls", 0)
        last_roll = user.get("last_roll")

        # Reset horaire
        if last_roll:
            last_roll_dt = datetime.fromisoformat(last_roll)
            if now - last_roll_dt >= timedelta(hours=1):
                rolls_used = 0

        # Total dispo = quota horaire + bonus permanents
        total_available = config.ROLLS_PER_HOUR + bonus_rolls
        if rolls_used >= total_available:
            if last_roll:
                reset_at = datetime.fromisoformat(last_roll) + timedelta(hours=1)
                remaining = int((reset_at - now).total_seconds())
                if remaining > 0:
                    await interaction.response.send_message(
                        embed=warning_embed(
                            f"Tu as utilisé tous tes rolls. Reset dans **{format_duration(remaining)}**."
                        ),
                        ephemeral=True,
                    )
                    return

        # Check salon
        guild_cfg = await self.bot.db.get_guild_config(guild_id)
        roll_ch_id = guild_cfg.get("roll_channel_id")
        if roll_ch_id and interaction.channel.id != roll_ch_id:
            ch = interaction.guild.get_channel(roll_ch_id)
            if ch:
                await interaction.response.send_message(
                    embed=warning_embed(f"Les rolls se font dans {ch.mention}."),
                    ephemeral=True,
                )
                return

        mode = guild_cfg.get("active_mode", "all")
        await interaction.response.defer()

        # ==== EVENTS ACTIFS ====
        active_events = await self.bot.db.get_active_events(guild_id)
        limited_event = next((e for e in active_events if e["type"] == "limited_character"), None)
        double_tokens_event = next((e for e in active_events if e["type"] == "double_tokens"), None)

        # ==== RARITY PROTECTION (item shop) ====
        protection = await self.bot.db.consume_rarity_protection(user_id, guild_id)

        # ==== PITY SYSTEM ====
        pity = user.get("pity_counter", 0)
        trigger_pity = pity >= config.PITY_THRESHOLD

        # Déterminer la rareté min garantie (on prend la plus haute entre pity et protection)
        min_rarity_guaranteed = None
        rarity_order = ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY"]
        if trigger_pity:
            min_rarity_guaranteed = config.PITY_MIN_RARITY
        if protection:
            if (min_rarity_guaranteed is None or
                    rarity_order.index(protection) > rarity_order.index(min_rarity_guaranteed)):
                min_rarity_guaranteed = protection

        character = None
        is_limited_hit = False

        # ==== LIMITED CHARACTER : tirage prioritaire ====
        if limited_event:
            roll_chance = random.randint(1, 100)
            if roll_chance <= config.EVENT_LIMITED_BOOST_PERCENT:
                lim_char = limited_event.get("data", {}).get("character")
                if lim_char:
                    # Vérifier qu'il n'est pas déjà claim
                    already = await self.bot.db.is_character_claimed(
                        guild_id, lim_char["id"], lim_char["source_type"]
                    )
                    if not already:
                        character = dict(lim_char)
                        # Boost de valeur
                        base_val = character.get("value", 0)
                        character["value"] = int(base_val * (1 + config.EVENT_LIMITED_VALUE_BONUS))
                        is_limited_hit = True

        # ==== TIRAGE NORMAL (avec rareté min garantie si applicable) ====
        if character is None:
            if min_rarity_guaranteed:
                min_idx = rarity_order.index(min_rarity_guaranteed)
                for _ in range(6):
                    c = await self.bot.fetcher.get_random_character(mode=mode)
                    if not c:
                        continue
                    c = enrich_character(c)
                    if rarity_order.index(c["rarity"]) >= min_idx:
                        character = c
                        break
                if not character:
                    character = await self.bot.fetcher.get_random_character(mode=mode)
                    if character:
                        character = enrich_character(character)
            else:
                character = await self.bot.fetcher.get_random_character(mode=mode)
                if character:
                    character = enrich_character(character)

        if not character:
            if hasattr(self.bot, "dashboard"):
                self.bot.dashboard.log_api("character_fetch", success=False)
            await interaction.followup.send(
                embed=error_embed("Impossible de récupérer un personnage. Réessaie dans quelques secondes."),
                ephemeral=True,
            )
            return

        if hasattr(self.bot, "dashboard"):
            self.bot.dashboard.log_api("character_fetch", success=True)
            self.bot.dashboard.log_roll(
                interaction.user.display_name,
                character["name"], character["source"], character["rarity"],
            )

        existing = await self.bot.db.is_character_claimed(
            guild_id, character["id"], character["source_type"]
        )

        # ==== GAINS TOKEN AUTOMATIQUES (juste pour le roll) ====
        roll_reward = compute_roll_reward(user.get("earn_multiplier", 0.0))
        # Event double tokens
        if double_tokens_event:
            mult = double_tokens_event.get("data", {}).get("multiplier",
                                                             config.EVENT_DOUBLE_TOKENS_MULTIPLIER)
            roll_reward = int(roll_reward * mult)
        await self.bot.db.update_user_currency(user_id, guild_id, roll_reward)

        # ==== COMPTEURS ====
        await self.bot.db.set_user_field(user_id, guild_id, "last_roll", now.isoformat())
        await self.bot.db.set_user_field(user_id, guild_id, "rolls_used", rolls_used + 1)
        await self.bot.db.increment_user_field(user_id, guild_id, "total_rolls", 1)

        # Pity : reset si perso high rarity, sinon incrémente
        if is_high_rarity(character["rarity"]):
            await self.bot.db.set_user_field(user_id, guild_id, "pity_counter", 0)
        else:
            await self.bot.db.increment_user_field(user_id, guild_id, "pity_counter", 1)

        # Achievements roll
        user_updated = await self.bot.db.get_or_create_user(user_id, guild_id)
        newly = check_achievements(user_updated, user_updated.get("achievements", []))

        # ==== AUTO-CLAIM : un user a-t-il ce perso en auto-claim actif ? ====
        auto_claimed_by_id = None
        if not existing:
            matching_ac = await self.bot.db.find_matching_auto_claims(
                guild_id, character["id"], character["source_type"]
            )
            for ac in matching_ac:
                # Vérifier cooldown auto-claim
                can_trigger = True
                if ac.get("last_triggered"):
                    try:
                        last_t = datetime.fromisoformat(ac["last_triggered"])
                        if now - last_t < timedelta(hours=config.AUTO_CLAIM_COOLDOWN_HOURS):
                            can_trigger = False
                    except ValueError:
                        pass
                if not can_trigger:
                    continue

                # Vérifier cooldown claim du user
                ac_user = await self.bot.db.get_or_create_user(ac["user_id"], guild_id)
                if ac_user.get("last_claim"):
                    try:
                        last_c = datetime.fromisoformat(ac_user["last_claim"])
                        if now - last_c < timedelta(minutes=config.CLAIM_COOLDOWN_MINUTES):
                            continue
                    except ValueError:
                        pass

                # Déclenchement auto-claim !
                await self.bot.db.add_character(ac["user_id"], guild_id, character)
                await self.bot.db.set_user_field(
                    ac["user_id"], guild_id, "last_claim", now.isoformat()
                )
                await self.bot.db.mark_auto_claim_triggered(ac["id"])

                # Gains
                wl_users = await self.bot.db.find_users_wishlisting(
                    guild_id, character["id"], character["source_type"]
                )
                was_wl = ac["user_id"] in wl_users
                ac_tokens, _, ac_newly = await grant_rewards_for_claim(
                    self.bot, ac["user_id"], guild_id, character, was_wl,
                    interaction.channel,
                )
                auto_claimed_by_id = ac["user_id"]
                if hasattr(self.bot, "dashboard"):
                    m = interaction.guild.get_member(ac["user_id"])
                    name = m.display_name if m else f"user {ac['user_id']}"
                    self.bot.dashboard.log_claim(
                        name + " (AUTO)",
                        character["name"], character["source"], character["rarity"],
                    )
                break  # un seul auto-claim par roll

        # ==== EMBED ====
        rolls_left = total_available - (rolls_used + 1)
        owner_name = None
        show_owner = False
        if existing:
            m = interaction.guild.get_member(existing["user_id"])
            owner_name = m.display_name if m else None
            show_owner = True
        elif auto_claimed_by_id:
            m = interaction.guild.get_member(auto_claimed_by_id)
            owner_name = m.display_name if m else None
            show_owner = True

        pity_text = ""
        new_user = await self.bot.db.get_or_create_user(user_id, guild_id)
        new_pity = new_user.get("pity_counter", 0)
        if new_pity > 0:
            pity_text = f"  ·  ⭐ Pity {new_pity}/{config.PITY_THRESHOLD}"

        footer_parts = [
            interaction.user.display_name,
            f"{rolls_left}/{total_available} rolls",
            f"+{roll_reward} {config.CURRENCY_NAME}",
        ]
        if double_tokens_event:
            footer_parts.append("💰×2 actif")
        footer = "  ·  ".join(footer_parts) + pity_text

        if is_limited_hit:
            footer = "⚡ LIMITED HIT · " + footer
        elif trigger_pity and not protection:
            footer = "🎁 PITY DÉCLENCHÉ · " + footer
        elif protection:
            footer = f"🛡️ Protection {protection} · " + footer

        embed = build_character_embed(
            character,
            owner_name=owner_name,
            show_owner=show_owner,
            footer_text=footer,
        )

        # Liste des wishers pour le ClaimView
        wl_users = []
        if not existing and not auto_claimed_by_id:
            wl_users = await self.bot.db.find_users_wishlisting(
                guild_id, character["id"], character["source_type"]
            )

        if existing or auto_claimed_by_id:
            await interaction.followup.send(embed=embed)
            # Si auto-claim → message spécifique
            if auto_claimed_by_id:
                member = interaction.guild.get_member(auto_claimed_by_id)
                name = member.mention if member else f"<@{auto_claimed_by_id}>"
                await interaction.followup.send(
                    f"🤖  **Auto-claim déclenché** pour {name} !"
                )
        else:
            view = ClaimView(self.bot, character, guild_id, was_wishlisted_for=wl_users)
            msg = await interaction.followup.send(embed=embed, view=view)
            view.message = msg

        # Achievements suite au roll
        for ach in newly:
            await self.bot.db.add_achievement(user_id, guild_id, ach.id)
            if ach.reward_tokens:
                await self.bot.db.update_user_currency(user_id, guild_id, ach.reward_tokens)
            if ach.reward_rolls:
                await self.bot.db.increment_user_field(user_id, guild_id, "bonus_rolls", ach.reward_rolls)
            if ach.reward_multiplier:
                await self.bot.db.add_earn_multiplier(user_id, guild_id, ach.reward_multiplier)
            await interaction.followup.send(embed=achievement_unlocked_embed(ach))


async def setup(bot):
    await bot.add_cog(RollsCog(bot))
