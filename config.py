import os

# =====================================================
# CONFIGURATION TetsuGacha
# =====================================================

# --- TOKEN DISCORD (sécurisé) ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "METS_TON_TOKEN_DISCORD_ICI")

# --- IDENTITÉ DU BOT ---
BOT_NAME = "TetsuGacha"
BOT_TAGLINE = "Le gacha ultime de ton serveur"
BOT_COLOR = 0xE91E63
BOT_ACCENT_COLOR = 0xFFD700

# --- CLÉS API (optionnelles) ---
TMDB_API_KEY = ""
IGDB_CLIENT_ID = ""
IGDB_CLIENT_SECRET = ""
COMICVINE_API_KEY = ""

# --- CONFIGURATION GÉNÉRALE ---
BOT_PREFIX = "!"
OWNER_ID = 0

# --- GAMEPLAY ---
ROLLS_PER_HOUR = 10
CLAIM_COOLDOWN_MINUTES = 180
CLAIM_REACT_TIME_SECONDS = 45
MAX_WISHLIST_SIZE = 20

# --- MONNAIE : TetsuToken ---
CURRENCY_NAME = "🪙"
CURRENCY_NAME_LONG = "TetsuTokens"
STARTING_CURRENCY = 500
DAILY_REWARD = 200

# --- GAINS DE TETSUTOKEN ---
TOKENS_PER_ROLL_BASE = 5
TOKENS_PER_CLAIM_BASE = 50
TOKENS_WISHLIST_MULTIPLIER = 3.0
TOKENS_RARITY_MULTIPLIER = {
    "LEGENDARY": 5.0,
    "EPIC": 3.0,
    "RARE": 1.8,
    "UNCOMMON": 1.2,
    "COMMON": 1.0,
}

# --- STREAK DAILY ---
STREAK_BONUS_PER_DAY = 50
STREAK_MAX_BONUS = 500
STREAK_RESET_HOURS = 48
STREAK_MILESTONES = {7: 3, 14: 5, 30: 10}

# --- PITY SYSTEM ---
PITY_THRESHOLD = 20
PITY_MIN_RARITY = "RARE"

# --- AUTO-CLAIM ---
MAX_AUTO_CLAIMS = 3
AUTO_CLAIM_COST = 300
AUTO_CLAIM_COOLDOWN_HOURS = 6

# --- ÉVEIL DE PERSO ---
AWAKEN_COST = 500
AWAKEN_VALUE_BONUS = 0.5

# --- ÉVÉNEMENTS SERVEUR ---
EVENT_DOUBLE_TOKENS_MULTIPLIER = 2.0
EVENT_MAX_DURATION_HOURS = 72
EVENT_LIMITED_BOOST_PERCENT = 15
EVENT_LIMITED_VALUE_BONUS = 1.0
EVENT_LIMITED_MIN_RARITY = "RARE"

# --- SHOP ---
SHOP_ITEMS = {
    "rarity_protection": {
        "name": "Protection Rareté",
        "emoji": "🛡️",
        "description": "Ton prochain roll est garanti minimum RARE.",
        "price": 400,
        "min_rarity_guaranteed": "RARE",
    },
    "rarity_protection_epic": {
        "name": "Protection Épique",
        "emoji": "⚔️",
        "description": "Ton prochain roll est garanti minimum ÉPIQUE.",
        "price": 1500,
        "min_rarity_guaranteed": "EPIC",
    },
    "bonus_rolls_5": {
        "name": "Pack 5 Rolls",
        "emoji": "🎟️",
        "description": "Obtiens 5 rolls bonus à utiliser quand tu veux.",
        "price": 300,
        "bonus_rolls": 5,
    },
}

# --- SHOWCASE ---
SHOWCASE_GRID_SIZE = 3
SHOWCASE_IMAGE_SIZE = 900

# --- RARETÉS ---
RARITY_TIERS = {
    "LEGENDARY": {"emoji": "🌟", "min_score": 90, "color": 0xFFD700, "value": 1000, "label": "Légendaire", "stars": 5},
    "EPIC":      {"emoji": "💜", "min_score": 70, "color": 0x9B59B6, "value": 500,  "label": "Épique",     "stars": 4},
    "RARE":      {"emoji": "💙", "min_score": 50, "color": 0x3498DB, "value": 200,  "label": "Rare",       "stars": 3},
    "UNCOMMON":  {"emoji": "💚", "min_score": 25, "color": 0x2ECC71, "value": 75,   "label": "Peu commun", "stars": 2},
    "COMMON":    {"emoji": "🤍", "min_score": 0,  "color": 0x95A5A6, "value": 25,   "label": "Commun",     "stars": 1},
}

# --- STOCKAGE ---
DATABASE_PATH = "data"

# --- LOGS ---
LOG_LEVEL = "INFO"