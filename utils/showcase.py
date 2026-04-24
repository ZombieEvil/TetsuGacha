"""
Génération d'images de showcase avec Pillow.

Produit une grille carrée (3x3 par défaut) des meilleurs persos d'un user,
avec bordures colorées selon la rareté, nom et valeur.
"""
import asyncio
import io
from typing import List, Dict, Optional

import aiohttp

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

import config


# Couleurs de bordure selon la rareté (hex -> RGB)
def _hex_to_rgb(hex_color: int) -> tuple:
    return ((hex_color >> 16) & 0xFF, (hex_color >> 8) & 0xFF, hex_color & 0xFF)


def _rarity_border_color(rarity: str) -> tuple:
    info = config.RARITY_TIERS.get(rarity, config.RARITY_TIERS["COMMON"])
    return _hex_to_rgb(info["color"])


async def _fetch_image(session: aiohttp.ClientSession, url: str) -> Optional[bytes]:
    if not url:
        return None
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            return await resp.read()
    except Exception:
        return None


def _get_font(size: int):
    """Essaie de charger une font système, fallback sur la default PIL."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _draw_placeholder(size: int, rarity: str, name: str) -> "Image.Image":
    """Crée une image placeholder si le fetch a échoué."""
    color = _rarity_border_color(rarity)
    img = Image.new("RGB", (size, size), color)
    draw = ImageDraw.Draw(img)
    font = _get_font(size // 10)
    if font:
        text = name[:12] if name else "?"
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            tw, th = draw.textsize(text, font=font)
        draw.text(((size - tw) / 2, (size - th) / 2), text,
                  fill=(255, 255, 255), font=font)
    return img


async def _render_one_cell(session: aiohttp.ClientSession, character: Dict,
                            cell_size: int) -> "Image.Image":
    """Rend une cellule de la grille : image + bordure + nom + valeur."""
    border = 8
    inner_size = cell_size - border * 2
    rarity = character.get("rarity", "COMMON")
    border_color = _rarity_border_color(rarity)

    # Télécharger l'image
    img_data = await _fetch_image(session, character.get("image_url", ""))
    inner_img = None
    if img_data:
        try:
            inner_img = Image.open(io.BytesIO(img_data)).convert("RGB")
        except Exception:
            inner_img = None

    if inner_img is None:
        inner_img = _draw_placeholder(inner_size, rarity,
                                       character.get("character_name", ""))
    else:
        # Resize en conservant les proportions puis crop centré
        inner_img.thumbnail((inner_size * 2, inner_size * 2), Image.LANCZOS)
        w, h = inner_img.size
        # Crop carré centré
        short = min(w, h)
        left = (w - short) // 2
        top = (h - short) // 2
        inner_img = inner_img.crop((left, top, left + short, top + short))
        inner_img = inner_img.resize((inner_size, inner_size), Image.LANCZOS)

    # Fond de la cellule (couleur de rareté)
    cell = Image.new("RGB", (cell_size, cell_size), border_color)
    cell.paste(inner_img, (border, border))

    # Overlay gradient en bas pour le texte lisible
    overlay = Image.new("RGBA", (cell_size, cell_size), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    gradient_h = cell_size // 4
    for i in range(gradient_h):
        alpha = int(200 * (i / gradient_h))
        overlay_draw.rectangle(
            [0, cell_size - gradient_h + i, cell_size, cell_size - gradient_h + i + 1],
            fill=(0, 0, 0, alpha),
        )
    cell = Image.alpha_composite(cell.convert("RGBA"), overlay).convert("RGB")

    # Texte : nom + valeur
    draw = ImageDraw.Draw(cell)
    name_font = _get_font(cell_size // 14)
    value_font = _get_font(cell_size // 18)

    name = character.get("character_name", "?")
    if len(name) > 18:
        name = name[:17] + "…"
    value_text = f"{character.get('value', 0)} · {rarity}"

    if name_font:
        draw.text((border + 4, cell_size - cell_size // 4),
                  name, fill=(255, 255, 255), font=name_font)
    if value_font:
        draw.text((border + 4, cell_size - cell_size // 8),
                  value_text, fill=(255, 220, 140), font=value_font)

    # Marqueur éveil
    if character.get("awakened"):
        awk_font = _get_font(cell_size // 10)
        if awk_font:
            draw.text((cell_size - border - cell_size // 8, border + 4),
                      "✨", fill=(255, 215, 0), font=awk_font)

    return cell


async def generate_showcase_image(characters: List[Dict],
                                   display_name: str,
                                   total_value: int,
                                   total_count: int,
                                   session: aiohttp.ClientSession) -> Optional[bytes]:
    """
    Retourne les bytes PNG de l'image showcase, ou None si Pillow indispo.
    """
    if not PIL_AVAILABLE:
        return None

    grid_size = config.SHOWCASE_GRID_SIZE
    img_size = config.SHOWCASE_IMAGE_SIZE

    # Layout : header (120px) + grille
    header_height = 120
    padding = 20
    cell_size = (img_size - padding * (grid_size + 1)) // grid_size
    total_height = header_height + padding * (grid_size + 1) + cell_size * grid_size

    # Fond
    bg_color = (26, 26, 40)
    canvas = Image.new("RGB", (img_size, total_height), bg_color)
    draw = ImageDraw.Draw(canvas)

    # Header : nom + stats
    title_font = _get_font(38)
    subtitle_font = _get_font(22)
    if title_font:
        draw.text((padding, padding), f"{display_name}",
                  fill=(255, 255, 255), font=title_font)
    if subtitle_font:
        draw.text((padding, padding + 50),
                  f"Collection · {total_count} persos · {total_value} {config.CURRENCY_NAME_LONG}",
                  fill=(200, 180, 220), font=subtitle_font)
    draw.text((img_size - 180, padding + 55),
              config.BOT_NAME,
              fill=(233, 30, 99), font=subtitle_font or title_font)

    # Générer les cellules en parallèle (rapide)
    slots = grid_size * grid_size
    chars_to_render = characters[:slots]
    tasks = [_render_one_cell(session, c, cell_size) for c in chars_to_render]
    cells = await asyncio.gather(*tasks, return_exceptions=True)

    # Placer les cellules dans la grille
    for idx, cell in enumerate(cells):
        if isinstance(cell, Exception):
            cell = _draw_placeholder(cell_size, "COMMON", "?")
        row = idx // grid_size
        col = idx % grid_size
        x = padding + col * (cell_size + padding)
        y = header_height + padding + row * (cell_size + padding)
        canvas.paste(cell, (x, y))

    # Si moins de persos que de slots → cellules vides
    for idx in range(len(chars_to_render), slots):
        row = idx // grid_size
        col = idx % grid_size
        x = padding + col * (cell_size + padding)
        y = header_height + padding + row * (cell_size + padding)
        empty = Image.new("RGB", (cell_size, cell_size), (40, 40, 55))
        edraw = ImageDraw.Draw(empty)
        slot_font = _get_font(cell_size // 6)
        if slot_font:
            text = "—"
            try:
                bbox = edraw.textbbox((0, 0), text, font=slot_font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except AttributeError:
                tw, th = edraw.textsize(text, font=slot_font)
            edraw.text(((cell_size - tw) / 2, (cell_size - th) / 2),
                       text, fill=(80, 80, 100), font=slot_font)
        canvas.paste(empty, (x, y))

    # Sauvegarder en bytes
    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
