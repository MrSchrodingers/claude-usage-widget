"""Color palette and level helpers — mirror of tauri-app/src/lib/theme.js."""

COLORS = {
    "bg":         "#1a1a2e",
    "bg_card":    "rgba(255,255,255,0.05)",
    "border":     "rgba(255,255,255,0.08)",
    "text":       "#e0e0e0",
    "text_dim":   "rgba(255,255,255,0.4)",
    "text_muted": "rgba(255,255,255,0.6)",
    "amber":       "#D97706",
    "amber_light": "#F59E0B",
    "amber_dim":   "#92400E",
    "blue":        "#3B82F6",
    "green":       "#10B981",
    "red":         "#EF4444",
    "orange":      "#F97316",
    "purple":      "#6366F1",
    "gold":        "#FFD700",
}


def limit_color(pct: float) -> str:
    if pct > 80:
        return COLORS["red"]
    if pct > 50:
        return COLORS["amber_light"]
    return COLORS["text"]


def bar_fill(pct: float, base: str) -> str:
    if pct > 80:
        return COLORS["red"]
    if pct > 50:
        return COLORS["amber_light"]
    return base


def status_color(indicator: str) -> str:
    return {
        "none":     COLORS["green"],
        "minor":    COLORS["amber_light"],
        "major":    COLORS["orange"],
        "critical": COLORS["red"],
    }.get(indicator, COLORS["text_dim"])


def status_color_rgb(indicator: str):
    return {
        "none":     (16, 185, 129),
        "minor":    (245, 158, 11),
        "major":    (249, 115, 22),
        "critical": (239, 68, 68),
    }.get(indicator, (128, 128, 128))


def component_status_color(status: str) -> str:
    return {
        "operational":          COLORS["green"],
        "degraded_performance": COLORS["amber_light"],
        "partial_outage":       COLORS["orange"],
        "major_outage":         COLORS["red"],
    }.get(status, COLORS["text_dim"])


def dumb_level_color(level: str) -> str:
    return {
        "genius":    COLORS["gold"],
        "smart":     COLORS["green"],
        "slow":      COLORS["amber_light"],
        "dumb":      COLORS["orange"],
        "braindead": COLORS["red"],
    }.get(level, COLORS["text"])


def dumb_level_label(level: str) -> str:
    return {
        "genius":    "Genius",
        "smart":     "Smart",
        "slow":      "Slow",
        "dumb":      "Dumb",
        "braindead": "Braindead",
    }.get(level, level)


def dumb_level_emoji(level: str) -> str:
    return {
        "genius":    "\u2728 Genius",
        "smart":     "\U0001F914 Hmm",
        "slow":      "\U0001F327 Slow",
        "dumb":      "\U0001F525 This is Fine",
        "braindead": "\U0001F480 Braindead",
    }.get(level, level)


def format_tokens(n) -> str:
    if not n:
        return "0"
    n = float(n)
    if n >= 1e9:
        return f"{n/1e9:.1f}B"
    if n >= 1e6:
        return f"{n/1e6:.1f}M"
    if n >= 1e3:
        return f"{n/1e3:.0f}K"
    return str(int(n))


SPRITE_MAP = {
    "genius":    {"prefix": "halo",  "frames": 6, "interval": 250},
    "smart":     {"prefix": "smart", "frames": 6, "interval": 300},
    "slow":      {"prefix": "rain",  "frames": 6, "interval": 100},
    "dumb":      {"prefix": "fire",  "frames": 6, "interval": 120},
    "braindead": {"prefix": "skull", "frames": 6, "interval": 200},
}
