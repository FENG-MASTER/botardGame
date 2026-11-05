from boardgame.schema import obj, arr, enum, STRING, INT, BOOL, POINT
from .catalog import CARDS, PRODUCTS
from . import milestones as ms
from .expansion_map import PIECES

POINT = dict(type="array", items=dict(type="integer", minimum=0, maximum=129), minItems=2, maxItems=2)
TILE_POINT = dict(type="array", items=dict(type="integer", minimum=-1, maximum=26), minItems=2, maxItems=2)
SHOP = obj({"position": POINT, "shop_id": STRING}, ["position"])
OFFRAMP = obj({"tile": TILE_POINT, "side": enum("left","right","top","bottom")}, ["tile","side"])
CAMPAIGN = obj({"campaign_id":STRING, "position":POINT, "rotate":BOOL}, ["campaign_id","position"])
MAILBOX = obj({**CAMPAIGN["properties"], "product":enum("burger","pizza","beer","lemonade","soda")}, ["campaign_id","position","product"])


def action(kind, fields=None, required=()):
    return obj({"type": enum(kind), **(fields or {})}, ["type", *required])


PLACEMENT = {"position": POINT, "entrance": dict(type="integer", minimum=0, maximum=3)}
SCHEMAS = {
    "place_restaurant": action("place_restaurant", PLACEMENT, ["position"]),
    "pass": action("pass"),
    "choose_reserve": action(
        "choose_reserve", {"amount": enum(5, 10, 20, 100, 200, 300)}, ["amount"]
    ),
    "restructure": action(
        "restructure",
        {"structure": {"type": "object", "additionalProperties": STRING}},
        ["structure"],
    ),
    "choose_order": action(
        "choose_order",
        {"position": dict(type="integer", minimum=0, maximum=5)},
        ["position"],
    ),
    "work": action(
        "work",
        {
            "hire": arr(
                obj(
                    {
                        "recruiter": STRING,
                        "kind": enum(*[k for k, c in CARDS.items() if c["entry"]]),
                    },
                    ["recruiter", "kind"],
                )
            ),
            "train": arr(
                obj(
                    {
                        "trainer": STRING,
                        "employee": STRING,
                        "hire_index": dict(type="integer", minimum=0, maximum=99),
                        "path": arr(enum(*CARDS), 3),
                        "coffee_shops": arr(SHOP, 2),
                    },
                    ["trainer", "path"],
                )
            ),
            "market": arr(
                obj(
                    {
                        "employee": STRING,
                        "campaign_id": STRING,
                        "product": enum(*PRODUCTS),
                        "duration": dict(type="integer", minimum=1, maximum=5),
                        "position": POINT,
                        "rotate": BOOL,
                        "side": enum("left", "right", "top", "bottom"),
                        "offset": INT,
                        "edge_tile": TILE_POINT,
                        "rural_side": enum("left","right","top","bottom"),
                        "offramp": OFFRAMP,
                        "second_product": enum("burger","pizza","beer","lemonade","soda"),
                        "second_campaign": CAMPAIGN,
                    },
                    ["employee", "campaign_id", "product", "duration"],
                )
            ),
            "produce": arr(
                obj(
                    {
                        "employee": STRING,
                        "product": enum(*PRODUCTS),
                        "route": arr(POINT, 1000),
                    },
                    ["employee"],
                )
            ),
            "develop": arr(
                obj(
                    {
                        "employee": STRING,
                        "position": POINT,
                        "rotate": BOOL,
                        "house_id": INT,
                        "new_house_id": INT,
                    },
                    ["employee", "position"],
                )
            ),
            "lobby": arr(obj({
                "employee": STRING, "piece": enum(*PIECES), "position": POINT,
                "rotation": dict(type="integer", minimum=0, maximum=3),
                "city": obj({"tile_id":STRING, "tile":TILE_POINT, "rotation":dict(type="integer",minimum=0,maximum=3)}, ["tile_id","tile"]),
            }, ["employee","piece","position"])),
            "restaurants": arr(
                obj(
                    {"employee": STRING, **PLACEMENT, "restaurant_id": STRING, "mailbox": MAILBOX},
                    ["employee", "position"],
                )
            ),
        },
    ),
    "payday": action("payday", {"fire": arr(STRING), "food":obj({k:dict(type="integer",minimum=0) for k in PRODUCTS if k!="coffee"})}),
    "choose_bonus": action("choose_bonus", {"choice":obj({"position":POINT,"shop_id":STRING,"campaign_id":STRING},["position"])}),
    "cleanup": action(
        "cleanup",
        {
            "keep": obj(
                {k: dict(type="integer", minimum=0, maximum=10) for k in PRODUCTS}
            )
        },
    ),
}


def available(engine, s, pid):
    if pid not in engine.actors(s):
        return dict(
            can_act=False,
            actions=[],
            reason="finished" if s["finished"] else "waiting",
            actors=engine.actors(s),
        )
    phase = s["phase"]
    p = s["players"][pid]
    names = {
        "setup_restaurants": ["place_restaurant"]
        + (["pass"] if s["placement_pass"] == 1 else []),
        "reserve": ["choose_reserve"],
        "restructure": ["restructure"],
        "order": ["choose_order"],
        "work": ["work"],
        "payday": ["payday"],
        "cleanup": ["cleanup"],
        "bonus": ["choose_bonus"],
    }[phase]
    result = dict(
        can_act=True,
        actors=engine.actors(s),
        actions=[dict(type=k, schema=SCHEMAS[k]) for k in names],
        semantics="Schemas describe candidate actions. Use validate-action to check a complete plan without mutation.",
    )
    if phase == "bonus":
        result["bonus"] = s["bonus"]
        result["choices"] = engine.bonus_options(s)
    result["milestones"] = s["milestone_pool"]
    if phase == "order":
        result["available_positions"] = [
            i for i in range(len(engine.living(s))) if str(i) not in s["positions"]
        ]
    if phase == "reserve":
        result["reserve_choices"] = [5, 10, 20] if "reserve_prices" in s["modules"] else [100, 200, 300]
    result["modules"] = s["modules"]
    result["employee_kinds"] = list(s["stock"]) + ["ceo"]
    if phase == "payday":
        result.update(salary_due=engine.salary(p), cash=p["cash"])
    if phase == "cleanup":
        result["freezer_capacity"] = ms.freezer(p)
    if phase == "work":
        result["active_employees"] = engine.active(p)
        result["next_employee_id"] = "e" + str(s["next_employee"])
        result["plan_order"] = [
            "hire",
            "train",
            "market",
            "produce",
            "develop",
            "lobby",
            "restaurants",
        ]
        result["lobby_components"] = {k:dict(v,remaining=s["lobby_supply"].get(k,0)) for k,v in PIECES.items()}
        result["training_reference"] = (
            "Use employee ID or hire_index (zero-based index in this plan’s hire list)."
        )
    if phase == "setup_restaurants":
        # Fully legal finite placements make a fresh agent immediately operable.
        from copy import deepcopy
        from boardgame.core import GameError

        options = []
        for y in range(s["board"]["height"] - 1):
            for x in range(s["board"]["width"] - 1):
                for corner in range(4):
                    a = dict(type="place_restaurant", position=[x, y], entrance=corner)
                    try:
                        engine.place_restaurant(deepcopy(s), pid, a, setup=True)
                    except GameError:
                        continue
                    options.append(a)
        result["placements"] = options
    return result
