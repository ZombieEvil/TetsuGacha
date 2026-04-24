"""
Dashboard temps réel pour le terminal.
Affiche panels, stats et flux d'événements en direct.
"""
from collections import deque
from datetime import datetime
import time

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich import box

import config


ASCII_BANNER = r"""
 ████████╗███████╗████████╗███████╗██╗   ██╗ ██████╗  █████╗  ██████╗██╗  ██╗ █████╗
 ╚══██╔══╝██╔════╝╚══██╔══╝██╔════╝██║   ██║██╔════╝ ██╔══██╗██╔════╝██║  ██║██╔══██╗
    ██║   █████╗     ██║   ███████╗██║   ██║██║  ███╗███████║██║     ███████║███████║
    ██║   ██╔══╝     ██║   ╚════██║██║   ██║██║   ██║██╔══██║██║     ██╔══██║██╔══██║
    ██║   ███████╗   ██║   ███████║╚██████╔╝╚██████╔╝██║  ██║╚██████╗██║  ██║██║  ██║
    ╚═╝   ╚══════╝   ╚═╝   ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝
"""


class BotDashboard:
    def __init__(self, max_events: int = 15, max_claims: int = 8):
        self.console = Console()
        self.start_time = time.time()

        self.bot_name = "Connexion…"
        self.bot_latency_ms = 0
        self.guild_count = 0
        self.user_count = 0
        self.mode_statuses = {}

        self.total_rolls = 0
        self.total_claims = 0
        self.total_trades = 0
        self.total_divorces = 0
        self.total_wishlist_hits = 0
        self.api_calls = 0
        self.api_errors = 0

        self.events = deque(maxlen=max_events)
        self.recent_claims = deque(maxlen=max_claims)

        self._live = None

    # API publique
    def log_event(self, event_type: str, message: str, color: str = "cyan"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.events.appendleft({"time": ts, "type": event_type, "msg": message, "color": color})

    def log_roll(self, user: str, character: str, source: str, rarity: str):
        self.total_rolls += 1
        self.log_event("ROLL",
            f"[bold]{user}[/bold] → [italic]{character}[/italic] ({source}) • {rarity}", "cyan")

    def log_claim(self, user: str, character: str, source: str, rarity: str):
        self.total_claims += 1
        self.recent_claims.appendleft({
            "time": datetime.now().strftime("%H:%M:%S"),
            "user": user, "character": character, "source": source, "rarity": rarity,
        })
        self.log_event("CLAIM",
            f"[bold magenta]{user}[/] ♥ [bold]{character}[/] ({source})", "magenta")

    def log_trade(self, user_a: str, user_b: str, char_a: str, char_b: str):
        self.total_trades += 1
        self.log_event("TRADE",
            f"[yellow]{user_a}[/] ⇄ [yellow]{user_b}[/] : {char_a} / {char_b}", "yellow")

    def log_divorce(self, user: str, character: str):
        self.total_divorces += 1
        self.log_event("DIVORCE", f"[red]{user}[/] 💔 {character}", "red")

    def log_wishlist_hit(self, user: str, character: str):
        self.total_wishlist_hits += 1
        self.log_event("WL-HIT",
            f"[bright_magenta]{user}[/] a revendiqué un perso wishlisté : {character}",
            "bright_magenta")

    def log_api(self, source: str, success: bool = True):
        self.api_calls += 1
        if not success:
            self.api_errors += 1
            self.log_event("API-ERR", f"[red]échec API {source}[/]", "red")

    def log_info(self, message: str):
        self.log_event("INFO", message, "green")

    def log_warn(self, message: str):
        self.log_event("WARN", message, "yellow")

    def log_error(self, message: str):
        self.log_event("ERROR", f"[red]{message}[/]", "red")

    def update_bot_info(self, name: str, latency_ms: int, guilds: int, users: int):
        self.bot_name = name
        self.bot_latency_ms = latency_ms
        self.guild_count = guilds
        self.user_count = users

    def update_mode(self, guild_id: int, guild_name: str, mode: str):
        self.mode_statuses[guild_id] = {"name": guild_name, "mode": mode}

    # Rendu
    def _uptime_str(self) -> str:
        seconds = int(time.time() - self.start_time)
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}h {m:02d}m {s:02d}s"
        if m:
            return f"{m}m {s:02d}s"
        return f"{s}s"

    def _render_header(self) -> Panel:
        text = Text(ASCII_BANNER, style="bold bright_magenta")
        subtitle = Text(
            f"  {config.BOT_TAGLINE} • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • Ctrl+C pour arrêter",
            style="dim cyan",
        )
        return Panel(
            Align.center(Text.assemble(text, "\n", subtitle)),
            border_style="bright_magenta",
            box=box.DOUBLE,
        )

    def _render_status(self) -> Panel:
        table = Table.grid(padding=(0, 1), expand=True)
        table.add_column(style="bold cyan", justify="right", ratio=1)
        table.add_column(style="white", ratio=2)

        latency_color = "green" if self.bot_latency_ms < 200 else "yellow" if self.bot_latency_ms < 500 else "red"

        table.add_row("BOT", f"[bold bright_green]{self.bot_name}[/]")
        table.add_row("STATUT", "[bold green]● EN LIGNE[/]")
        table.add_row("UPTIME", f"[bright_white]{self._uptime_str()}[/]")
        table.add_row("LATENCE", f"[{latency_color}]{self.bot_latency_ms} ms[/]")
        table.add_row("SERVEURS", f"[bright_white]{self.guild_count}[/]")
        table.add_row("UTILISATEURS", f"[bright_white]{self.user_count:,}[/]")

        return Panel(table, title="[bold cyan]◆ SYSTÈME ◆[/]",
                     border_style="cyan", box=box.ROUNDED)

    def _render_stats(self) -> Panel:
        table = Table.grid(padding=(0, 1), expand=True)
        table.add_column(style="bold yellow", justify="right", ratio=1)
        table.add_column(style="white", ratio=1)

        err_rate = 0 if self.api_calls == 0 else (self.api_errors / self.api_calls * 100)
        err_color = "green" if err_rate < 5 else "yellow" if err_rate < 20 else "red"

        table.add_row("🎲 ROLLS", f"[bright_white]{self.total_rolls:,}[/]")
        table.add_row("💖 CLAIMS", f"[magenta]{self.total_claims:,}[/]")
        table.add_row("🤝 TRADES", f"[yellow]{self.total_trades:,}[/]")
        table.add_row("💔 DIVORCES", f"[red]{self.total_divorces:,}[/]")
        table.add_row("🎯 WL HITS", f"[bright_magenta]{self.total_wishlist_hits:,}[/]")
        table.add_row("📡 API", f"[cyan]{self.api_calls:,}[/]")
        table.add_row("⚠️  ERR", f"[{err_color}]{err_rate:.1f}%[/]")

        return Panel(table, title="[bold yellow]◆ STATS LIVE ◆[/]",
                     border_style="yellow", box=box.ROUNDED)

    def _render_modes(self) -> Panel:
        if not self.mode_statuses:
            content = Text("Aucun serveur actif", style="dim italic")
        else:
            table = Table.grid(padding=(0, 1), expand=True)
            table.add_column(style="cyan", ratio=2)
            table.add_column(style="white", ratio=1)
            for info in list(self.mode_statuses.values())[:6]:
                mode_style = {
                    "all": "[bright_cyan]🌐 TOUT[/]",
                    "anime": "[blue]📖 ANIME[/]",
                    "movie": "[bright_yellow]🎬 FILM[/]",
                    "game": "[green]🎮 JEU[/]",
                    "comic": "[red]💥 COMIC[/]",
                }.get(info["mode"], info["mode"].upper())
                name = info["name"]
                if len(name) > 22:
                    name = name[:19] + "…"
                table.add_row(name, mode_style)
            content = table
        return Panel(content, title="[bold bright_magenta]◆ SERVEURS ◆[/]",
                     border_style="bright_magenta", box=box.ROUNDED)

    def _render_events(self) -> Panel:
        if not self.events:
            content = Text(
                "En attente d'activité…\n\n  > Tape /roll sur Discord pour lancer le bal !",
                style="dim italic",
            )
        else:
            type_colors = {
                "ROLL": "cyan", "CLAIM": "magenta", "TRADE": "yellow",
                "DIVORCE": "red", "WL-HIT": "bright_magenta",
                "API-ERR": "red", "ERROR": "red", "WARN": "yellow",
                "INFO": "green",
            }
            lines = []
            for ev in list(self.events):
                c = type_colors.get(ev["type"], "white")
                lines.append(f"[dim]{ev['time']}[/] [bold {c}][{ev['type']:8}][/] {ev['msg']}")
            content = Text.from_markup("\n".join(lines))
        return Panel(content, title="[bold green]◆ FLUX D'ÉVÉNEMENTS ◆[/]",
                     border_style="green", box=box.ROUNDED)

    def _render_recent_claims(self) -> Panel:
        if not self.recent_claims:
            content = Text("Aucun claim encore…", style="dim italic")
        else:
            table = Table(show_header=True, header_style="bold magenta",
                          box=box.SIMPLE, expand=True, padding=(0, 1))
            table.add_column("Heure", style="dim", width=8)
            table.add_column("Joueur", style="bright_white")
            table.add_column("Personnage", style="magenta")
            table.add_column("Licence", style="cyan")
            table.add_column("Rareté", justify="center")

            rarity_colors = {
                "LEGENDARY": "bold yellow", "EPIC": "bold magenta",
                "RARE": "bold blue", "UNCOMMON": "bold green", "COMMON": "white",
            }
            for c in list(self.recent_claims):
                r_style = rarity_colors.get(c["rarity"], "white")
                table.add_row(
                    c["time"], c["user"][:15], c["character"][:25], c["source"][:20],
                    Text(c["rarity"], style=r_style),
                )
            content = table
        return Panel(content, title="[bold magenta]◆ DERNIERS CLAIMS ◆[/]",
                     border_style="magenta", box=box.ROUNDED)

    def _build_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(Layout(name="header", size=10), Layout(name="body"))
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="center", ratio=2),
            Layout(name="right", ratio=1),
        )
        layout["left"].split_column(Layout(name="status"), Layout(name="stats"))
        layout["center"].split_column(Layout(name="events", ratio=2), Layout(name="claims", ratio=1))
        layout["right"].update(self._render_modes())

        layout["header"].update(self._render_header())
        layout["status"].update(self._render_status())
        layout["stats"].update(self._render_stats())
        layout["events"].update(self._render_events())
        layout["claims"].update(self._render_recent_claims())
        return layout

    def render(self) -> Layout:
        return self._build_layout()

    def start(self):
        self._live = Live(self.render(), console=self.console,
                          refresh_per_second=2, screen=True)
        self._live.start()

    def refresh(self):
        if self._live:
            self._live.update(self.render())

    def stop(self):
        if self._live:
            self._live.stop()

    def print_farewell(self):
        self.console.print(
            Panel(
                Align.center(Text(f"🔌  {config.BOT_NAME} se déconnecte…\nÀ bientôt !",
                                  style="bold bright_red")),
                border_style="red", box=box.DOUBLE,
            )
        )


dashboard = BotDashboard()
