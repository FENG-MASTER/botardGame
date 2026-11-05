"""Ketchup 2019 module configuration and compatibility (rulebook pp. 6–17)."""
from boardgame.core import require

MODULES = {
    "new_districts": ("新城区", 6),
    "lobbyists": ("说客", 7),
    "new_milestones": ("新里程碑", 8),
    "coffee": ("咖啡", 10),
    "kimchi": ("泡菜", 11),
    "sushi": ("寿司", 12),
    "noodles": ("面条", 12),
    "ketchup": ("番茄酱机制", 13),
    "fry_chefs": ("薯条大厨", 13),
    "night_shift": ("夜班经理", 14),
    "mass_marketeers": ("大众营销员", 14),
    "rural_marketeers": ("乡村营销员", 15),
    "gourmet_critics": ("美食评论家", 15),
    "movie_stars": ("电影明星", 16),
    "reserve_prices": ("储备价格", 16),
    "hard_choices": ("艰难抉择", 17),
    "six_players": ("六人游戏", 17),
}

# Only modules with action handling and regression coverage may be opened.
AVAILABLE_MODULES = {
    "new_districts", "kimchi", "sushi", "noodles", "ketchup", "fry_chefs",
    "night_shift", "mass_marketeers", "gourmet_critics", "movie_stars",
    "reserve_prices", "hard_choices", "six_players",
    "lobbyists", "rural_marketeers", "coffee", "new_milestones",
}


def descriptors():
    return [dict(id=k, name=v[0], rules_page=v[1], available=k in AVAILABLE_MODULES,
                 requires=["new_districts"] if k == "six_players" else [],
                 incompatible_with=["hard_choices"] if k == "new_milestones" else
                                   ["new_milestones"] if k == "hard_choices" else [])
            for k,v in MODULES.items()]


def normalize(config, players):
    modules = config.get("modules", [])
    require(isinstance(modules, list) and all(isinstance(m, str) for m in modules),
            "modules must be an array of module IDs", "invalid_parameters")
    require(len(set(modules)) == len(modules) and set(modules) <= MODULES.keys(),
            "Unknown or repeated FCM module", "invalid_parameters")
    selected = set(modules)
    require(selected <= AVAILABLE_MODULES,
            "Modules not yet available: " + ", ".join(sorted(selected - AVAILABLE_MODULES)))
    require(not ({"new_milestones", "hard_choices"} <= selected),
            "Hard choices requires base milestones; cannot combine with new_milestones")
    require(not config.get("introductory") or not selected,
            "The introductory rules cannot be combined with expansion modules")
    require(players != 6 or {"six_players", "new_districts"} <= selected,
            "Six-player games require six_players and new_districts")
    require("six_players" not in selected or (players == 6 and "new_districts" in selected),
            "six_players requires six players and new_districts")
    require(not (players >= 5 and "lobbyists" in selected) or "new_districts" in selected,
            "Lobbyists with five or six players require new_districts")
    return sorted(selected)
