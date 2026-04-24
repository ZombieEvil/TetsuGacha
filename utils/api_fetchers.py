"""
Fetchers pour récupérer personnages + image de la licence depuis plusieurs APIs.

Chaque fetcher retourne :
{
    "id": str,
    "name": str,
    "source": str,            # "Naruto", "The Witcher 3"...
    "source_type": str,       # "anime", "manga", "movie", "tv", "game", "comic"
    "image_url": str,         # portrait du perso
    "source_image_url": str,  # poster/jaquette/cover de la licence
    "popularity_score": int (0-100),
    "description": str,
}
"""
import aiohttp
import asyncio
import random
import time
from typing import Optional, Dict


# ============================================================
# ANILIST - Anime/Manga (avec image de la licence)
# ============================================================
ANILIST_URL = "https://graphql.anilist.co"

ANILIST_QUERY = """
query ($page: Int, $perPage: Int, $sort: [CharacterSort]) {
  Page(page: $page, perPage: $perPage) {
    characters(sort: $sort) {
      id
      name { full native }
      image { large medium }
      description(asHtml: false)
      favourites
      gender
      media(perPage: 1, sort: POPULARITY_DESC) {
        nodes {
          title { romaji english }
          type
          popularity
          coverImage { large extraLarge }
          bannerImage
        }
      }
    }
  }
}
"""


async def fetch_anilist_random_character(session: aiohttp.ClientSession) -> Optional[Dict]:
    page = random.randint(1, 500)
    variables = {"page": page, "perPage": 25, "sort": "FAVOURITES_DESC"}
    try:
        async with session.post(ANILIST_URL,
                                json={"query": ANILIST_QUERY, "variables": variables},
                                timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return None

    chars = data.get("data", {}).get("Page", {}).get("characters", [])
    if not chars:
        return None

    char = random.choice(chars)
    media = char["media"]["nodes"][0] if char["media"]["nodes"] else {}
    source_title = (media.get("title", {}).get("english")
                    or media.get("title", {}).get("romaji") or "Inconnu")

    cover = media.get("coverImage", {}) or {}
    source_image = cover.get("extraLarge") or cover.get("large") or media.get("bannerImage")

    favourites = char.get("favourites", 0) or 0
    score = min(100, int((favourites / 50000) * 100))
    source_type = "manga" if media.get("type") == "MANGA" else "anime"

    return {
        "id": f"al_{char['id']}",
        "name": char["name"]["full"] or char["name"]["native"],
        "source": source_title,
        "source_type": source_type,
        "image_url": char["image"]["large"] or char["image"]["medium"],
        "source_image_url": source_image,
        "popularity_score": score,
        "description": (char.get("description") or "")[:400],
    }


# ============================================================
# TMDB - Films / Séries / Acteurs
# ============================================================
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_IMG_BIG = "https://image.tmdb.org/t/p/original"


async def fetch_tmdb_random_character(session: aiohttp.ClientSession, api_key: str) -> Optional[Dict]:
    if not api_key:
        return None
    page = random.randint(1, 100)
    url = f"{TMDB_BASE}/person/popular"
    params = {"api_key": api_key, "page": page, "language": "en-US"}
    try:
        async with session.get(url, params=params,
                               timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return None

    people = [p for p in data.get("results", []) if p.get("profile_path")]
    if not people:
        return None

    person = random.choice(people)
    known_for = person.get("known_for", [])
    source_title = "Cinéma"
    source_type = "movie"
    source_image = None
    if known_for:
        first = known_for[0]
        source_title = first.get("title") or first.get("name") or "Cinéma"
        source_type = "tv" if first.get("media_type") == "tv" else "movie"
        if first.get("poster_path"):
            source_image = TMDB_IMG_BIG + first["poster_path"]
        elif first.get("backdrop_path"):
            source_image = TMDB_IMG_BIG + first["backdrop_path"]

    popularity = person.get("popularity", 0) or 0
    score = min(100, int(popularity))

    return {
        "id": f"tmdb_{person['id']}",
        "name": person["name"],
        "source": source_title,
        "source_type": source_type,
        "image_url": TMDB_IMG_BASE + person["profile_path"],
        "source_image_url": source_image,
        "popularity_score": score,
        "description": f"Connu pour : {source_title}",
    }


# ============================================================
# IGDB - Jeux vidéo
# ============================================================
class IGDBAuth:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._expires_at = 0

    async def get_token(self, session: aiohttp.ClientSession) -> Optional[str]:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        if not self.client_id or not self.client_secret:
            return None
        url = "https://id.twitch.tv/oauth2/token"
        params = {"client_id": self.client_id, "client_secret": self.client_secret,
                  "grant_type": "client_credentials"}
        try:
            async with session.post(url, params=params,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                self._token = data["access_token"]
                self._expires_at = time.time() + data.get("expires_in", 3600)
                return self._token
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None


async def fetch_igdb_random_character(session: aiohttp.ClientSession,
                                      auth: IGDBAuth) -> Optional[Dict]:
    token = await auth.get_token(session)
    if not token:
        return None
    offset = random.randint(0, 5000)
    headers = {"Client-ID": auth.client_id, "Authorization": f"Bearer {token}"}
    body = (
        "fields name, mug_shot.image_id, games.name, games.rating, games.cover.image_id; "
        "where mug_shot != null; "
        f"limit 10; offset {offset};"
    )
    try:
        async with session.post("https://api.igdb.com/v4/characters",
                                headers=headers, data=body,
                                timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            chars = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return None
    if not chars:
        return None

    char = random.choice(chars)
    if not char.get("mug_shot"):
        return None
    games = char.get("games", [])
    game_name = games[0]["name"] if games else "Jeu vidéo"
    rating = games[0].get("rating", 50) if games else 50
    score = min(100, int(rating))

    image_id = char["mug_shot"]["image_id"]
    image_url = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"

    source_image = None
    if games and games[0].get("cover", {}).get("image_id"):
        cov_id = games[0]["cover"]["image_id"]
        source_image = f"https://images.igdb.com/igdb/image/upload/t_1080p/{cov_id}.jpg"

    return {
        "id": f"igdb_{char['id']}",
        "name": char["name"],
        "source": game_name,
        "source_type": "game",
        "image_url": image_url,
        "source_image_url": source_image,
        "popularity_score": score,
        "description": f"Personnage du jeu : {game_name}",
    }


# ============================================================
# COMIC VINE - Marvel / DC
# ============================================================
COMICVINE_BASE = "https://comicvine.gamespot.com/api"


async def fetch_comicvine_random_character(session: aiohttp.ClientSession,
                                           api_key: str) -> Optional[Dict]:
    if not api_key:
        return None
    offset = random.randint(0, 30000)
    url = f"{COMICVINE_BASE}/characters/"
    params = {
        "api_key": api_key, "format": "json", "limit": 20, "offset": offset,
        "field_list": "id,name,image,publisher,count_of_issue_appearances,deck",
    }
    headers = {"User-Agent": "TetsuGachaBot/1.0"}
    try:
        async with session.get(url, params=params, headers=headers,
                               timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return None

    results = [r for r in data.get("results", []) if r.get("image", {}).get("medium_url")]
    if not results:
        return None

    char = random.choice(results)
    appearances = char.get("count_of_issue_appearances", 0) or 0
    score = min(100, int((appearances / 2000) * 100))
    publisher = char.get("publisher", {}) or {}
    publisher_name = publisher.get("name", "Comics") if isinstance(publisher, dict) else "Comics"

    return {
        "id": f"cv_{char['id']}",
        "name": char["name"],
        "source": publisher_name,
        "source_type": "comic",
        "image_url": char["image"]["medium_url"],
        "source_image_url": char["image"].get("original_url") or char["image"].get("super_url"),
        "popularity_score": score,
        "description": (char.get("deck") or "")[:400],
    }


# ============================================================
# FETCHER UNIFIÉ
# ============================================================
class CharacterFetcher:
    def __init__(self, tmdb_key: str = "", igdb_id: str = "", igdb_secret: str = "",
                 comicvine_key: str = ""):
        self.tmdb_key = tmdb_key
        self.igdb_auth = IGDBAuth(igdb_id, igdb_secret)
        self.comicvine_key = comicvine_key
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_random_character(self, mode: str = "all") -> Optional[Dict]:
        """
        mode :
          - "all"   : toutes sources pondérées
          - "anime" : anime/manga uniquement
          - "movie" : films/séries
          - "game"  : jeux vidéo
          - "comic" : comics
        """
        await self.start()

        if mode == "anime":
            sources = [("anilist", 1.0)]
        elif mode == "movie":
            sources = [("tmdb", 1.0)]
        elif mode == "game":
            sources = [("igdb", 1.0)]
        elif mode == "comic":
            sources = [("comicvine", 1.0)]
        else:
            sources = [
                ("anilist", 0.50),
                ("tmdb", 0.20) if self.tmdb_key else ("anilist", 0.20),
                ("comicvine", 0.15) if self.comicvine_key else ("anilist", 0.15),
                ("igdb", 0.15) if (self.igdb_auth.client_id and self.igdb_auth.client_secret)
                               else ("anilist", 0.15),
            ]

        for _ in range(3):
            names, weights = zip(*sources)
            source = random.choices(names, weights=weights, k=1)[0]
            char = None
            if source == "anilist":
                char = await fetch_anilist_random_character(self.session)
            elif source == "tmdb":
                char = await fetch_tmdb_random_character(self.session, self.tmdb_key)
            elif source == "igdb":
                char = await fetch_igdb_random_character(self.session, self.igdb_auth)
            elif source == "comicvine":
                char = await fetch_comicvine_random_character(self.session, self.comicvine_key)
            if char:
                return char

        return await fetch_anilist_random_character(self.session)
