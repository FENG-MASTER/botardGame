"""Square board geometry, weighted tile distance, marketing reach and routing."""

from collections import deque
import heapq
import random
from boardgame.core import require, integer


def neighbors(p):
    x, y = p
    return [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]


def tile(p):
    return p[0] // 5, p[1] // 5


def rectangle(x, y, w, h):
    return [[a, b] for b in range(y, y + h) for a in range(x, x + w)]


def generated(players, seed):
    """Original development map; never presented as the publisher's 20 tiles."""
    cols, rows = {2: (3, 3), 3: (3, 4), 4: (4, 4), 5: (5, 4)}[players]
    rng = random.Random(seed)
    cells = [["empty"] * (cols * 5) for _ in range(rows * 5)]
    houses = []
    for ty in range(rows):
        for tx in range(cols):
            x, y = tx * 5, ty * 5
            for i in range(5):
                cells[y + 2][x + i] = "road"
                cells[y + i][x + 2] = "road"
            cells[y + 3][x + 3] = rng.choice(["beer", "lemonade", "soda"])
            area = rectangle(x, y, 2, 2)
            for a, b in area:
                cells[b][a] = "house"
            houses.append(
                dict(
                    id=len(houses) + 10,
                    cells=area,
                    garden=False,
                    printed=True,
                    demand=[],
                )
            )
    return dict(width=cols * 5, height=rows * 5, cells=cells, houses=houses)


def validate(board):
    require(isinstance(board, dict), "board must be an object")
    w = integer(board.get("width"), 5, 30, "width")
    h = integer(board.get("height"), 5, 30, "height")
    require(w % 5 == 0 and h % 5 == 0, "Board dimensions must be multiples of five")
    cells = board.get("cells")
    require(
        isinstance(cells, list)
        and len(cells) == h
        and all(isinstance(r, list) and len(r) == w for r in cells),
        "Invalid board grid",
    )
    allowed = {"empty", "road", "bridge", "house", "beer", "lemonade", "soda", "park"}
    require(
        all(isinstance(c, str) and c in allowed for r in cells for c in r),
        "Unknown board cell",
    )
    houses = board.get("houses")
    require(isinstance(houses, list) and len(houses) <= 100, "Invalid houses")
    used = set()
    ids = set()
    for house in houses:
        require(isinstance(house, dict), "Invalid house")
        hid = house.get("id")
        if hid not in ("π", "9¾"):
            integer(hid, 1, 999, "house.id")
        require(hid not in ("π", "9¾") or house.get("apartment") is True,
                "Special house IDs require an apartment")
        house["order"] = {"π": 3.141592653589793, "9¾": 9.75}.get(hid, hid)
        require(hid not in ids, "Duplicate house id")
        ids.add(hid)
        require(type(house.get("garden")) is bool, "garden must be boolean")
        area = house.get("cells")
        require(
            isinstance(area, list) and len(area) in (4, 6, 9),
            "House must contain 4 or 6 cells",
        )
        for p in area:
            q = point(board, p)
            require(
                q not in used and cells[q[1]][q[0]] == "house", "Invalid house cell"
            )
            used.add(q)
        xs = [p[0] for p in area]
        ys = [p[1] for p in area]
        require(
            (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1) == len(area),
            "House must be a rectangle",
        )
        require(
            sorted([max(xs) - min(xs) + 1, max(ys) - min(ys) + 1])
            == ([3, 3] if house.get("apartment") else [2, 3] if house["garden"] else [2, 2]),
            "Invalid house shape",
        )
        house["demand"] = []
        house["printed"] = True
    require(
        used
        == {
            (x, y)
            for y, row in enumerate(cells)
            for x, c in enumerate(row)
            if c == "house"
        },
        "Unregistered house cells",
    )


def point(b, p):
    require(isinstance(p, list) and len(p) == 2, "Coordinates must be [x,y]")
    return (
        integer(p[0], 0, b["width"] - 1, "x"),
        integer(p[1], 0, b["height"] - 1, "y"),
    )


def inside(b, p):
    return 0 <= p[0] < b["width"] and 0 <= p[1] < b["height"]


def road(b, p):
    return inside(b, p) and b["cells"][p[1]][p[0]] in ("road", "bridge")


def occupied(s, exclude=None):
    out = set()
    for p in s["players"].values():
        for r in p["restaurants"] + p.get("coffee_shops", []):
            if r["id"] != exclude:
                out.update(map(tuple, r["cells"]))
    for c in s["campaigns"]:
        out.update(map(tuple, c.get("cells", [])))
    return out


def empty(s, area, exclude=None):
    b = s["board"]
    occ = occupied(s, exclude)
    require(
        all(
            inside(b, p) and b["cells"][p[1]][p[0]] == "empty" and tuple(p) not in occ
            for p in area
        ),
        "Placement must be on empty squares",
    )


def entrances(s, pid, coffee=True):
    p = s["players"][pid]
    drive = any(
        e["kind"] in ("local_manager", "regional_manager")
        for e in p["employees"]
        if e["id"] in p["active"]
    )
    return [
        tuple(a)
        for r in p["restaurants"]
        if r["open"]
        for a in (r["cells"] if drive else [r["entrance"]])
    ] + ([tuple(shop["cells"][0]) for shop in p.get("coffee_shops", [])] if coffee else [])


def distances(b, starts, roadworks=()):
    # Bridge cells carry separate horizontal/vertical lanes. Entering from an
    # adjacent building chooses a lane; roads cannot turn on bridges.
    costs = {}
    barriers = {tuple(p): roadworks.count(p) for p in roadworks}
    heap = []
    for p in starts:
        for q in neighbors(p):
            if road(b, q):
                lane = "h" if q[0] != p[0] else "v"
                node = (q[0], q[1], lane if b["cells"][q[1]][q[0]] == "bridge" else "")
                d = int(tile(p) != tile(q)) + barriers.get(q, 0)
                if d < costs.get(node, 999):
                    costs[node] = d
                    heapq.heappush(heap, (d, node))
    while heap:
        d, node = heapq.heappop(heap)
        if costs[node] != d:
            continue
        x, y, lane = node
        for q in neighbors((x, y)):
            direction = "h" if q[0] != x else "v"
            if not road(b, q) or (lane and lane != direction):
                continue
            nxt = (q[0], q[1], direction if b["cells"][q[1]][q[0]] == "bridge" else "")
            nd = d + int(tile((x, y)) != tile(q)) + barriers.get(q, 0)
            if nd < costs.get(nxt, 999):
                costs[nxt] = nd
                heapq.heappush(heap, (nd, nxt))
    return costs


def distance(b, starts, ends, roadworks=()):
    costs = distances(b, starts, roadworks)
    result = 999
    for p in ends:
        for q in neighbors(p):
            lane = (
                ("h" if q[0] != p[0] else "v")
                if road(b, q) and b["cells"][q[1]][q[0]] == "bridge"
                else ""
            )
            result = min(
                result, costs.get((q[0], q[1], lane), 999) + int(tile(p) != tile(q))
            )
    return result


def reached(b, c, h):
    area = list(map(tuple, c.get("cells", [])))
    house = set(map(tuple, h["cells"]))
    if c["kind"] == "billboard":
        return any(q in house for p in area for q in neighbors(p))
    if c["kind"] == "radio":
        return any(
            max(abs(tile(a)[0] - tile(p)[0]), abs(tile(a)[1] - tile(p)[1])) <= 1
            for a in area
            for p in house
        )
    if c["kind"] == "airplane":
        axis = 1 if c["side"] in ("left", "right") else 0
        return any(c["offset"] <= p[axis] < c["offset"] + c["span"] for p in house)
    seen = set(area)
    queue = deque(area)
    while queue:
        p = queue.popleft()
        if p in house:
            return True
        for q in neighbors(p):
            if inside(b, q) and not road(b, q) and q not in seen:
                seen.add(q)
                queue.append(q)
    return False
