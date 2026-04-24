"""
Système d'achievements / badges.
Chaque achievement a :
  - id : clé unique
  - name, description
  - emoji
  - condition : fonction(user_stats, character=None) -> bool
  - rewards : tokens, rolls bonus, ou multiplicateur permanent sur les gains
"""
from typing import Dict, Callable, Optional


class Achievement:
    def __init__(self, aid: str, name: str, description: str, emoji: str,
                 reward_tokens: int = 0, reward_rolls: int = 0,
                 reward_multiplier: float = 0.0,
                 check: Optional[Callable] = None):
        self.id = aid
        self.name = name
        self.description = description
        self.emoji = emoji
        self.reward_tokens = reward_tokens
        self.reward_rolls = reward_rolls
        self.reward_multiplier = reward_multiplier  # ex: 0.05 = +5% permanent sur gains
        self.check = check


# Stats attendues dans user_stats :
#   total_claims, total_rolls, current_streak, max_streak, total_trades,
#   total_wishlist_hits, legendary_count, epic_count
# character peut être le perso qu'on vient de claim (pour triggers liés à un event)

def _check_first_claim(s, _c=None):
    return s.get("total_claims", 0) >= 1

def _check_10_claims(s, _c=None):
    return s.get("total_claims", 0) >= 10

def _check_50_claims(s, _c=None):
    return s.get("total_claims", 0) >= 50

def _check_100_claims(s, _c=None):
    return s.get("total_claims", 0) >= 100

def _check_first_legendary(s, _c=None):
    return s.get("legendary_count", 0) >= 1

def _check_3_legendaries(s, _c=None):
    return s.get("legendary_count", 0) >= 3

def _check_streak_7(s, _c=None):
    return s.get("max_streak", 0) >= 7

def _check_streak_30(s, _c=None):
    return s.get("max_streak", 0) >= 30

def _check_first_trade(s, _c=None):
    return s.get("total_trades", 0) >= 1

def _check_10_trades(s, _c=None):
    return s.get("total_trades", 0) >= 10

def _check_wishlist_hit(s, _c=None):
    return s.get("total_wishlist_hits", 0) >= 1

def _check_100_rolls(s, _c=None):
    return s.get("total_rolls", 0) >= 100

def _check_1000_rolls(s, _c=None):
    return s.get("total_rolls", 0) >= 1000


ACHIEVEMENTS: Dict[str, Achievement] = {
    # Progression
    "first_claim": Achievement(
        "first_claim", "Première rencontre", "Revendique ton premier personnage",
        "💖", reward_tokens=100, check=_check_first_claim,
    ),
    "collector_10": Achievement(
        "collector_10", "Apprenti collectionneur", "Revendique 10 personnages",
        "📚", reward_tokens=300, reward_rolls=3, check=_check_10_claims,
    ),
    "collector_50": Achievement(
        "collector_50", "Vrai collectionneur", "Revendique 50 personnages",
        "🎴", reward_tokens=1000, reward_rolls=5, reward_multiplier=0.05,
        check=_check_50_claims,
    ),
    "collector_100": Achievement(
        "collector_100", "Maître collectionneur", "Revendique 100 personnages",
        "👑", reward_tokens=3000, reward_rolls=10, reward_multiplier=0.10,
        check=_check_100_claims,
    ),

    # Rareté
    "first_legendary": Achievement(
        "first_legendary", "Rareté ultime", "Obtiens ton premier personnage Légendaire",
        "🌟", reward_tokens=500, check=_check_first_legendary,
    ),
    "three_legendaries": Achievement(
        "three_legendaries", "Chanceux", "Obtiens 3 personnages Légendaires",
        "✨", reward_tokens=1500, reward_rolls=5, check=_check_3_legendaries,
    ),

    # Streak
    "streak_7": Achievement(
        "streak_7", "Une semaine d'amour", "Connecte-toi 7 jours consécutifs",
        "🔥", reward_tokens=500, reward_rolls=3, check=_check_streak_7,
    ),
    "streak_30": Achievement(
        "streak_30", "Dévouement", "Connecte-toi 30 jours consécutifs",
        "💎", reward_tokens=3000, reward_rolls=10, reward_multiplier=0.15,
        check=_check_streak_30,
    ),

    # Social
    "first_trade": Achievement(
        "first_trade", "Échange cordial", "Réussis ton premier échange",
        "🤝", reward_tokens=200, check=_check_first_trade,
    ),
    "trader_10": Achievement(
        "trader_10", "Négociateur", "Réussis 10 échanges",
        "💼", reward_tokens=1000, reward_multiplier=0.05, check=_check_10_trades,
    ),
    "wishlist_hit": Achievement(
        "wishlist_hit", "Coup du destin", "Revendique un perso qui était sur ta wishlist",
        "🎯", reward_tokens=300, check=_check_wishlist_hit,
    ),

    # Volume
    "rolls_100": Achievement(
        "rolls_100", "Accro au gacha", "Effectue 100 rolls",
        "🎰", reward_tokens=400, reward_rolls=3, check=_check_100_rolls,
    ),
    "rolls_1000": Achievement(
        "rolls_1000", "Addict", "Effectue 1000 rolls",
        "🎲", reward_tokens=3000, reward_rolls=10, reward_multiplier=0.10,
        check=_check_1000_rolls,
    ),
}


def check_achievements(user_stats: Dict, already_unlocked: list,
                        character: Optional[Dict] = None) -> list:
    """
    Retourne la liste des achievements NOUVELLEMENT débloqués.
    """
    newly_unlocked = []
    for aid, ach in ACHIEVEMENTS.items():
        if aid in already_unlocked:
            continue
        try:
            if ach.check and ach.check(user_stats, character):
                newly_unlocked.append(ach)
        except Exception:
            pass
    return newly_unlocked


def get_achievement(aid: str) -> Optional[Achievement]:
    return ACHIEVEMENTS.get(aid)
