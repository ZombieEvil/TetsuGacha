"""Helpers : raretés, embeds, calculs de gains, streak, pity."""
import discord
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import config


def clean_description(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("~!", "").replace("!~", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_rarity(popularity_score: int) -> str:
    for tier, info in sorted(
        config.RARITY_TIERS.items(),
        key=lambda x: x[1]["min_score"],
        reverse=True
    ):
        if popularity_score >= info["min_score"]:
            return tier
    return "COMMON"


def get_rarity_info(rarity: str) -> Dict:
    return config.RARITY_TIERS.get(rarity, config.RARITY_TIERS["COMMON"])


def rarity_stars(rarity: str) -> str:
    """Retourne les étoiles d'une rareté : ★★★☆☆"""
    stars = get_rarity_info(rarity).get("stars", 1)
    return "★" * stars + "☆" * (5 - stars)


def is_high_rarity(rarity: str) -> bool:
    """True si LEGENDARY ou EPIC ou RARE (4★+)"""
    order = ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY"]
    min_order = order.index(config.PITY_MIN_RARITY)
    return order.index(rarity) >= min_order


def enrich_character(character: Dict) -> Dict:
    rarity = get_rarity(character.get("popularity_score", 0))
    info = get_rarity_info(rarity)
    character["rarity"] = rarity
    character["value"] = info["value"]
    return character


def source_emoji(source_type: str) -> str:
    return {
        "anime": "🌸", "manga": "📖", "movie": "🎬",
        "tv": "📺", "game": "🎮", "comic": "💥",
    }.get(source_type, "✨")


def source_label(source_type: str) -> str:
    return {
        "anime": "Anime", "manga": "Manga", "movie": "Film",
        "tv": "Série", "game": "Jeu vidéo", "comic": "Comic",
    }.get(source_type, "Autre")


def progress_bar(value: int, maxi: int = 100, length: int = 12) -> str:
    filled = int((value / maxi) * length) if maxi else 0
    return "▰" * filled + "▱" * (length - filled)


# ============================================================
# GAINS TetsuToken
# ============================================================
def compute_roll_reward(user_multiplier: float = 0.0) -> int:
    """Tokens gagnés quand on fait un roll (sans claim)."""
    base = config.TOKENS_PER_ROLL_BASE
    return int(base * (1.0 + user_multiplier))


def compute_claim_reward(character: Dict, was_wishlisted: bool,
                         user_multiplier: float = 0.0) -> Tuple[int, Dict]:
    """
    Tokens gagnés quand on claim un perso.
    Retourne (total, breakdown pour affichage).
    """
    base = config.TOKENS_PER_CLAIM_BASE
    rarity = character.get("rarity", "COMMON")
    rarity_mult = config.TOKENS_RARITY_MULTIPLIER.get(rarity, 1.0)
    sub = base * rarity_mult

    wishlist_mult = config.TOKENS_WISHLIST_MULTIPLIER if was_wishlisted else 1.0
    sub *= wishlist_mult

    sub *= (1.0 + user_multiplier)

    total = int(sub)
    breakdown = {
        "base": base,
        "rarity_multiplier": rarity_mult,
        "rarity_name": rarity,
        "wishlist_multiplier": wishlist_mult,
        "user_multiplier": user_multiplier,
        "total": total,
    }
    return total, breakdown


# ============================================================
# STREAK DAILY
# ============================================================
def compute_streak(last_daily_iso: Optional[str], current_streak: int,
                   now: Optional[datetime] = None) -> Tuple[int, str]:
    """
    Calcule le nouveau streak en fonction du dernier daily.
    Retourne (new_streak, reason).
    reason : "continued" | "started" | "reset"
    """
    if now is None:
        now = datetime.utcnow()
    if not last_daily_iso:
        return 1, "started"
    try:
        last = datetime.fromisoformat(last_daily_iso)
    except ValueError:
        return 1, "started"

    delta = now - last
    # Si > reset_hours → reset
    if delta > timedelta(hours=config.STREAK_RESET_HOURS):
        return 1, "reset"
    # Si < 24h → pas encore cumul du lendemain (le cooldown empêchera de toute façon)
    # Si entre 24h et reset_hours → on continue
    return current_streak + 1, "continued"


def streak_daily_bonus(streak: int) -> int:
    """Bonus de tokens selon le streak (plafonné)."""
    bonus = min(streak * config.STREAK_BONUS_PER_DAY, config.STREAK_MAX_BONUS)
    return bonus


def streak_milestone_reward(old_streak: int, new_streak: int) -> int:
    """Retourne les rolls bonus accordés si on vient de franchir un palier."""
    rolls_bonus = 0
    for milestone, rolls in config.STREAK_MILESTONES.items():
        if old_streak < milestone <= new_streak:
            rolls_bonus += rolls
    return rolls_bonus


# ============================================================
# EMBEDS
# ============================================================
def build_character_embed(character: Dict, owner_name: Optional[str] = None,
                          show_owner: bool = False,
                          footer_text: Optional[str] = None,
                          show_awakened: bool = True) -> discord.Embed:
    rarity = character.get("rarity", "COMMON")
    info = get_rarity_info(rarity)
    rarity_label = info.get("label", rarity)

    awakened = character.get("awakened", False)
    awaken_level = character.get("awaken_level", 0)

    # Titre : étoile ★ + emoji rareté + nom + ✨ si éveillé
    title_parts = [info["emoji"], character["name"]]
    if awakened and show_awakened:
        title_parts.append("·")
        title_parts.append("✨" * min(awaken_level, 3))
    title = "  ".join(title_parts)

    src_emoji = source_emoji(character["source_type"])
    src_lbl = source_label(character["source_type"])
    desc_lines = [
        f"{src_emoji}  **{character['source']}**",
        f"*{src_lbl}*  ·  {rarity_stars(rarity)}",
        "",
    ]

    embed = discord.Embed(
        title=title,
        description="\n".join(desc_lines),
        color=info["color"],
    )

    if character.get("image_url"):
        embed.set_image(url=character["image_url"])
    if character.get("source_image_url"):
        embed.set_thumbnail(url=character["source_image_url"])

    pop = character.get("popularity_score", 0)
    embed.add_field(
        name="Rareté",
        value=f"{info['emoji']}  **{rarity_label}**",
        inline=True,
    )
    embed.add_field(
        name="Valeur",
        value=f"**{character.get('value', 0)}**  {config.CURRENCY_NAME}",
        inline=True,
    )
    embed.add_field(
        name=f"Popularité · {pop}",
        value=f"`{progress_bar(pop)}`",
        inline=True,
    )

    if show_owner and owner_name:
        embed.add_field(
            name="\u200b",
            value=f"❤️  Déjà revendiqué par **{owner_name}**",
            inline=False,
        )

    desc = clean_description(character.get("description", ""))
    if desc:
        if len(desc) > 250:
            desc = desc[:250].rsplit(" ", 1)[0] + "…"
        embed.add_field(name="\u200b", value=f"> {desc}", inline=False)

    if footer_text:
        embed.set_footer(text=footer_text)
    return embed


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m" if mins else f"{hours}h"


def make_embed(title: str, description: str = "", color: int = None,
               emoji: str = "") -> discord.Embed:
    if color is None:
        color = config.BOT_COLOR
    if emoji:
        title = f"{emoji}  {title}"
    return discord.Embed(title=title, description=description, color=color)


def success_embed(msg: str) -> discord.Embed:
    return make_embed("Succès", msg, color=0x2ECC71, emoji="✅")


def error_embed(msg: str) -> discord.Embed:
    return make_embed("Erreur", msg, color=0xE74C3C, emoji="❌")


def warning_embed(msg: str) -> discord.Embed:
    return make_embed("Attention", msg, color=0xF39C12, emoji="⚠️")


def info_embed(title: str, msg: str) -> discord.Embed:
    return make_embed(title, msg, color=config.BOT_COLOR, emoji="ℹ️")


def achievement_unlocked_embed(achievement) -> discord.Embed:
    """Embed pour un achievement débloqué."""
    embed = discord.Embed(
        title=f"🏆  Succès débloqué · {achievement.name}",
        description=f"{achievement.emoji}  *{achievement.description}*",
        color=config.BOT_ACCENT_COLOR,
    )
    rewards = []
    if achievement.reward_tokens:
        rewards.append(f"**+{achievement.reward_tokens}** {config.CURRENCY_NAME}")
    if achievement.reward_rolls:
        rewards.append(f"**+{achievement.reward_rolls}** rolls bonus")
    if achievement.reward_multiplier:
        rewards.append(f"**+{int(achievement.reward_multiplier * 100)}%** sur les gains à vie")
    if rewards:
        embed.add_field(name="Récompenses", value="\n".join(rewards), inline=False)
    return embed


# ============================================================
# NOTIFICATIONS (respect du notif_mode du serveur)
# ============================================================
async def send_notification(bot, member, guild, message: str,
                            fallback_channel=None):
    """
    Envoie une notification selon le mode configuré du serveur.
    - dm : DM uniquement (silence si DM fermés)
    - channel : dans le salon fallback_channel
    - both : les deux
    """
    try:
        cfg = await bot.db.get_guild_config(guild.id)
    except Exception:
        cfg = {"notif_mode": "dm"}
    mode = cfg.get("notif_mode", "dm")

    # Préférence user : dm_only_notifs force dm
    try:
        u = await bot.db.get_or_create_user(member.id, guild.id)
        if u.get("dm_only_notifs"):
            mode = "dm"
    except Exception:
        pass

    if mode in ("dm", "both"):
        try:
            await member.send(message)
        except discord.Forbidden:
            pass
    if mode in ("channel", "both") and fallback_channel:
        try:
            await fallback_channel.send(f"{member.mention} {message}")
        except discord.Forbidden:
            pass
