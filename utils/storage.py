"""
Stockage JSON avec support complet :
  - users : currency, cooldowns, streak, pity counter, achievements, stats détaillées
  - characters : avec champs awaken, claim_context
  - wishlists
  - guild_config : + options DM-only
  - trades
  - auto_claims : liste des persos en auto-claim
  - counters

Écriture atomique + verrous async + autosave toutes les 3s.
"""
import asyncio
import json
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Set


class JSONStorage:
    def __init__(self, folder: str):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

        self._files = {
            "users":            self.folder / "users.json",
            "characters":       self.folder / "claimed_characters.json",
            "wishlists":        self.folder / "wishlists.json",
            "guilds":           self.folder / "guild_config.json",
            "trades":           self.folder / "trades.json",
            "auto_claims":      self.folder / "auto_claims.json",
            "events":           self.folder / "events.json",
            "global_profiles":  self.folder / "global_profiles.json",
            "counters":         self.folder / "counters.json",
        }

        self._locks = {k: asyncio.Lock() for k in self._files}
        self._cache: Dict[str, Any] = {}
        self._dirty: Set[str] = set()
        self._autosave_task = None

    # ============================================================
    # I/O
    # ============================================================
    def _default_for(self, key: str) -> Any:
        if key in ("trades", "auto_claims", "events"):
            return []
        if key == "counters":
            return {
                "next_character_id": 1,
                "next_trade_id": 1,
                "next_autoclaim_id": 1,
                "next_event_id": 1,
            }
        return {}

    def _load_file(self, key: str) -> Any:
        path = self._files[key]
        if not path.exists():
            return self._default_for(key)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            backup = path.with_suffix(f".corrupt-{int(datetime.utcnow().timestamp())}.json")
            try:
                shutil.copy(path, backup)
            except OSError:
                pass
            return self._default_for(key)

    def _save_file_sync(self, key: str):
        path = self._files[key]
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(self.folder), prefix=f".{key}-", suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(self._cache[key], f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    async def _save(self, key: str):
        self._dirty.add(key)

    async def _flush_now(self, keys: Optional[Set[str]] = None):
        targets = keys if keys is not None else set(self._dirty)
        for key in list(targets):
            async with self._locks[key]:
                if key in self._cache:
                    await asyncio.to_thread(self._save_file_sync, key)
                self._dirty.discard(key)

    async def _autosave_loop(self):
        try:
            while True:
                await asyncio.sleep(3.0)
                if self._dirty:
                    await self._flush_now()
        except asyncio.CancelledError:
            if self._dirty:
                await self._flush_now()
            raise

    async def init(self):
        for key in self._files:
            self._cache[key] = await asyncio.to_thread(self._load_file, key)
        if self._autosave_task is None or self._autosave_task.done():
            self._autosave_task = asyncio.create_task(self._autosave_loop())

    async def close(self):
        if self._autosave_task:
            self._autosave_task.cancel()
            try:
                await self._autosave_task
            except asyncio.CancelledError:
                pass
        await self._flush_now()

    # ============================================================
    # Helpers internes
    # ============================================================
    def _next_id(self, counter_key: str) -> int:
        counters = self._cache["counters"]
        val = counters.get(counter_key, 1)
        counters[counter_key] = val + 1
        self._dirty.add("counters")
        return val

    def _guild_users(self, guild_id: int) -> Dict[str, Any]:
        return self._cache["users"].setdefault(str(guild_id), {})

    def _guild_chars(self, guild_id: int) -> List[Dict]:
        return self._cache["characters"].setdefault(str(guild_id), [])

    def _user_wishlist(self, guild_id: int, user_id: int) -> List[Dict]:
        gmap = self._cache["wishlists"].setdefault(str(guild_id), {})
        return gmap.setdefault(str(user_id), [])

    # ============================================================
    # UTILISATEURS
    # ============================================================
    async def get_or_create_user(self, user_id: int, guild_id: int) -> Dict[str, Any]:
        async with self._locks["users"]:
            users = self._guild_users(guild_id)
            uid = str(user_id)
            if uid not in users:
                users[uid] = {
                    "user_id": user_id,
                    "guild_id": guild_id,
                    "currency": 500,
                    "last_roll": None,
                    "rolls_used": 0,
                    "bonus_rolls": 0,   # rolls bonus cumulés (streak, achievements)
                    "last_claim": None,
                    "last_daily": None,
                    "total_claims": 0,
                    "total_rolls": 0,
                    "total_trades": 0,
                    "total_wishlist_hits": 0,
                    "legendary_count": 0,
                    "epic_count": 0,
                    # Streak
                    "current_streak": 0,
                    "max_streak": 0,
                    # Pity system
                    "pity_counter": 0,  # rolls sans RARE+
                    # Achievements
                    "achievements": [],
                    "earn_multiplier": 0.0,  # cumul des bonus permanents
                    # Préférences notification
                    "dm_only_notifs": False,
                    "created_at": datetime.utcnow().isoformat(),
                }
                await self._save("users")
            else:
                # Migration : ajoute les nouveaux champs si ils manquent
                u = users[uid]
                defaults = {
                    "bonus_rolls": 0, "total_rolls": 0, "total_trades": 0,
                    "total_wishlist_hits": 0, "legendary_count": 0, "epic_count": 0,
                    "current_streak": 0, "max_streak": 0, "pity_counter": 0,
                    "achievements": [], "earn_multiplier": 0.0, "dm_only_notifs": False,
                }
                changed = False
                for k, v in defaults.items():
                    if k not in u:
                        u[k] = v
                        changed = True
                if changed:
                    await self._save("users")
            return dict(users[uid])

    async def update_user_currency(self, user_id: int, guild_id: int, amount: int):
        await self.get_or_create_user(user_id, guild_id)
        async with self._locks["users"]:
            user = self._guild_users(guild_id)[str(user_id)]
            user["currency"] = max(0, user.get("currency", 0) + amount)
            await self._save("users")

    async def set_user_field(self, user_id: int, guild_id: int, field: str, value: Any):
        allowed = {
            "last_roll", "rolls_used", "bonus_rolls", "last_claim", "last_daily",
            "total_claims", "total_rolls", "total_trades", "total_wishlist_hits",
            "legendary_count", "epic_count", "currency", "current_streak",
            "max_streak", "pity_counter", "dm_only_notifs", "earn_multiplier",
        }
        if field not in allowed:
            raise ValueError(f"Champ non autorisé: {field}")
        await self.get_or_create_user(user_id, guild_id)
        async with self._locks["users"]:
            self._guild_users(guild_id)[str(user_id)][field] = value
            await self._save("users")

    async def increment_user_field(self, user_id: int, guild_id: int,
                                    field: str, delta: int = 1):
        await self.get_or_create_user(user_id, guild_id)
        async with self._locks["users"]:
            u = self._guild_users(guild_id)[str(user_id)]
            u[field] = u.get(field, 0) + delta
            await self._save("users")

    async def add_achievement(self, user_id: int, guild_id: int,
                              achievement_id: str) -> bool:
        await self.get_or_create_user(user_id, guild_id)
        async with self._locks["users"]:
            u = self._guild_users(guild_id)[str(user_id)]
            if achievement_id in u.get("achievements", []):
                return False
            u.setdefault("achievements", []).append(achievement_id)
            await self._save("users")
            return True

    async def add_earn_multiplier(self, user_id: int, guild_id: int, value: float):
        await self.get_or_create_user(user_id, guild_id)
        async with self._locks["users"]:
            u = self._guild_users(guild_id)[str(user_id)]
            u["earn_multiplier"] = u.get("earn_multiplier", 0.0) + value
            await self._save("users")

    # ============================================================
    # PERSONNAGES
    # ============================================================
    async def add_character(self, user_id: int, guild_id: int,
                            character: Dict[str, Any]) -> int:
        await self.get_or_create_user(user_id, guild_id)
        async with self._locks["characters"]:
            char_id = self._next_id("next_character_id")
            entry = {
                "id": char_id,
                "user_id": user_id,
                "guild_id": guild_id,
                "character_id": str(character["id"]),
                "character_name": character["name"],
                "character_source": character.get("source", "Inconnu"),
                "source_type": character["source_type"],
                "image_url": character.get("image_url"),
                "source_image_url": character.get("source_image_url"),
                "rarity": character["rarity"],
                "popularity_score": character.get("popularity_score", 0),
                "value": character.get("value", 0),
                "awakened": False,          # éveil débloqué ?
                "awaken_level": 0,          # 0, 1, 2, 3
                "claimed_at": datetime.utcnow().isoformat(),
                "data_json": character,
            }
            self._guild_chars(guild_id).append(entry)
            await self._save("characters")
        return char_id

    async def is_character_claimed(self, guild_id: int, character_id: str,
                                    source_type: str) -> Optional[Dict]:
        async with self._locks["characters"]:
            cid = str(character_id)
            for c in self._guild_chars(guild_id):
                if c["character_id"] == cid and c["source_type"] == source_type:
                    return dict(c)
            return None

    async def get_user_characters(self, user_id: int, guild_id: int,
                                   limit: int = 10, offset: int = 0,
                                   sort_by: str = "value") -> List[Dict]:
        async with self._locks["characters"]:
            chars = [c for c in self._guild_chars(guild_id)
                     if c["user_id"] == user_id]

        if sort_by == "value":
            chars.sort(key=lambda c: c.get("value", 0), reverse=True)
        elif sort_by == "recent":
            chars.sort(key=lambda c: c.get("claimed_at", ""), reverse=True)
        elif sort_by == "name":
            chars.sort(key=lambda c: (c.get("character_name") or "").lower())
        elif sort_by == "rarity":
            chars.sort(key=lambda c: c.get("popularity_score", 0), reverse=True)
        return [dict(c) for c in chars[offset:offset + limit]]

    async def count_user_characters(self, user_id: int, guild_id: int) -> int:
        async with self._locks["characters"]:
            return sum(1 for c in self._guild_chars(guild_id)
                       if c["user_id"] == user_id)

    async def delete_character(self, character_db_id: int) -> Optional[Dict]:
        async with self._locks["characters"]:
            for guild_chars in self._cache["characters"].values():
                for i, c in enumerate(guild_chars):
                    if c["id"] == character_db_id:
                        deleted = dict(c)
                        guild_chars.pop(i)
                        await self._save("characters")
                        return deleted
            return None

    async def get_character_owner(self, character_db_id: int) -> Optional[int]:
        async with self._locks["characters"]:
            for guild_chars in self._cache["characters"].values():
                for c in guild_chars:
                    if c["id"] == character_db_id:
                        return c["user_id"]
        return None

    async def get_character_by_id(self, character_db_id: int) -> Optional[Dict]:
        async with self._locks["characters"]:
            for guild_chars in self._cache["characters"].values():
                for c in guild_chars:
                    if c["id"] == character_db_id:
                        return dict(c)
        return None

    async def awaken_character(self, character_db_id: int,
                                new_value: int) -> Optional[Dict]:
        async with self._locks["characters"]:
            for guild_chars in self._cache["characters"].values():
                for c in guild_chars:
                    if c["id"] == character_db_id:
                        c["awakened"] = True
                        c["awaken_level"] = c.get("awaken_level", 0) + 1
                        c["value"] = new_value
                        await self._save("characters")
                        return dict(c)
        return None

    async def find_user_character(self, user_id: int, guild_id: int,
                                   search: str) -> Optional[Dict]:
        needle = (search or "").lower().strip()
        if not needle:
            return None
        async with self._locks["characters"]:
            matches = [
                c for c in self._guild_chars(guild_id)
                if c["user_id"] == user_id and needle in c["character_name"].lower()
            ]
        if not matches:
            return None
        matches.sort(key=lambda c: c.get("value", 0), reverse=True)
        return dict(matches[0])

    # ============================================================
    # MATCHING WISHLIST : wanted (qui veut mes persos) / holders (qui a les miens)
    # ============================================================
    async def find_wishlist_matches_for_user_chars(self, user_id: int,
                                                     guild_id: int) -> List[Dict]:
        """
        Pour chaque perso du user, trouve qui l'a en wishlist.
        Retourne [{character, wishers: [user_id,...]}]
        """
        async with self._locks["characters"]:
            my_chars = [dict(c) for c in self._guild_chars(guild_id)
                        if c["user_id"] == user_id]

        async with self._locks["wishlists"]:
            gmap = self._cache["wishlists"].get(str(guild_id), {})
            wish_index: Dict[tuple, List[int]] = {}
            for uid_str, wl in gmap.items():
                try:
                    uid = int(uid_str)
                except ValueError:
                    continue
                if uid == user_id:
                    continue
                for w in wl:
                    key = (w["character_id"], w["source_type"])
                    wish_index.setdefault(key, []).append(uid)

        results = []
        for c in my_chars:
            key = (c["character_id"], c["source_type"])
            if key in wish_index:
                results.append({"character": c, "wishers": wish_index[key]})
        results.sort(key=lambda r: len(r["wishers"]), reverse=True)
        return results

    async def find_holders_for_user_wishlist(self, user_id: int,
                                              guild_id: int) -> List[Dict]:
        """
        Pour chaque perso de ma wishlist, retrouve le owner actuel (si existe).
        Retourne [{wish, owner_id, character}]
        """
        async with self._locks["wishlists"]:
            wl = list(self._user_wishlist(guild_id, user_id))

        async with self._locks["characters"]:
            chars = list(self._guild_chars(guild_id))
            index = {(c["character_id"], c["source_type"]): c for c in chars}

        results = []
        for w in wl:
            key = (w["character_id"], w["source_type"])
            if key in index:
                c = index[key]
                results.append({
                    "wish": dict(w),
                    "owner_id": c["user_id"],
                    "character": dict(c),
                })
        return results

    # ============================================================
    # WISHLIST
    # ============================================================
    async def add_to_wishlist(self, user_id: int, guild_id: int, char_id: str,
                               name: str, source_type: str) -> bool:
        async with self._locks["wishlists"]:
            wl = self._user_wishlist(guild_id, user_id)
            cid = str(char_id)
            if any(w["character_id"] == cid and w["source_type"] == source_type for w in wl):
                return False
            wl.append({
                "character_id": cid,
                "character_name": name,
                "source_type": source_type,
                "added_at": datetime.utcnow().isoformat(),
            })
            await self._save("wishlists")
            return True

    async def remove_from_wishlist(self, user_id: int, guild_id: int,
                                    search: str) -> Optional[str]:
        needle = (search or "").lower().strip()
        if not needle:
            return None
        async with self._locks["wishlists"]:
            wl = self._user_wishlist(guild_id, user_id)
            for i, w in enumerate(wl):
                if needle in w["character_name"].lower():
                    removed = w["character_name"]
                    wl.pop(i)
                    await self._save("wishlists")
                    return removed
            return None

    async def get_wishlist(self, user_id: int, guild_id: int) -> List[Dict]:
        async with self._locks["wishlists"]:
            wl = list(self._user_wishlist(guild_id, user_id))
        wl.sort(key=lambda w: w.get("added_at", ""), reverse=True)
        return [dict(w) for w in wl]

    async def count_wishlist(self, user_id: int, guild_id: int) -> int:
        async with self._locks["wishlists"]:
            return len(self._user_wishlist(guild_id, user_id))

    async def find_users_wishlisting(self, guild_id: int, char_id: str,
                                      source_type: str) -> List[int]:
        result = []
        cid = str(char_id)
        async with self._locks["wishlists"]:
            gmap = self._cache["wishlists"].get(str(guild_id), {})
            for uid_str, wl in gmap.items():
                for w in wl:
                    if w["character_id"] == cid and w["source_type"] == source_type:
                        try:
                            result.append(int(uid_str))
                        except ValueError:
                            pass
                        break
        return result

    # ============================================================
    # AUTO-CLAIM
    # ============================================================
    async def add_auto_claim(self, user_id: int, guild_id: int,
                              char_id: str, char_name: str,
                              source_type: str) -> int:
        async with self._locks["auto_claims"]:
            ac_id = self._next_id("next_autoclaim_id")
            self._cache["auto_claims"].append({
                "id": ac_id,
                "user_id": user_id,
                "guild_id": guild_id,
                "character_id": str(char_id),
                "character_name": char_name,
                "source_type": source_type,
                "active": True,
                "last_triggered": None,
                "created_at": datetime.utcnow().isoformat(),
            })
            await self._save("auto_claims")
            return ac_id

    async def remove_auto_claim(self, auto_claim_id: int) -> bool:
        async with self._locks["auto_claims"]:
            for i, ac in enumerate(self._cache["auto_claims"]):
                if ac["id"] == auto_claim_id:
                    self._cache["auto_claims"].pop(i)
                    await self._save("auto_claims")
                    return True
        return False

    async def get_user_auto_claims(self, user_id: int, guild_id: int) -> List[Dict]:
        async with self._locks["auto_claims"]:
            return [dict(ac) for ac in self._cache["auto_claims"]
                    if ac["user_id"] == user_id and ac["guild_id"] == guild_id
                    and ac.get("active", True)]

    async def count_user_auto_claims(self, user_id: int, guild_id: int) -> int:
        async with self._locks["auto_claims"]:
            return sum(1 for ac in self._cache["auto_claims"]
                       if ac["user_id"] == user_id and ac["guild_id"] == guild_id
                       and ac.get("active", True))

    async def find_matching_auto_claims(self, guild_id: int, char_id: str,
                                         source_type: str) -> List[Dict]:
        """Retourne les auto-claims actifs pour ce perso (trié par date de création)."""
        cid = str(char_id)
        async with self._locks["auto_claims"]:
            matches = [dict(ac) for ac in self._cache["auto_claims"]
                       if ac["guild_id"] == guild_id
                       and ac["character_id"] == cid
                       and ac["source_type"] == source_type
                       and ac.get("active", True)]
        matches.sort(key=lambda ac: ac.get("created_at", ""))
        return matches

    async def mark_auto_claim_triggered(self, auto_claim_id: int):
        async with self._locks["auto_claims"]:
            for ac in self._cache["auto_claims"]:
                if ac["id"] == auto_claim_id:
                    ac["last_triggered"] = datetime.utcnow().isoformat()
                    await self._save("auto_claims")
                    return

    # ============================================================
    # CONFIG SERVEUR
    # ============================================================
    async def get_guild_config(self, guild_id: int) -> Dict:
        async with self._locks["guilds"]:
            gid = str(guild_id)
            if gid not in self._cache["guilds"]:
                self._cache["guilds"][gid] = {
                    "guild_id": guild_id,
                    "roll_channel_id": None,
                    "active_mode": "all",
                    "member_role_id": None,
                    "notif_mode": "dm",  # "dm" | "channel" | "both"
                    "updated_at": datetime.utcnow().isoformat(),
                }
                await self._save("guilds")
            else:
                g = self._cache["guilds"][gid]
                if "notif_mode" not in g:
                    g["notif_mode"] = "dm"
                    await self._save("guilds")
            return dict(self._cache["guilds"][gid])

    async def set_guild_field(self, guild_id: int, field: str, value: Any):
        allowed = {"roll_channel_id", "active_mode", "member_role_id", "notif_mode"}
        if field not in allowed:
            raise ValueError(f"Champ non autorisé: {field}")
        await self.get_guild_config(guild_id)
        async with self._locks["guilds"]:
            self._cache["guilds"][str(guild_id)][field] = value
            self._cache["guilds"][str(guild_id)]["updated_at"] = datetime.utcnow().isoformat()
            await self._save("guilds")

    # ============================================================
    # TRADES
    # ============================================================
    async def create_trade(self, guild_id: int, initiator: int, target: int,
                           init_char: int, target_char: int) -> int:
        async with self._locks["trades"]:
            tid = self._next_id("next_trade_id")
            self._cache["trades"].append({
                "id": tid,
                "guild_id": guild_id,
                "initiator_id": initiator,
                "target_id": target,
                "initiator_char_id": init_char,
                "target_char_id": target_char,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            })
            await self._save("trades")
            return tid

    async def complete_trade(self, trade_id: int) -> bool:
        async with self._locks["trades"]:
            trade = next((t for t in self._cache["trades"] if t["id"] == trade_id), None)
            if not trade:
                return False

        async with self._locks["characters"]:
            for gchars in self._cache["characters"].values():
                for c in gchars:
                    if c["id"] == trade["initiator_char_id"]:
                        c["user_id"] = trade["target_id"]
                    elif c["id"] == trade["target_char_id"]:
                        c["user_id"] = trade["initiator_id"]
            await self._save("characters")

        async with self._locks["trades"]:
            trade["status"] = "completed"
            await self._save("trades")
        return True

    # ============================================================
    # EVENTS SERVEUR
    # ============================================================
    async def create_event(self, guild_id: int, event_type: str,
                           ends_at_iso: str, data: Dict = None) -> int:
        """
        event_type : 'double_tokens' | 'limited_character'
        data : dict avec infos spécifiques (ex: character pour limited_character)
        """
        async with self._locks["events"]:
            eid = self._next_id("next_event_id")
            self._cache["events"].append({
                "id": eid,
                "guild_id": guild_id,
                "type": event_type,
                "data": data or {},
                "started_at": datetime.utcnow().isoformat(),
                "ends_at": ends_at_iso,
                "active": True,
            })
            await self._save("events")
            return eid

    async def get_active_events(self, guild_id: int) -> List[Dict]:
        """Retourne les events actifs non expirés. Désactive auto ceux qui sont expirés."""
        now = datetime.utcnow()
        active = []
        async with self._locks["events"]:
            changed = False
            for ev in self._cache["events"]:
                if ev["guild_id"] != guild_id:
                    continue
                if not ev.get("active", True):
                    continue
                try:
                    ends = datetime.fromisoformat(ev["ends_at"])
                    if now >= ends:
                        ev["active"] = False
                        changed = True
                        continue
                except ValueError:
                    pass
                active.append(dict(ev))
            if changed:
                await self._save("events")
        return active

    async def get_active_event_by_type(self, guild_id: int,
                                        event_type: str) -> Optional[Dict]:
        events = await self.get_active_events(guild_id)
        for ev in events:
            if ev["type"] == event_type:
                return ev
        return None

    async def stop_event(self, event_id: int) -> bool:
        async with self._locks["events"]:
            for ev in self._cache["events"]:
                if ev["id"] == event_id:
                    ev["active"] = False
                    await self._save("events")
                    return True
        return False

    # ============================================================
    # RARITY PROTECTION (active sur le prochain roll)
    # ============================================================
    async def set_rarity_protection(self, user_id: int, guild_id: int,
                                     min_rarity: str):
        """Définit une protection qui sera consommée au prochain roll."""
        await self.get_or_create_user(user_id, guild_id)
        async with self._locks["users"]:
            u = self._guild_users(guild_id)[str(user_id)]
            u["rarity_protection"] = min_rarity
            await self._save("users")

    async def consume_rarity_protection(self, user_id: int,
                                         guild_id: int) -> Optional[str]:
        """Récupère et consomme la protection si elle existe."""
        await self.get_or_create_user(user_id, guild_id)
        async with self._locks["users"]:
            u = self._guild_users(guild_id)[str(user_id)]
            protection = u.get("rarity_protection")
            if protection:
                u["rarity_protection"] = None
                await self._save("users")
            return protection

    # ============================================================
    # GLOBAL PROFILE (opt-in, vitrine cross-serveur)
    # ============================================================
    async def set_global_profile_optin(self, user_id: int, enabled: bool,
                                        favorite_guild_id: Optional[int] = None):
        """
        Active/désactive le partage global du profil.
        favorite_guild_id : serveur dont la collection sera affichée en priorité.
        """
        async with self._locks["global_profiles"]:
            uid = str(user_id)
            if enabled:
                self._cache["global_profiles"][uid] = {
                    "user_id": user_id,
                    "enabled": True,
                    "favorite_guild_id": favorite_guild_id,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            else:
                self._cache["global_profiles"].pop(uid, None)
            await self._save("global_profiles")

    async def get_global_profile(self, user_id: int) -> Optional[Dict]:
        async with self._locks["global_profiles"]:
            return dict(self._cache["global_profiles"].get(str(user_id), {})) or None

    async def get_all_user_characters_cross_guilds(self, user_id: int,
                                                     limit: int = 9) -> List[Dict]:
        """Récupère les persos les plus précieux de l'user sur TOUS les serveurs."""
        all_chars = []
        async with self._locks["characters"]:
            for gid, gchars in self._cache["characters"].items():
                for c in gchars:
                    if c["user_id"] == user_id:
                        all_chars.append(dict(c))
        all_chars.sort(key=lambda c: c.get("value", 0), reverse=True)
        return all_chars[:limit]

    # ============================================================
    # LEADERBOARD
    # ============================================================
    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> List[Dict]:
        async with self._locks["characters"]:
            chars = list(self._guild_chars(guild_id))

        stats: Dict[int, Dict] = {}
        for c in chars:
            uid = c["user_id"]
            if uid not in stats:
                stats[uid] = {"user_id": uid, "total": 0, "total_value": 0}
            stats[uid]["total"] += 1
            stats[uid]["total_value"] += c.get("value", 0)

        ranked = sorted(stats.values(), key=lambda s: s["total_value"], reverse=True)
        return ranked[:limit]
