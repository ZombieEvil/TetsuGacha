# =====================================================
# CONFIGURATION TetsuGacha - Renomme en config.py
# =====================================================

# --- TOKEN DISCORD ---
DISCORD_TOKEN = "MTQ5NjMwMDk1MDY4Njc5ODAwNQ.G_Ciwj.TEhkaOYCwxO0jHdUA63qiKJDWAarfK2drT4Pmo"

# --- IDENTITÉ DU BOT ---
BOT_NAME = "TetsuGacha"
BOT_TAGLINE = "Le gacha ultime de ton serveur"
BOT_COLOR = 0xE91E63
BOT_ACCENT_COLOR = 0xFFD700

# --- CLÉS API (optionnelles sauf AniList qui est sans clé) ---
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

# --- MONNAIE : TetsuToken (XP + argent) ---
CURRENCY_NAME = "🪙"
CURRENCY_NAME_LONG = "TetsuTokens"
STARTING_CURRENCY = 500
DAILY_REWARD = 200  # Récompense de base (modifiée par le streak)

# --- GAINS DE TETSUTOKEN (système XP + argent) ---
# Un roll qui rate (perso pas claim) rapporte un peu, un claim rapporte gros
TOKENS_PER_ROLL_BASE = 5      # Tokens par roll (réagir)
TOKENS_PER_CLAIM_BASE = 50    # Tokens par claim (gros bonus)
TOKENS_WISHLIST_MULTIPLIER = 3.0  # x3 si le perso était sur la wishlist
# Bonus selon rareté du perso claim
TOKENS_RARITY_MULTIPLIER = {
    "LEGENDARY": 5.0,
    "EPIC": 3.0,
    "RARE": 1.8,
    "UNCOMMON": 1.2,
    "COMMON": 1.0,
}

# --- STREAK DAILY (connexions consécutives) ---
STREAK_BONUS_PER_DAY = 50     # +50 tokens par jour consécutif
STREAK_MAX_BONUS = 500        # Plafond
STREAK_RESET_HOURS = 48       # Si > 48h sans daily, le streak reset
STREAK_MILESTONES = {         # Bonus rolls à certains paliers de streak
    7: 3,    # 7 jours → +3 rolls bonus
    14: 5,   # 14 jours → +5 rolls bonus
    30: 10,  # 30 jours → +10 rolls bonus
}

# --- PITY SYSTEM (garanti après X rolls sans un bon perso) ---
PITY_THRESHOLD = 20           # 20 rolls sans RARE+ → garanti RARE+ au 21e
PITY_MIN_RARITY = "RARE"      # Rareté minimale garantie

# --- AUTO-CLAIM (feature premium payante en tokens) ---
MAX_AUTO_CLAIMS = 3            # Max 3 persos en auto-claim actifs par user
AUTO_CLAIM_COST = 300          # Coût en tokens pour activer un auto-claim
AUTO_CLAIM_COOLDOWN_HOURS = 6  # Entre 2 déclenchements d'auto-claim

# --- ÉVEIL DE PERSO (awaken) ---
AWAKEN_COST = 500              # Coût en tokens pour éveiller un perso
AWAKEN_VALUE_BONUS = 0.5       # +50% de valeur

# --- ÉVÉNEMENTS SERVEUR ---
# Double tokens : multiplicateur appliqué aux gains pendant l'event
EVENT_DOUBLE_TOKENS_MULTIPLIER = 2.0
EVENT_MAX_DURATION_HOURS = 72      # Durée max d'un event en heures
# Limited character : boost de chance pour qu'il apparaisse
EVENT_LIMITED_BOOST_PERCENT = 15   # 15% de chance à chaque roll que ce soit le perso limited
EVENT_LIMITED_VALUE_BONUS = 1.0    # +100% de valeur sur le perso limited
# Rareté minimum pour qu'un perso puisse être tiré comme "limited"
EVENT_LIMITED_MIN_RARITY = "RARE"

# --- SHOP : ITEMS ACHETABLES ---
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
SHOWCASE_GRID_SIZE = 3              # grille 3x3 = top 9 persos
SHOWCASE_IMAGE_SIZE = 900           # taille en px de l'image (carrée)

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
