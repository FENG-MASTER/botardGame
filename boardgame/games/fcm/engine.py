from collections import Counter
from copy import deepcopy
import random
from boardgame.core import require, integer
from .catalog import CARDS, PRODUCTS, MILESTONES, stock, campaigns
from . import board as geo
from .modules import MODULES, normalize, descriptors
from .catalog import BASE_PRODUCTS, enabled_cards
from . import tiles as tile_data
from . import expansion_map as exmap
from . import milestones as ms
from . import coffee


class FCM:
    id = "fcm"
    version = "0.3.0"

    def descriptor(self):
        return dict(
            id=self.id,
            name="Food Chain Magnate",
            version=self.version,
            min_players=2,
            max_players=6,
            ruleset="base-2015-development",
            status="development",
            notes=[
                "Module availability is explicit; unavailable modules cannot be enabled.",
                "Map cells, component sizes and employee upgrades transcribed from supplied TTS assets and rulebooks.",
                "Development implementation; not certified for tournament use.",
            ],
            config_schema={
                "type": "object",
                "properties": {
                    "scenario": {"type": "object"},
                    "introductory": {"type": "boolean"},
                    "modules": {"type": "array", "items": {"enum": list(MODULES)}, "uniqueItems": True},
                },
                "additionalProperties": False,
            },
            employees=CARDS,
            products=PRODUCTS,
            milestones=MILESTONES,
            milestone_sets=dict(base=MILESTONES, new=ms.NEW, modules=ms.MODULE),
            modules=descriptors(),
        )

    def create(self, players, config, seed):
        require(2 <= len(players) <= 6, "FCM needs 2–6 players")
        require(
            set(config) <= {"scenario", "introductory", "modules"}, "Unsupported FCM configuration"
        )
        require(
            type(config.get("introductory", False)) is bool,
            "introductory must be boolean",
        )
        order = list(players)
        modules = normalize(config, len(players))
        random.Random(seed).shuffle(order)
        scenario = config.get("scenario", {})
        require(
            isinstance(scenario, dict)
            and set(scenario) <= {"board", "stock", "campaign_tiles"},
            "Invalid scenario",
        )
        board = deepcopy(scenario.get("board", tile_data.generated(len(players), seed, modules)))
        geo.validate(board)
        supply = deepcopy(scenario.get("stock", stock(len(players), modules)))
        require(
            isinstance(supply, dict) and set(supply) == set(enabled_cards(modules)) - {"ceo"},
            "Scenario stock must define every employee except CEO",
        )
        for k, v in supply.items():
            integer(v, 0, 100, "stock." + k)
        tiles = deepcopy(scenario.get("campaign_tiles", campaigns(len(players), modules)))
        require(
            isinstance(tiles, dict) and 1 <= len(tiles) <= 24, "Invalid campaign tiles"
        )
        for k, v in tiles.items():
            require(
                k.isdigit() and 1 <= int(k) <= 24 and isinstance(v, dict),
                "Invalid campaign id",
            )
            require(
                v.get("kind") in ("billboard", "mailbox", "airplane", "radio", "guide", "giant_billboard"),
                "Invalid campaign kind",
            )
            integer(v.get("width"), 1, 5, "campaign width")
            integer(v.get("height"), 1, 5, "campaign height")
        intro = config.get("introductory", False)
        return dict(
            modules=modules,
            lobby_supply={k:v["count"] for k,v in exmap.PIECES.items()} if "lobbyists" in modules else {},
            roadworks=[],
            built_features=[],
            offramps=[],
            rural=dict(id="rural", order=1000, cells=[], garden=False, rural=True, demand=[], demand_sources=[]),
            base_price=10,
            new_house_ids=tile_data.NEW_HOUSES,
            phase="setup_restaurants",
            round=1,
            order=order,
            queue=list(reversed(order)),
            passed=[],
            placement_pass=1,
            players={
                p: dict(
                    modules=modules,
                    cash=0,
                    employees=[dict(id=p + ":ceo", kind="ceo", busy=None)],
                    active=[p + ":ceo"],
                    structure={},
                    restaurants=[],
                    inventory={k: 0 for k in PRODUCTS},
                    milestones=[],
                    eliminated=False,
                    hire_discount=0,
                    coffee_shops=[],
                )
                for p in players
            },
            board=board,
            stock=supply,
            campaign_tiles=tiles,
            campaigns=[],
            reserves={},
            bank=len(players) * (75 if intro else 50),
            bank_breaks=0,
            ceo_slots=3,
            next_ceo_slots=3,
            introductory=intro,
            pending={},
            milestone_pool=ms.available(modules, MILESTONES),
            coffee_bonus=[],
            closed_milestones=[],
            claimed=[],
            next_employee=1,
            winner=None,
            finished=False,
            scenario="custom" if scenario else "tts-2202544434",
            log=[],
        )

    def emit(self, s, kind, **data):
        s["log"].append(dict(type=kind, **data))

    def grant(self, s, pid, m):
        p = s["players"][pid]
        if m not in s["milestone_pool"] or s["introductory"] or m in s["closed_milestones"] or m in p["milestones"]:
            return False
        p["milestones"].append(m)
        if m not in s["claimed"]:
            s["claimed"].append(m)
        self.emit(s, "milestone", player=pid, milestone=m)
        bonus = {
            "first_burger_produced": ("burger_cook", 1),
            "first_pizza_produced": ("pizza_cook", 1),
            "first_hire_three": ("management_trainee", 2),
        }.get(m)
        if bonus:
            for _ in range(min(bonus[1], s["stock"][bonus[0]])):
                self.employee(s, pid, bonus[0])
        if m == 'new_first_marketing_trainee_used':
            for kind in ('kitchen_trainee','errand_boy'):
                if s['stock'][kind]:self.employee(s,pid,kind)
        if m in ('new_first_recruiting_girl_used','new_first_trainer_used'):
            kind='executive_vice_president' if m=='new_first_recruiting_girl_used' else 'trainer'
            if s['stock'][kind] or kind=='executive_vice_president':
                extra=s['stock'][kind]==0
                if extra:s['stock'][kind]+=1
                eid=self.employee(s,pid,kind)
                employee=next(e for e in p['employees'] if e['id']==eid)
                employee['box_copy']=extra
                if kind=='executive_vice_president':employee['salary_exempt']=True
        if m == 'first_coffee_sold':s['coffee_bonus'].append(pid)
        return True

    def employee(self, s, pid, kind):
        require(kind in s["stock"] and s["stock"][kind] > 0, "Employee is out of stock")
        p = s["players"][pid]
        require(
            not CARDS[kind]["unique"] or all(e["kind"] != kind for e in p["employees"]),
            "Only one copy of this top position is permitted",
        )
        require(not kind.endswith("_movie_star") or not any(e["kind"].endswith("_movie_star") for e in p["employees"]),
                "Only one movie star per company")
        require(
            kind != "cfo" or "first_hundred" not in p["milestones"],
            "CFO forbidden after first_hundred",
        )
        eid = "e" + str(s["next_employee"])
        s["next_employee"] += 1
        p["employees"].append(dict(id=eid, kind=kind, busy=None))
        s["stock"][kind] -= 1
        return eid

    def active(self, p):
        return [e for e in p["employees"] if e["id"] in p["active"]]

    def movie_rank(self, p):
        ranks = {"b_movie_star": 0, "c_movie_star": 1, "d_movie_star": 2}
        return min((ranks.get(e["kind"], 3) for e in self.active(p)), default=3)

    def work_multiplier(self, p, employee):
        if employee["kind"] == "ceo" or self.salary_required(p, employee):
            return 1
        return 2 if any(e["kind"] == "night_shift_manager" for e in self.active(p)) else 1

    def salary_required(self, p, employee):
        card = CARDS[employee["kind"]]
        return card["salary"] and not employee.get("salary_exempt", False) and not (
            card["color"] == "blue" and "first_billboard" in p["milestones"]
        )

    def living(self, s):
        return [pid for pid in s["order"] if not s["players"][pid]["eliminated"]]

    def actors(self, s):
        if s["finished"]:
            return []
        if s["phase"] in ("reserve", "restructure", "payday", "cleanup"):
            return [p for p in self.living(s) if p not in s["pending"]]
        return s["queue"][:1]

    def observe(self, s, pid):
        view = deepcopy(s)
        view.pop("log", None)
        view["actors"] = self.actors(s)
        view["submitted"] = list(s["pending"])
        view["pending"] = (
            {pid: deepcopy(s["pending"][pid])} if pid in s["pending"] else {}
        )
        can_see = s["bank_breaks"] > 0 or (
            pid in s["players"] and "first_twenty" in s["players"][pid]["milestones"]
        )
        view["reserves"] = {
            p: (v if can_see or p == pid else None) for p, v in s["reserves"].items()
        }
        # Employees are public, but face-down current commitments never are.
        if s["phase"] == "restructure":
            for p, company in view["players"].items():
                if p != pid:
                    company["active"] = []
                    company["structure"] = {}
        return view

    def apply(self, s, pid, a):
        s["log"] = []
        self.apply_decision(s, pid, a)
        self.advance_automatic(s)
        return s.pop("log", [])

    def automatic_action(self, s, pid):
        """Only resolve forced decisions; never choose a player's strategy."""
        p = s["players"][pid]
        phase = s["phase"]
        if phase == 'bonus' and not self.bonus_options(s):
            return dict(type='choose_bonus'), 'no_bonus_placement'
        if phase == "restructure" and not any(
            e["kind"] != "ceo" and not e["busy"] for e in p["employees"]
        ):
            return dict(type="restructure", structure={}), "no_available_employees"
        if phase == "order":
            positions = [
                i for i in range(len(self.living(s)))
                if str(i) not in s["positions"]
            ]
            if len(positions) == 1:
                return dict(type="choose_order", position=positions[0]), "only_position"
        if (
            phase == "payday"
            and not any(
                e["kind"] != "ceo" and not e["busy"] for e in p["employees"]
            )
            and self.salary(p) <= p["cash"]
        ):
            # No optional firing, and busy marketers need not be fired.
            return dict(type="payday", fire=[]), "no_firing_choice"
        if phase == "cleanup":
            if not any(p["inventory"].values()):
                return dict(type="cleanup", keep={}), "empty_inventory"
            if not ms.freezer(p):
                return dict(type="cleanup", keep={}), "no_freezer"
        return None

    def advance_automatic(self, s):
        # Each action advances a queue or pending set. Work always remains a
        # decision boundary, so this cannot run through unbounded empty rounds.
        while not s["finished"]:
            for pid in self.actors(s):
                automatic = self.automatic_action(s, pid)
                if automatic is not None:
                    action, reason = automatic
                    self.emit(
                        s, "decision_automated", player=pid,
                        phase=s["phase"], reason=reason,
                    )
                    self.apply_decision(s, pid, action)
                    break
            else:
                return

    def apply_decision(self, s, pid, a):
        require(isinstance(a, dict), "action must be an object", "invalid_parameters")
        from .actions import SCHEMAS
        from boardgame.schema import validate

        require(
            isinstance(a.get("type"), str) and a["type"] in SCHEMAS,
            "Unknown action type",
            "invalid_parameters",
        )
        validate(a, SCHEMAS[a["type"]])
        require(
            pid in self.actors(s), "You cannot act in this phase", "not_your_turn", 409
        )
        phase = s["phase"]
        kind = a.get("type")
        if phase == 'bonus':
            require(kind=='choose_bonus', 'Choose a bonus placement')
            choice=a.get('choice')
            options=self.bonus_options(s)
            require(choice in options or choice is None and not options, 'Choose one of the available bonus placements')
            info=s.pop('bonus')
            if choice is not None:
                if info['kind']=='coffee':exmap.shop(s,pid,choice,unlimited=True)
                else:self.bonus_campaign(s,pid,'radio',choice,house=info['house'])
            if info['kind']=='coffee':
                s['coffee_bonus'].remove(pid)
                self.cleanup_bonuses(s)
            else:self.dinner(s,resume=True)
        elif phase == "setup_restaurants":
            require(
                kind in ("place_restaurant", "pass"), "Choose place_restaurant or pass"
            )
            if kind == "pass":
                require(s["placement_pass"] == 1, "Second placement pass is mandatory")
                s["passed"].append(pid)
            else:
                self.place_restaurant(s, pid, a, setup=True)
            s["queue"].pop(0)
            if not s["queue"]:
                if s["passed"]:
                    s["queue"] = [p for p in s["order"] if p in s["passed"]]
                    s["passed"] = []
                    s["placement_pass"] = 2
                else:
                    s["phase"] = "restructure" if s["introductory"] else "reserve"
                    s["pending"] = {}
        elif phase == "reserve":
            require(kind == "choose_reserve", "Choose a reserve card")
            require(
                type(a.get("amount")) is int and a["amount"] in (
                    (5, 10, 20) if "reserve_prices" in s.get("modules", []) else (100, 200, 300)
                ),
                "Reserve must be 100, 200 or 300",
            )
            s["reserves"][pid] = a["amount"]
            s["pending"][pid] = True
            if len(s["pending"]) == len(self.living(s)):
                s["phase"] = "restructure"
                s["pending"] = {}
        elif phase == "restructure":
            require(kind == "restructure", "Submit your organization structure")
            self.restructure(s, pid, a)
            if len(s["pending"]) == len(self.living(s)):
                self.reveal(s)
        elif phase == "order":
            require(kind == "choose_order", "Choose an available turn-order position")
            position = integer(
                a.get("position"), 0, len(self.living(s)) - 1, "position"
            )
            require(str(position) not in s["positions"], "Position already taken")
            s["positions"][str(position)] = pid
            s["queue"].pop(0)
            if not s["queue"]:
                s["order"] = [
                    s["positions"][str(i)] for i in range(len(s["positions"]))
                ]
                s["phase"] = "work"
                s["queue"] = self.living(s)
        elif phase == "work":
            require(kind == "work", "Submit an atomic working-day plan")
            self.work(s, pid, a)
            s["queue"].pop(0)
            if not s["queue"]:
                self.dinner(s)
        elif phase == "payday":
            require(kind == "payday", "Submit employees to fire")
            self.payday(s, pid, a)
            s["pending"][pid] = True
            if len(s["pending"]) == len(self.living(s)):
                self.marketing(s)
                s["phase"] = "cleanup"
                s["pending"] = {}
        elif phase == "cleanup":
            require(kind == "cleanup", "Select inventory to keep")
            self.cleanup(s, pid, a)
            s["pending"][pid] = True
            if len(s["pending"]) == len(self.living(s)):
                self.cleanup_bonuses(s)

    def cleanup_bonuses(self,s):
        s['roadworks']=[]
        for row in s['board']['cells']:
            for x,cell in enumerate(row):
                if cell=='construction':row[x]='road'
        for pid in self.living(s):
            if pid in s['coffee_bonus']:
                s['phase']='bonus';s['queue']=[pid];s['bonus']=dict(kind='coffee',player=pid)
                return
        self.new_round(s)

    def bonus_campaign(self,s,pid,kind,a,house=None,restaurant=None):
        tile=s['campaign_tiles'].get(a.get('campaign_id'),{})
        require(tile.get('kind')==kind, 'Wrong bonus marketing tile')
        temp=dict(id=None,kind='brand_director',busy=None)
        self.market(s,pid,temp,CARDS['brand_director'],dict(a,duration=2 if kind=='radio' else 1,product='pizza' if kind=='radio' else a.get('product')),bonus=True)
        campaign=s['campaigns'][-1]
        target=house['cells'] if house else [restaurant['entrance']]
        require(all(geo.tile(v) in {geo.tile(q) for q in target} for v in campaign['cells']), 'Bonus campaign must fit in the destination city tile')
        campaign['eternal']=kind=='mailbox';campaign['remaining']=None if kind=='mailbox' else 2

    def bonus_options(self,s):
        from boardgame.core import GameError
        info=s['bonus'];pid=info['player'];result=[];b=s['board']
        if info['kind']=='coffee':
            shops=s['players'][pid]['coffee_shops']
            ids=[v['id'] for v in shops] if len(shops)==3 else [None]
            for y in range(b['height']):
                for x in range(b['width']):
                    if b['cells'][y][x]!='empty':continue
                    for sid in ids:
                        a=dict(position=[x,y]);
                        if sid:a['shop_id']=sid
                        try:exmap.shop(deepcopy(s),pid,a,unlimited=True)
                        except GameError:continue
                        result.append(a)
        else:
            available=[cid for cid,t in s['campaign_tiles'].items() if t['kind']=='radio' and not any(c['id']==cid for c in s['campaigns'])]
            for tx,ty in sorted({geo.tile(v) for v in info['house']['cells']}):
                for y in range(ty*5,ty*5+5):
                    for x in range(tx*5,tx*5+5):
                        for cid in available:
                            a=dict(campaign_id=cid,position=[x,y])
                            try:self.bonus_campaign(deepcopy(s),pid,'radio',a,house=info['house'])
                            except GameError:continue
                            result.append(a)
        return result

    def restructure(self, s, pid, a):
        p = s["players"][pid]
        structure = a.get("structure", {})
        require(
            isinstance(structure, dict), "structure maps employee IDs to supervisor IDs"
        )
        em = {e["id"]: e for e in p["employees"]}
        ceo = pid + ":ceo"
        require(
            all(
                e in em and e != ceo and not em[e]["busy"] and isinstance(parent, str)
                for e, parent in structure.items()
            ),
            "Unknown, CEO or busy employee in structure",
        )
        valid = True
        counts = Counter(structure.values())
        for eid, parent in structure.items():
            if parent != ceo:
                if (
                    parent not in structure
                    or structure[parent] != ceo
                    or not CARDS[em[parent]["kind"]]["slots"]
                    or CARDS[em[eid]["kind"]]["manager"]
                ):
                    valid = False
        for parent, count in counts.items():
            capacity = (
                ms.ceo_slots(s, p)
                if parent == ceo
                else CARDS[em[parent]["kind"]]["slots"]
                if parent in em
                else 0
            )
            if count > capacity:
                valid = False
        s["pending"][pid] = dict(
            structure=structure if valid else {}, overflow=not valid
        )

    def reveal(self, s):
        for pid in self.living(s):
            p = s["players"][pid]
            p["structure"] = s["pending"][pid]["structure"]
            p["active"] = [pid + ":ceo"] + sorted(p["structure"])
            for e in self.active(p):
                m = {
                    "waitress": "first_waitress",
                    "errand_boy": "first_errand_boy",
                    "cart_operator": "first_cart_operator",
                    "pricing_manager": "first_lower_price",
                    "discount_manager": "first_lower_price",
                }.get(e["kind"])
                if m:
                    self.grant(s, pid, m)
            if s["pending"][pid]["overflow"]:
                self.emit(s, "structure_overflow", player=pid)

        for pid in self.living(s):
            p=s['players'][pid]
            if 'new_first_discount_manager_used' in p['milestones'] and sum(CARDS[e['kind']]['price'] for e in self.active(p)) <= -3:
                # Remove money without awarding cash or triggering cash milestones.
                self.pay(s,pid,100)
                p['cash']-=100
                self.emit(s,'discount_bank_removed',player=pid,amount=100)

        def slots(pid):
            p = s["players"][pid]
            return (
                ms.ceo_slots(s, p)
                + sum(
                    CARDS[e["kind"]]["slots"]
                    for e in self.active(p)
                    if e["kind"] != "ceo"
                )
                - len(p["structure"])
                + 2 * ("first_airplane" in p["milestones"])
            )

        s["queue"] = sorted(
            self.living(s), key=lambda p: (self.movie_rank(s["players"][p]), -slots(p), s["order"].index(p))
        )
        s["pending"] = {}
        s["positions"] = {}
        s["phase"] = "order"
        self.emit(s, "structures_revealed")

    def place_restaurant(self, s, pid, a, setup=False, manager=None):
        p = s["players"][pid]
        b = s["board"]
        x, y = geo.point(b, a.get("position"))
        corner = integer(a.get("entrance", 0), 0, 3, "entrance")
        area = geo.rectangle(x, y, 2, 2)
        entrance = area[corner]
        moving = a.get("restaurant_id")
        require(
            not moving or (not setup and manager == "regional_manager"),
            "Only regional managers can move restaurants",
        )
        old = next((r for r in p["restaurants"] if r["id"] == moving), None)
        require(not moving or old is not None, "Restaurant not owned")
        geo.empty(s, area, moving)
        require(
            any(geo.road(b, q) for q in geo.neighbors(entrance)),
            "Entrance must border a road",
        )
        if setup:
            require(
                all(
                    geo.tile(r["entrance"]) != geo.tile(entrance)
                    for v in s["players"].values()
                    for r in v["restaurants"]
                ),
                "Starting entrances must occupy distinct tiles",
            )
        if manager == "local_manager":
            require(
                geo.distance(b, geo.entrances(s, pid), [entrance]) <= 3,
                "New restaurant is beyond local manager range",
            )
        require(old or len(p["restaurants"]) < 3, "Only three restaurants per chain")
        if old:
            p["restaurants"].remove(old)
        p["restaurants"].append(
            dict(
                id=moving or pid + ":r" + str(len(p["restaurants"]) + 1),
                cells=area,
                entrance=entrance,
                open=manager != "local_manager",
            )
        )

    def work(self, s, pid, a):
        require(
            set(a)
            <= {"type", "hire", "train", "market", "produce", "develop", "lobby", "restaurants"},
            "Unknown working-day field",
        )
        for key in ("hire", "train", "market", "produce", "develop", "lobby", "restaurants"):
            require(
                isinstance(a.get(key, []), list) and len(a.get(key, [])) <= 100,
                f"{key} must be an array of at most 100 actions",
            )
        p = s["players"][pid]
        active = {e["id"]: e for e in self.active(p)}
        hire_used = Counter()
        train_used = Counter()
        trained = {}
        debt = set()
        hire_ids = []
        exhausted = set()

        def actor(eid, ability=None):
            require(isinstance(eid, str) and eid in active, "Employee is not active")
            require(eid not in exhausted, "Already-used employee cannot work again after promotion")
            e = active[eid]
            c = CARDS[e["kind"]]
            if ability:
                require(c[ability], "Employee does not have this ability")
            return e, c

        for item in a.get("hire", []):
            require(isinstance(item, dict), "Invalid hire action")
            recruiter, c = actor(item.get("recruiter"), "hire")
            kind = item.get("kind")
            require(
                isinstance(kind, str) and kind in s["stock"] and CARDS[kind]["entry"],
                "Only entry positions can be hired",
            )
            hire_used[item["recruiter"]] += 1
            require(
                hire_used[item["recruiter"]] <= c["hire"] * self.work_multiplier(p, active[item["recruiter"]]),
                "Recruitment capacity exceeded",
            )
            if s["stock"][kind] > 0:
                eid = self.employee(s, pid, kind)
            else:
                eid = "e" + str(s["next_employee"])
                s["next_employee"] += 1
                p["employees"].append(dict(id=eid, kind=kind, busy=None))
                debt.add(eid)
            hire_ids.append(eid)
            if recruiter["kind"] == "recruiting_girl":self.grant(s,pid,"new_first_recruiting_girl_used")
        if len(a.get("hire", [])) >= 3:
            self.grant(s, pid, "first_hire_three")
        p["hire_discount"] = 5 * sum(
            CARDS[e["kind"]]["hire"] - hire_used[eid]
            for eid, e in active.items()
            if CARDS[e["kind"]]["discount"]
        )
        for item in a.get("train", []):
            require(isinstance(item, dict), "Invalid training action")
            trainer = item.get("trainer")
            trainer_employee, c = actor(trainer, "train")
            trainer_kind=trainer_employee["kind"]
            target = item.get("employee")
            e = next((e for e in p["employees"] if e["id"] == target), None)
            # Newly hired cards can be referenced by zero-based hire index as well.
            if e is None and type(item.get("hire_index")) is int:
                index = integer(
                    item["hire_index"], 0, len(a.get("hire", [])) - 1, "hire_index"
                )
                e = next(v for v in p["employees"] if v["id"] == hire_ids[index])
            require(
                e is not None and (e["id"] not in active or "new_first_lemonade_sold" in p["milestones"]) and not e["busy"],
                "Only beach employees can be trained",
            )
            target = e["id"]
            path = item.get("path")
            require(
                isinstance(path, list)
                and 1 <= len(path) <= 3
                and all(isinstance(k, str) for k in path),
                "Training path must contain 1–3 positions",
            )
            require(
                target not in trained
                or trained[target] == trainer
                or ms.stacking(p),
                "Cannot combine trainers on one employee without milestone",
            )
            train_used[trainer] += len(path)
            if train_used[trainer] > c["train"] and not ms.stacking(p):
                require(target not in trained and len(path) <= c["train"],
                        "Night shift cannot train the same employee twice without stacking milestone")
            require(train_used[trainer] <= c["train"] * self.work_multiplier(p, active[trainer]), "Training capacity exceeded")
            original = e["kind"]
            previous = original
            for kind in path:
                require(kind in s["stock"] and kind in CARDS[previous]["upgrades"], "Invalid upgrade path")
                if e['id'] in active:
                    require(CARDS[kind]['color']==CARDS[original]['color'], 'Active training cannot change employee color')
                    if hire_used[e['id']] or train_used[e['id']]:exhausted.add(e['id'])
                previous = kind
            final = path[-1]
            require(not final.endswith("_movie_star") or not any(v["kind"].endswith("_movie_star") for v in p["employees"]),
                    "Only one movie star per company")
            require(s["stock"][final] > 0, "Final training card out of stock")
            require(
                not CARDS[final]["unique"]
                or not any(v["kind"] == final for v in p["employees"]),
                "Duplicate top position",
            )
            require(
                final != "cfo" or "first_hundred" not in p["milestones"],
                "CFO forbidden after first_hundred",
            )
            if target not in debt:
                s["stock"][e["kind"]] += 1
            debt.discard(target)
            s["stock"][final] -= 1
            e["kind"] = final
            trained[target] = trainer
            self.grant(s, pid, "first_train")
            if trainer_kind=='trainer':self.grant(s,pid,'new_first_trainer_used')
            shops=item.get('coffee_shops',[])
            opportunities=sum(k in ('barista','lead_barista') for k in path)
            require(len(shops)<=opportunities, 'Too many coffee shops for this training path')
            for placement in shops:exmap.shop(s,pid,placement)
        require(not debt, "Out-of-stock recruits must be trained immediately")
        used = Counter()
        for item in a.get("market", []):
            require(isinstance(item, dict), "Invalid marketing action")
            e, c = actor(item.get("employee"), "marketing")
            require(used[e["id"]] < self.work_multiplier(p, e), "Employee used too many times")
            used[e["id"]] += 1
            self.market(s, pid, e, c, item)
        for item in a.get("produce", []):
            require(isinstance(item, dict), "Invalid production action")
            e, c = actor(item.get("employee"), "quantity")
            require(used[e["id"]] < self.work_multiplier(p, e), "Employee used too many times")
            used[e["id"]] += 1
            self.produce(s, pid, e, c, item)
        for item in a.get("develop", []):
            require(isinstance(item, dict), "Invalid development action")
            e, _ = actor(item.get("employee"))
            require(
                e["kind"] == "new_business_developer" and e["id"] not in used,
                "Invalid or reused developer",
            )
            used[e["id"]] += 1
            self.develop(s, item)
            if not item.get("house_id"):self.grant(s,pid,"new_first_house_built")
        for item in a.get("lobby", []):
            require("lobbyists" in s["modules"], "Lobbyists module is disabled")
            e, _ = actor(item.get("employee"))
            require(e["kind"] == "lobbyist" and not used[e["id"]], "Invalid or reused lobbyist")
            used[e["id"]] += 1
            exmap.lobby(self, s, pid, item)
        for item in a.get("restaurants", []):
            require(isinstance(item, dict), "Invalid restaurant action")
            e, _ = actor(item.get("employee"))
            require(
                e["kind"] in ("local_manager", "regional_manager")
                and e["id"] not in used,
                "Invalid or reused manager",
            )
            used[e["id"]] += 1
            self.place_restaurant(s, pid, item, manager=e["kind"])
            if not item.get('restaurant_id') and self.grant(s,pid,'new_first_restaurant'):
                bonus=item.get('mailbox')
                if bonus:
                    self.bonus_campaign(s,pid,'mailbox',bonus,restaurant=p['restaurants'][-1])
            else:require(not item.get('mailbox'), 'No new restaurant mailbox bonus')
        if any(e['kind']=='discount_manager' for e in self.active(p)):
            self.grant(s,pid,'new_first_discount_manager_used')
        self.emit(s, "work_completed", player=pid)

    def market(self, s, pid, e, c, a, bonus=False):
        p = s["players"][pid]
        b = s["board"]
        cid = a.get("campaign_id")
        require(
            isinstance(cid, str) and cid in s["campaign_tiles"], "Unknown campaign tile"
        )
        require(
            not any(v["id"] == cid for v in s["campaigns"]),
            "Campaign tile already in use",
        )
        t = s["campaign_tiles"][cid]
        kind = t["kind"]
        if e["kind"] == "gourmet_food_critic":
            require(kind == "guide", "Gourmet critics may only place guides")
        elif e["kind"] == "rural_marketeer":
            require(kind == "giant_billboard", "Rural marketeers may only place giant billboards")
        else:
            require(kind in ("billboard", "mailbox", "airplane", "radio") and
                    c["marketing"] >= {"billboard": 1, "mailbox": 2, "airplane": 3, "radio": 4}.get(kind, 99),
                    "Marketeer cannot launch this campaign")
        fresh=False if bonus else self.grant(s,pid,'new_first_'+e['kind']+'_used')
        if not bonus:self.grant(s,pid,'new_first_marketeer_used')
        product = a.get("product")
        require(product in BASE_PRODUCTS, "Only base foods and drinks can be marketed")
        duration = integer(a.get("duration"), 1, c["marketing"] + 1, "duration")
        campaign = dict(
            id=cid,
            kind=kind,
            player=pid,
            employee=e["id"],
            product=product,
            remaining=duration,
            cells=[],
        )
        if kind == "airplane":
            side = a.get("side")
            require(side in ("left", "right", "top", "bottom"), "Invalid airplane side")
            offset = integer(
                a.get("offset"),
                0,
                (b["height"] if side in ("left", "right") else b["width"]) - t["width"],
                "offset",
            )
            edge=a.get('edge_tile')
            if edge is not None:
                tx,ty=edge
                require((tx,ty) in exmap.tile_positions(b), 'Unknown airplane anchor tile')
                line={'left':tx*5,'right':tx*5+5,'top':ty*5,'bottom':ty*5+5}[side]
            else:line={'left':0,'right':b['width'],'top':0,'bottom':b['height']}[side]
            for coordinate in range(offset,offset+t['width']):
                tx,ty=({'left':(line//5,coordinate//5),'right':(line//5-1,coordinate//5),'top':(coordinate//5,line//5),'bottom':(coordinate//5,line//5-1)})[side]
                require(exmap.edge_clear(dict(s,campaigns=[]),tx,ty,side), 'Airplane must occupy an exposed edge without highway')
            require(not any(v['kind']=='airplane' and v['side']==side and v.get('edge_line',line)==line and max(offset,v['offset'])<min(offset+t['width'],v['offset']+v['span']) for v in s['campaigns']), 'Airplane tiles overlap')
            campaign.update(side=side, offset=offset, span=t['width'], edge_line=line)
        elif kind == "giant_billboard":
            side = a.get("rural_side")
            require(side in exmap.SIDES, "Choose a rural billboard side")
            require(not any(v["kind"] == kind and v["rural_side"] == side for v in s["campaigns"]), "Rural side occupied")
            campaign["rural_side"] = side
            if self.grant(s, pid, "first_rural_marketeer_used") and len(s["offramps"]) < 3:
                require(a.get("offramp") is not None, "First rural marketer use requires a highway offramp")
                exmap.add_offramp(s, a["offramp"])
            else:
                require(not a.get("offramp"), "No highway bonus available")
        elif kind == "guide":
            pass
        else:
            x, y = geo.point(b, a.get("position"))
            rotate = a.get("rotate", False)
            require(type(rotate) is bool, "rotate must be boolean")
            w, h = (t["height"], t["width"]) if rotate else (t["width"], t["height"])
            area = geo.rectangle(x, y, w, h)
            geo.empty(s, area)
            require(
                any(geo.road(b, q) for v in area for q in geo.neighbors(v)),
                "Campaign must border a road",
            )
            if c["distance"] is not None:
                require(
                    geo.distance(b, geo.entrances(s, pid), area) <= c["distance"],
                    "Campaign is out of range",
                )
            campaign["cells"] = area
        if not bonus and kind in ("billboard", "airplane", "radio"):
            self.grant(s, pid, "first_" + kind)
        if not bonus:self.grant(
            s,
            pid,
            "first_"
            + (product if product in ("burger", "pizza") else "drink")
            + "_marketed",
        )
        second_product=a.get('second_product')
        require(not second_product or (fresh and e['kind']=='brand_manager' and kind=='airplane'), 'Second product only for first brand manager airplane')
        if second_product:campaign['products']=[product,second_product]
        campaign["eternal"] = kind == "giant_billboard" or "first_billboard" in p["milestones"] or (kind=='radio' and 'new_first_brand_director_used' in p['milestones'])
        if campaign["eternal"]:
            campaign["remaining"] = None
        e["busy"] = cid
        s["campaigns"].append(campaign)
        second=a.get('second_campaign')
        if second:
            require(fresh and e['kind']=='campaign_manager', 'Extra campaign only for first campaign manager use')
            require(s['campaign_tiles'].get(second.get('campaign_id'),{}).get('kind')==kind, 'Extra campaign must have same type')
            self.market(s,pid,e,c,dict(second,product=product,duration=duration))

    def produce(self, s, pid, e, c, a):
        p = s["players"][pid]
        kind = e["kind"]
        product = a.get("product")
        b = s["board"]
        if kind in ("kitchen_trainee", "errand_boy") or c["product"]:
            allowed = (
                ["burger", "pizza"]
                if kind == "kitchen_trainee"
                else ["beer", "lemonade", "soda"]
                if kind == "errand_boy"
                else [c["product"]]
            )
            product = product or c["product"]
            require(product in allowed, "Employee cannot produce this product")
            qty = c["quantity"] + int(
                kind == "errand_boy" and "first_errand_boy" in p["milestones"]
            )
            p["inventory"][product] += qty
            if product in ("burger", "pizza"):
                self.grant(s, pid, "first_" + product + "_produced")
            return
        path = a.get("route")
        require(
            isinstance(path, list) and 1 <= len(path) <= 1000, "Buyer needs a route"
        )
        reach = c["distance"] + int("first_cart_operator" in p["milestones"])
        sources = set()
        if kind == "zeppelin_pilot":
            require(
                all(
                    isinstance(q, list)
                    and len(q) == 2
                    and all(type(v) is int for v in q)
                    for q in path
                ),
                "Zeppelin route uses tile coordinates",
            )
            points = list(map(tuple, path))
            require(
                len(set(points)) == len(points) and len(points) - 1 <= reach,
                "Zeppelin cannot revisit tiles or exceed range",
            )
            require(
                points[0] in {geo.tile(q) for q in geo.entrances(s, pid)},
                "Route must start at a restaurant tile",
            )
            for i, q in enumerate(points):
                require(
                    q in exmap.tile_positions(b),
                    "Tile outside board",
                )
                require(
                    i == 0 or q in geo.neighbors(points[i - 1]),
                    "Zeppelin route must be orthogonally connected",
                )
                for y in range(q[1] * 5, q[1] * 5 + 5):
                    for x in range(q[0] * 5, q[0] * 5 + 5):
                        if b["cells"][y][x] in ("beer", "lemonade", "soda"):
                            sources.add((x, y))
        else:
            points = [geo.point(b, q) for q in path]
            starts = [q for q in geo.entrances(s, pid) if points[0] in geo.neighbors(q)]
            require(starts, "Route must start on a road at a restaurant entrance")
            cost = min(int(geo.tile(q) != geo.tile(points[0])) for q in starts)
            for i, q in enumerate(points):
                require(geo.road(b, q), "Buyer route must follow roads")
                if i:
                    require(
                        q in geo.neighbors(points[i - 1]), "Route must be connected"
                    )
                    cost += int(geo.tile(q) != geo.tile(points[i - 1]))
                if i >= 2:
                    require(q != points[i - 2], "Buyer cannot make a U-turn")
                if i and i < len(points) - 1 and b["cells"][q[1]][q[0]] == "bridge":
                    require(
                        points[i - 1][0] == points[i + 1][0]
                        or points[i - 1][1] == points[i + 1][1],
                        "Cannot turn on a bridge",
                    )
                for src in geo.neighbors(q):
                    if geo.inside(b, src) and b["cells"][src[1]][src[0]] in (
                        "beer",
                        "lemonade",
                        "soda",
                    ):
                        sources.add(src)
            require(cost <= reach, "Buyer exceeded tile range")
        qty = c["quantity"] + int("first_errand_boy" in p["milestones"])
        if kind == "cart_operator" and sources:self.grant(s,pid,"new_first_cart_operator_used")
        for x, y in sources:
            p["inventory"][b["cells"][y][x]] += qty * (2 if "new_first_cart_operator_used" in p["milestones"] else 1)

    def develop(self, s, a):
        b = s["board"]
        x, y = geo.point(b, a.get("position"))
        rotate = a.get("rotate", False)
        require(type(rotate) is bool, "rotate must be boolean")
        house_id = a.get("house_id")
        if house_id is not None:
            h = next((h for h in b["houses"] if h["id"] == house_id), None)
            require(
                h and not h["garden"] and h["printed"],
                "Garden needs a printed house without a garden",
            )
            area = geo.rectangle(x, y, 1 if rotate else 2, 2 if rotate else 1)
            geo.empty(s, area)
            combined = h["cells"] + area
            xs = [q[0] for q in combined]
            ys = [q[1] for q in combined]
            require(
                sorted([max(xs) - min(xs) + 1, max(ys) - min(ys) + 1]) == [2, 3],
                "House and garden must form a 2×3 rectangle",
            )
            h["cells"] = combined
            h["garden"] = True
        else:
            hid = integer(a.get("new_house_id"), 1, 19, "new_house_id")
            require(hid in s["new_house_ids"], "Not a buildable house number")
            require(
                not any(h["id"] == hid for h in b["houses"]), "House number unavailable"
            )
            area = geo.rectangle(x, y, 3 if rotate else 2, 2 if rotate else 3)
            geo.empty(s, area)
            require(
                any(geo.road(b, q) for v in area for q in geo.neighbors(v)),
                "House must border a road",
            )
            b["houses"].append(
                dict(id=hid, cells=area, garden=True, printed=False, demand=[])
            )
        for x, y in area:
            b["cells"][y][x] = "house"

    def pay(self, s, pid, amount):
        p = s["players"][pid]
        p["cash"] += amount
        s["bank"] -= amount
        if not s["introductory"] and s["bank_breaks"] == 0 and s["bank"] <= 0:
            s["bank_breaks"] = 1
            if "reserve_prices" in s["modules"]:
                s["bank"] += 200 * len(s["players"])
                counts = Counter(s["reserves"].values())
                s["base_price"] = max(counts, key=lambda price: (counts[price], {10:0, 5:1, 20:2}[price]))
            else:
                s["bank"] += sum(s["reserves"].values())
                counts = Counter(v // 100 + 1 for v in s["reserves"].values())
                s["next_ceo_slots"] = max(counts, key=lambda x: (counts[x], x))
            self.emit(s, "bank_broken", number=1)
        final_break = 1 if s["introductory"] else 2
        if s["bank"] <= 0 and s["bank_breaks"] < final_break:
            s["bank_breaks"] = final_break
            self.emit(s, "bank_broken", number=final_break)
        if p["cash"] >= 20:
            self.grant(s, pid, "first_twenty")

    def dinner(self, s, resume=False):
        s["phase"] = "dinner"
        if resume:
            ctx=s.pop('dinner_context')
            houses=s['board']['houses']+([dict(s['rural'],cells=[v for ramp in s['offramps'] for v in ramp['cells']])] if 'rural_marketeers' in s['modules'] else [])
            incomes=ctx['incomes'];price_adjustments=ctx['price_adjustments']
            waitresses=ctx['waitresses'];cfo=ctx['cfo'];dist=ctx['dist']
            # JSON object keys normalize numeric house IDs to strings.
            insolvent=set(ctx['insolvent']);ketchup_awards=set(ctx['ketchup_awards'])
            pizza_counts=ctx['pizza_counts']
        else:
            houses = s["board"]["houses"] + ([dict(s["rural"], cells=[v for ramp in s["offramps"] for v in ramp["cells"]])] if "rural_marketeers" in s["modules"] else [])
            incomes = {pid: 0 for pid in self.living(s)}
            prices = {}
            price_adjustments = {}
            waitresses = {}
            cfo = {}
            dist = {}
            for pid in self.living(s):
                p = s["players"][pid]
                active = self.active(p)
                price_adjustments[pid] = (
                    sum(CARDS[e["kind"]]["price"] for e in active)
                    - int("first_lower_price" in p["milestones"])
                )
                waitresses[pid] = sum(self.work_multiplier(p, e) for e in active if e["kind"] == "waitress")
                cfo[pid] = "first_hundred" in p["milestones"] or any(
                    e["kind"] == "cfo" for e in active
                )
                dist[pid] = {
                    str(h["id"]): geo.distance(s["board"], h["cells"], geo.entrances(s, pid, coffee=False), s["roadworks"])
                    for h in houses
                }
            insolvent = set()
            ketchup_awards = set()
            pizza_counts={}
        for h in sorted(houses, key=lambda h: h.get("order", h["id"])):
            # A reserve vote may change the base price after the previous house.
            prices = {pid: s["base_price"] + adjustment
                      for pid, adjustment in price_adjustments.items()}
            need = Counter(h["demand"])
            if not need:
                continue
            meals = {}
            for candidate in self.living(s):
                inventory = s["players"][candidate]["inventory"]
                if dist[candidate][str(h["id"])] >= 999:
                    continue
                options = []
                total = sum(need.values())
                if h["garden"] and "sushi" in s["modules"] and inventory["sushi"] >= total:
                    options.append((0, Counter(sushi=total)))
                if all(inventory[k] >= v for k,v in need.items()):
                    options.append((1, need.copy()))
                if "noodles" in s["modules"] and inventory["noodles"] >= total:
                    options.append((2, Counter(noodles=total)))
                if not options:
                    continue
                rank, meal = min(options, key=lambda item: item[0])
                has_kimchi = "kimchi" in s["modules"] and inventory["kimchi"] > 0
                if has_kimchi:
                    meal["kimchi"] = 1
                meals[candidate] = (rank + (0 if has_kimchi else 3), meal)
            candidates = list(meals)
            if not candidates:
                continue
            pid = min(
                candidates,
                key=lambda pid: (
                    meals[pid][0],
                    prices[pid] + dist[pid][str(h["id"])] - int("ketchup" in s["players"][pid]["milestones"]) - 2*int("new_first_marketeer_used" in s["players"][pid]["milestones"]),
                    self.movie_rank(s["players"][pid]),
                    -waitresses[pid],
                    s["order"].index(pid),
                ),
            )
            p = s["players"][pid]
            need = meals[pid][1]
            if "ketchup" in s["modules"]:
                ketchup_awards.update(owner for owner in h.get("demand_sources", []) if owner and owner != pid)
            if 'coffee' in s['modules']:
                for location in coffee.stops(self,s,h,pid):
                    owner=location['player'];seller=s['players'][owner]
                    amount=(s['base_price']+price_adjustments[owner])*exmap.multiplier(s,h)
                    seller['inventory']['coffee']-=1
                    incomes[owner]+=amount
                    self.pay(s,owner,amount)
                    self.grant(s,owner,'first_coffee_sold')
                    self.emit(s,'coffee_sold',house=h['id'],player=owner,location=location['id'],income=amount)
                # Coffee sales can break the bank before the meal is paid for.
                prices={owner:s['base_price']+adjustment for owner,adjustment in price_adjustments.items()}
            first_pizza=False
            for product in need:
                fresh=self.grant(s,pid,'new_first_'+product+'_sold')
                if product=='pizza' and fresh:pizza_counts[pid]=0
            income = 10 * sum(e["kind"] == "fry_chef" for e in self.active(p))
            for product, count in need.items():
                bonus = 5 * (product in BASE_PRODUCTS and
                    "first_"
                    + (product if product in ("burger", "pizza") else "drink")
                    + "_marketed"
                    in p["milestones"]
                )
                income += count * (prices[pid] * exmap.multiplier(s, h) + bonus)
                p["inventory"][product] -= count
            h["demand"] = []
            h["demand_sources"] = []
            if h.get("rural"):
                s["rural"]["demand"] = []
                s["rural"]["demand_sources"] = []
            incomes[pid] += income
            self.pay(s, pid, income)
            if p["cash"] < 0:
                insolvent.add(pid)
            self.emit(
                s,
                "house_served",
                house=h["id"],
                player=pid,
                products=dict(need),
                income=income,
            )
            if 'pizza' in need and pid in pizza_counts and pizza_counts[pid]<3 and not h.get('rural'):
                pizza_counts[pid]+=1
                s['bonus']=dict(kind='radio',player=pid,house=deepcopy(h))
                if self.bonus_options(s):
                    s['dinner_context']=dict(houses=houses,incomes=incomes,price_adjustments=price_adjustments,
                        waitresses=waitresses,cfo=cfo,dist=dist,insolvent=sorted(insolvent),
                        ketchup_awards=sorted(ketchup_awards),pizza_counts=pizza_counts)
                    s['phase']='bonus';s['queue']=[pid]
                    return
                s.pop('bonus')
        for pid in self.living(s):
            p = s["players"][pid]
            if waitresses[pid]:self.grant(s,pid,'new_first_waitress_used')
            tips = waitresses[pid] * (5 if "first_waitress" in p["milestones"] else 3)
            incomes[pid] += tips
            self.pay(s, pid, tips)
        for pid in self.living(s):
            if cfo[pid]:
                self.pay(s, pid, (incomes[pid] + 1) // 2)
            if s["players"][pid]["cash"] < 0:
                insolvent.add(pid)
            if s["players"][pid]["cash"] >= 100:
                self.grant(s, pid, "first_hundred")
        for pid in sorted(ketchup_awards):
            self.grant(s, pid, "ketchup")
        for pid in sorted(insolvent):
            p = s["players"][pid]
            p["eliminated"] = True
            for e in p["employees"]:
                if e["kind"] != "ceo":
                    s["stock"][e["kind"]] += 1
            p["employees"] = []
            p["active"] = []
            self.emit(s, "chain_bankrupt", player=pid)
        if (
            s["bank_breaks"] >= (1 if s["introductory"] else 2)
            or len(self.living(s)) <= 1
        ):
            s["finished"] = True
            s["phase"] = "finished"
            candidates = self.living(s)
            s["winner"] = (
                max(
                    candidates,
                    key=lambda p: (s["players"][p]["cash"], -s["order"].index(p)),
                )
                if candidates
                else None
            )
            self.emit(s, "game_finished", winner=s["winner"])
            return
        s["phase"] = "cleanup" if s["introductory"] else "payday"
        s["pending"] = {}
        if s["introductory"]:
            self.marketing(s)

    def salary(self, p, employees=None):
        employees = p["employees"] if employees is None else employees
        count = sum(self.salary_required(p, e) for e in employees)
        return max(
            0, (3 if "new_first_waitress_used" in p["milestones"] else 5) * count - p["hire_discount"] - 15 * ("first_train" in p["milestones"])
        )

    def payday(self, s, pid, a):
        p = s["players"][pid]
        fire = a.get("fire", [])
        require(
            isinstance(fire, list)
            and all(isinstance(e, str) for e in fire)
            and len(set(fire)) == len(fire),
            "fire must contain distinct employee IDs",
        )
        em = {e["id"]: e for e in p["employees"]}
        require(
            all(e in em and em[e]["kind"] != "ceo" for e in fire),
            "Cannot fire CEO or unknown employee",
        )
        # Process nonbusy cards first; busy cards can be fired only when salary
        # cannot be met and all other salaried employees have been dismissed.
        remaining = [
            e for e in p["employees"] if not (e["id"] in fire and not e["busy"])
        ]
        for eid in fire:
            e = em[eid]
            if e["busy"]:
                require(
                    self.salary(p, remaining) > p["cash"]
                    and "new_first_trainer_used" not in p["milestones"]
                    and not ("new_first_beer_sold" in p["milestones"] and self.salary(p,remaining) <= p["cash"] + sum(v for k,v in p["inventory"].items() if k!="coffee")*(3 if "new_first_waitress_used" in p["milestones"] else 5))
                    and not any(
                        self.salary_required(p,v) and not v["busy"] for v in remaining
                    ),
                    "Busy marketer may only be fired as an unavoidable last resort",
                )
                remaining.remove(e)
        require(
            not (
                "first_hundred" in p["milestones"]
                and any(e["kind"] == "cfo" for e in remaining)
            ),
            "You must fire CFO after first_hundred",
        )
        wage = self.salary(p, remaining)
        food=a.get('food',{})
        require(not food or 'new_first_beer_sold' in p['milestones'], 'Food wages require first beer sold')
        for product,count in food.items():integer(count,0,p['inventory'][product],product)
        tokens=sum(food.values());unit=3 if 'new_first_waitress_used' in p['milestones'] else 5
        require(tokens <= (wage+unit-1)//unit, 'Too many tokens for the remaining salaries')
        wage=max(0,wage-tokens*unit)
        if 'new_first_trainer_used' in p['milestones'] and wage>p['cash']:
            remaining_food=sum(v for k,v in p['inventory'].items() if k!='coffee')-tokens
            require('new_first_beer_sold' not in p['milestones'] or not remaining_food, 'Use available food before leaving salaries unpaid')
            unpaid=wage-p['cash'];wage=max(0,p['cash'])
            self.emit(s,'salaries_unpaid',player=pid,amount=unpaid)
        require(wage <= p['cash'], 'Cannot afford salaries; fire more employees or pay with food')
        for product,count in food.items():p['inventory'][product]-=count
        for eid in fire:
            if not em[eid].get("box_copy"):s["stock"][em[eid]["kind"]] += 1
        p["employees"] = remaining
        p["active"] = [eid for eid in p["active"] if eid not in fire]
        p["cash"] -= wage
        s["bank"] += wage
        if wage >= 20:
            self.grant(s, pid, "first_pay_twenty")
        self.emit(s, "salaries_paid", player=pid, amount=wage, fired=fire, food=food)

    def marketing(self, s):
        campaigns = sorted(s["campaigns"], key=lambda c: int(c["id"]))
        phases = 1 + sum(e["kind"] == "mass_marketeer" for pid in self.living(s) for e in self.active(s["players"][pid]))
        for _ in range(phases):
            for c in campaigns:
                qty = 2 if c["kind"] == "radio" and "first_radio" in s["players"][c["player"]]["milestones"] else 1
                for product in c.get('products',[c['product']]):
                    targets = [s["rural"]] if c["kind"] == "giant_billboard" else s["board"]["houses"]
                    for h in targets:
                        reached = True if c["kind"] == "giant_billboard" else h["garden"] if c["kind"] == "guide" else geo.reached(s["board"], c, h)
                        if not reached:
                            continue
                        count = qty * (2 if h.get("apartment") or h.get("rural") else 1)
                        added = count if h.get("apartment") or h.get("rural") else max(0, min(count, (5 if h["garden"] else 3) - len(h["demand"])))
                        h.setdefault("demand_sources", [None] * len(h["demand"]))
                        h["demand"] += [product] * added
                        h["demand_sources"] += [c["player"] if c.get("employee") else None] * added
                        if c.get('employee') and 'new_first_marketeer_used' in s['players'][c['player']]['milestones']:
                            self.pay(s,c['player'],5*added)
        ended = []
        for c in campaigns:
            if not c["eternal"]:
                c["remaining"] -= 1
                if not c["remaining"]:
                    ended.append(c)
        for c in ended:
            s["campaigns"].remove(c)
        for pid in self.living(s):
            for e in s["players"][pid]["employees"]:
                linked = [c["id"] for c in s["campaigns"] if c.get("employee") == e["id"] and c["player"] == pid]
                if e["busy"]:
                    e["busy"] = linked[0] if linked else None
        self.emit(s, "marketing_resolved", expired=[c["id"] for c in ended], phases=phases)

    def cleanup(self, s, pid, a):
        p = s["players"][pid]
        keep = a.get("keep", {})
        require(
            isinstance(keep, dict) and set(keep) <= set(PRODUCTS),
            "Invalid freezer inventory",
        )
        for k, v in keep.items():
            integer(v, 0, p["inventory"][k], k)
        require(not keep.get("coffee", 0), "Coffee cannot be stored")
        require(not keep.get("kimchi", 0) or sum(v for k,v in keep.items() if k != "kimchi") == 0,
                "Kimchi must be stored separately from all other food and drink")
        limit = ms.freezer(p)
        require(
            sum(keep.values()) <= limit,
            "Freezer capacity exceeded (new freezers work next round)",
        )
        if sum(p["inventory"].values()) > sum(keep.values()):
            self.grant(s, pid, "first_discard")
        p["inventory"] = {k: keep.get(k, 0) for k in PRODUCTS}
        p["inventory"]["kimchi"] += sum(e["kind"] == "kimchi_master" for e in self.active(p))

    def new_round(self, s):
        s["roadworks"] = []
        for row in s["board"]["cells"]:
            for x, cell in enumerate(row):
                if cell == "construction": row[x] = "road"
        if 'new_milestones' in s['modules'] and s['round']==2:
            for m in ('new_first_marketeer_used','new_first_trainer_used','new_first_recruiting_girl_used'):
                if m not in s['closed_milestones']:s['closed_milestones'].append(m)
        if "hard_choices" in s["modules"]:
            expired = (["first_burger_marketed", "first_pizza_marketed", "first_drink_marketed", "first_train"]
                       if s["round"] == 2 else ["first_hire_three"] if s["round"] == 3 else [])
            for milestone in expired:
                if milestone not in s["closed_milestones"]:
                    s["closed_milestones"].append(milestone)
        for pid in self.living(s):
            p = s["players"][pid]
            p["active"] = [pid + ":ceo"]
            p["structure"] = {}
            for r in p["restaurants"]:
                r["open"] = True
        s["closed_milestones"] += [
            m for m in s["claimed"] if m not in s["closed_milestones"]
        ]
        s["claimed"] = []
        s["round"] += 1
        s["ceo_slots"] = s["next_ceo_slots"]
        s["pending"] = {}
        s["phase"] = "restructure"

    def actions(self, s, pid):
        from .actions import available

        return available(self, s, pid)
