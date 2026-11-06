"""Room-specific public contract; internal replay state keeps its stable format."""
from copy import deepcopy
from .catalog import BASE_PRODUCTS, MILESTONES, enabled_cards
from .modules import descriptors
from . import milestones as ms

PRODUCT_MODULES = {"sushi": "sushi", "noodles": "noodles", "kimchi": "kimchi", "coffee": "coffee"}
STATE_MODULES = {
    "lobby_supply": "lobbyists", "roadworks": "lobbyists", "built_features": "lobbyists",
    "offramps": "rural_marketeers", "rural": "rural_marketeers", "coffee_bonus": "coffee",
}


def products(modules):
    return [*BASE_PRODUCTS, *(p for p, m in PRODUCT_MODULES.items() if m in modules)]


def catalog(config):
    modules = config.get("modules", [])
    cards = deepcopy(enabled_cards(modules))
    for card in cards.values():
        card["upgrades"] = [k for k in card["upgrades"] if k in cards]
    return dict(scope="room", products=products(modules), employees=cards,
                milestones=[] if config.get("introductory") else ms.available(modules, MILESTONES),
                modules=[d for d in descriptors() if d["id"] in modules])


def observation(view):
    """Project an already redacted copy, including historical idempotent responses."""
    modules = view.get("modules", [])
    allowed = products(modules)
    for field, module in STATE_MODULES.items():
        if module not in modules:
            view.pop(field, None)
    # Internal suspended-dinner calculations are not a player-facing component.
    view.pop("dinner_context", None)
    if "lobbyists" not in modules:
        view.get("board", {}).pop("available_tiles", None)
    for p in view["players"].values():
        p["inventory"] = {k: p["inventory"].get(k, 0) for k in allowed}
        if "coffee" not in modules:
            p.pop("coffee_shops", None)
    if view.get("introductory"):
        view["milestone_pool"] = []
    return view


def action_schema(kind, s):
    from .actions import SCHEMAS
    schema = deepcopy(SCHEMAS[kind])
    modules = s.get("modules", [])
    props = schema["properties"]
    enabled = enabled_cards(modules)
    if kind == "choose_reserve":
        props["amount"]["enum"] = [5, 10, 20] if "reserve_prices" in modules else [100, 200, 300]
    elif kind == "choose_order":
        props["position"]["maximum"] = len(s["players"]) - 1
    elif kind == "work":
        props["hire"]["items"]["properties"]["kind"]["enum"] = [k for k,c in enabled.items() if c["entry"]]
        train = props["train"]["items"]["properties"]
        train["path"]["items"]["enum"] = list(enabled)
        if "coffee" not in modules:
            train.pop("coffee_shops")
        market = props["market"]["items"]["properties"]
        # Expansion products cannot be advertised, even when enabled.
        market["product"]["enum"] = list(BASE_PRODUCTS)
        if "rural_marketeers" not in modules:
            market.pop("rural_side")
            market.pop("offramp")
        if "new_milestones" not in modules:
            market.pop("second_product")
            market.pop("second_campaign")
            props["restaurants"]["items"]["properties"].pop("mailbox")
        props["produce"]["items"]["properties"]["product"]["enum"] = [p for p in products(modules) if p != "kimchi"]
        if "lobbyists" not in modules:
            props.pop("lobby")
    elif kind == "payday":
        if "new_milestones" not in modules:
            props.pop("food")
        else:
            props["food"]["properties"] = {k:v for k,v in props["food"]["properties"].items() if k in products(modules) and k != "coffee"}
    elif kind == "cleanup":
        props["keep"]["properties"] = {k:v for k,v in props["keep"]["properties"].items() if k in products(modules) and k != "coffee"}
    elif kind == "choose_bonus":
        choice = props["choice"]["properties"]
        if s.get("bonus", {}).get("kind") == "coffee":
            choice.pop("campaign_id")
        else:
            choice.pop("shop_id")
    return schema


def event(event, modules):
    result = deepcopy(event)
    if result.get("type") == "salaries_paid" and "new_milestones" not in modules:
        result.pop("food", None)
    if result.get("type") == "work_completed" and "plan" in result:
        # Older journals can contain empty expansion-specific fields.
        schema = action_schema("work", {"modules": modules})["properties"]
        result["plan"] = {k:v for k,v in result["plan"].items() if k in schema and v}
        for key in ("train", "market", "restaurants"):
            allowed = schema[key]["items"]["properties"]
            if key in result["plan"]:
                result["plan"][key] = [{k:v for k,v in row.items() if k in allowed} for row in result["plan"][key]]
    return result
