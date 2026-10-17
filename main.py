"""
Kaggriculture demo bot — v2.

Changes from v1 (which won consistently but left value on the table):
  - FIXED BUG: v1 held sellable stock whenever price < base, which let
    fertilizer (and anything else) get stuck unsold for the whole season.
    v2 always sells surplus every turn (minus a small wheat feed-reserve).
    Steep glut-curve items (milk/strawberry/wool/melon) especially punish
    holding, since the opponent's farm is visible and can out-race you to
    the same sale — selling promptly is simply the safer policy here.
  - Crop portfolio expanded from wheat/carrot only to wheat, carrot,
    tomato, strawberry, melon, each gated by a last-plantable-day cutoff
    so seed money never gets spent on a crop that can't mature before the
    season ends (this was one of the report's open questions; the real
    CROPS constants below answer it).
  - Multiple animals: goose -> cow -> sheep, one per shed-adjacent corner,
    unlocked in step with land purchases. All three corners sit next to
    each other around the shed, so a single farmer can tend all three.
  - 2 hands per unlocked quadrant instead of 1 (hiring is cheap; tile
    coverage is the actual constraint per the report's labour analysis),
    with each quadrant's zone split into row-bands so hands sharing a
    quadrant don't just duplicate each other's sweep.
  - Reserved-corner handling so hands don't plant on a tile the farmer is
    about to build a coop/pasture on (this caused an infinite pickup/drop
    loop in v1 for a single corner; v2 avoids it for all three).

Pure function of `obs`, no cross-turn state. Constants mirror the
installed kaggle_environments source (envs/kaggriculture/kaggriculture.py).
"""

# ---- Game constants (mirrors kaggle_environments/envs/kaggriculture) ----

CROPS = {
    "WHEAT":      {"seed": 10, "first_yield_day": 2, "max_yield_day": 4,  "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first_yield_day": 2, "max_yield_day": 3,  "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first_yield_day": 8, "max_yield_day": 8,  "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}

ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP",    "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW":   {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}

MARKET_BASE = {
    "WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250,
    "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100,
}

LAND_ORDER = ["NE", "SW", "SE"]
LAND_PRICES = [1000, 2000, 4000]

# Assumed season length (episodeSteps 720 / turnsPerDay 24 by default).
SEASON_DAYS = 30

# Last day it's still worth planting each crop: non-ongoing crops need to
# reach max_yield_day to pay off; ongoing crops just need first_yield_day
# to get at least one harvest cycle in before the season ends.
def _last_plant_day(crop):
    cd = CROPS[crop]
    horizon = cd["first_yield_day"] if cd["ongoing"] else cd["max_yield_day"]
    return SEASON_DAYS - horizon - 1


LAST_PLANT_DAY = {c: _last_plant_day(c) for c in CROPS}

# Rotation order hands cycle through (weighted toward the cheap staples).
PLANT_ROTATION_ORDER = ["WHEAT", "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]
SEED_BUFFER = {"WHEAT": 6, "CARROT": 3, "TOMATO": 2, "STRAWBERRY": 2, "MELON": 2}

# Acquisition order: (animal, structure) placed on shed corners [NW, NE, SW]
# in that order (NW is free from turn 0; NE/SW require buying that land).
ANIMAL_PLAN = [("GOOSE", "COOP"), ("COW", "PASTURE"), ("SHEEP", "PASTURE")]
ANIMAL_BUY_BUFFER = 300

HANDS_PER_QUADRANT = 2
MAX_HANDS = 8
MARKET_ORDER_CAP = 10
WHEAT_CARRY_TARGET = 8           # wheat the farmer tries to keep on hand for feeding
LAND_BUFFER_BEHIND = 200         # buy land sooner if we're behind on money
LAND_BUFFER_AHEAD = 500          # ...more conservatively if we're ahead
WHEAT_FEED_RESERVE_PER_ANIMAL = 4


# ---------------------------- geometry helpers ----------------------------

def board_size_of(farm):
    return len(farm["tiles"])


def shed_tiles(board_size):
    half = board_size // 2
    # NW, NE, SW, SE corners next to the shed, in that order.
    return [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]


def is_shed_adjacent(pos, board_size):
    return tuple(pos) in set(shed_tiles(board_size))


def quadrant_bounds(quadrant, board_size):
    half = board_size // 2
    x0, x1 = (0, half) if quadrant in ("NW", "SW") else (half, board_size)
    y0, y1 = (0, half) if quadrant in ("NW", "NE") else (half, board_size)
    return x0, x1, y0, y1


def split_zone_rows(zone, k):
    """Split a zone into k horizontal row-bands so multiple hands sharing
    one quadrant sweep different rows instead of duplicating each other."""
    x0, x1, y0, y1 = zone
    rows = y1 - y0
    k = max(1, min(k, rows))
    bands = []
    for i in range(k):
        ry0 = y0 + (rows * i) // k
        ry1 = y0 + (rows * (i + 1)) // k
        bands.append((x0, x1, ry0, max(ry1, ry0 + 1)))
    return bands


def move_toward(pos, target):
    x, y = pos
    tx, ty = target
    if x < tx:
        return "EAST"
    if x > tx:
        return "WEST"
    if y < ty:
        return "SOUTH"
    if y > ty:
        return "NORTH"
    return None  # already there


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def snake_next(pos, zone):
    x0, x1, y0, y1 = zone
    x, y = pos
    row = y - y0
    if row % 2 == 0:  # left -> right
        if x + 1 < x1:
            return (x + 1, y)
        return (x, y + 1) if y + 1 < y1 else (x0, y0)
    else:             # right -> left
        if x - 1 >= x0:
            return (x - 1, y)
        return (x, y + 1) if y + 1 < y1 else (x0, y0)


def in_zone(pos, zone):
    x0, x1, y0, y1 = zone
    x, y = pos
    return x0 <= x < x1 and y0 <= y < y1


# ------------------------------ tile helpers -------------------------------

def is_plant(tile):
    return isinstance(tile, dict) and tile.get("kind") == "PLANT"


def is_animal(tile):
    return isinstance(tile, dict) and "animal" in tile


def is_empty_structure(tile):
    return isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE") and "animal" not in tile


def all_animal_tiles(farm):
    out = []
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if is_animal(tile):
                out.append(((x, y), tile))
    return out


def next_animal_slot(farm, board_size):
    """First ANIMAL_PLAN entry that doesn't have a live animal on its
    corner yet — handles both 'not built yet' and 'built but not placed
    (or escaped)' the same way, in order."""
    corners = shed_tiles(board_size)
    for i, (animal_name, structure_kind) in enumerate(ANIMAL_PLAN):
        corner = corners[i]
        tile = farm["tiles"][corner[1]][corner[0]]
        if is_animal(tile):
            continue
        return i, animal_name, structure_kind, corner
    return None


def reserved_animal_corners(farm, board_size):
    """Shed corners earmarked for a future coop/pasture that isn't built
    yet — hands must not plant on these or they'll block construction."""
    slot = next_animal_slot(farm, board_size)
    if slot is None:
        return set()
    i = slot[0]
    corners = shed_tiles(board_size)
    return {c for c in corners[i:len(ANIMAL_PLAN)] if farm["tiles"][c[1]][c[0]] is None}


def nearest_animal_need(farm, pos):
    """Find the closest animal tile with an outstanding CARE/FEED/HARVEST/
    COLLECT_FERTILIZER need. Returns (target_pos, action) or None."""
    best, best_dist = None, None
    for (x, y), tile in all_animal_tiles(farm):
        need = None
        if not tile["cared_today"]:
            need = "CARE"
        elif not tile["fed_today"]:
            need = "FEED"
        elif tile["yield_units"] > 0:
            need = "HARVEST"
        elif tile.get("fertilizer_available"):
            need = "COLLECT_FERTILIZER"
        if need is None:
            continue
        d = manhattan(pos, (x, y))
        if best is None or d < best_dist:
            best, best_dist = ((x, y), need), d
    return best


def plantable_crops(day):
    return [c for c in PLANT_ROTATION_ORDER if day <= LAST_PLANT_DAY[c]]


# ------------------------------ hand behavior -------------------------------

def hand_action(pos, tile, zone, day, seeds, h_idx, reserved_corners):
    """One farmhand: plant -> water -> harvest -> keep sweeping the zone."""
    if isinstance(tile, dict) and tile.get("kind") == "WEED":
        return ["DIG"]

    if tile is None:
        if pos not in reserved_corners:
            candidates = plantable_crops(day) or ["WHEAT"]
            crop = candidates[(pos[0] + pos[1] + h_idx) % len(candidates)]
            if seeds.get(crop, 0) > 0:
                return ["PLANT", crop]
            # try any other plantable crop we do have seed for
            for c in candidates:
                if seeds.get(c, 0) > 0:
                    return ["PLANT", c]
    elif is_plant(tile):
        crop = tile["crop"]
        cd = CROPS[crop]
        age = day - tile["planted_day"]
        if not tile["watered_today"] and age <= cd["max_yield_day"] + 1:
            return ["WATER"]
        if tile["yield_units"] > 0 and (cd["ongoing"] or age >= cd["max_yield_day"]):
            return ["HARVEST"]

    if not in_zone(pos, zone):
        nxt = (zone[0], zone[2])
    else:
        nxt = snake_next(pos, zone)
    step = move_toward(pos, nxt)
    return [step] if step else ["PASS"]


# ------------------------------ farmer behavior -----------------------------

def farmer_action(farm, private, board_size, day):
    pos = tuple(farm["farmer"])
    tile = farm["tiles"][pos[1]][pos[0]]
    inv = private["inventories"][0]
    shed = private["shed"]
    home = shed_tiles(board_size)[0]

    # Drop anything sellable, but never auto-drop wheat (reserved for
    # feeding) or an animal currently being carried to its structure.
    droppable = sum(n for item, n in inv.items() if item != "WHEAT" and item not in ANIMALS)
    if droppable > 0 and is_shed_adjacent(pos, board_size):
        return ["DROP"]

    # Tend whichever owned animal needs attention next.
    need = nearest_animal_need(farm, pos)
    if need is not None:
        target_pos, action = need
        if pos == target_pos:
            if action == "FEED":
                if inv.get("WHEAT", 0) > 0:
                    return ["FEED"]
                # else fall through to fetch wheat below
            else:
                return [action]
        if action == "FEED" and inv.get("WHEAT", 0) == 0:
            if is_shed_adjacent(pos, board_size):
                if shed.get("WHEAT", 0) > 0:
                    return ["PICKUP", "WHEAT", min(WHEAT_CARRY_TARGET, shed["WHEAT"])]
                # no wheat yet; fall through to expansion/idle logic below
            else:
                step = move_toward(pos, home)
                if step:
                    return [step]
        else:
            step = move_toward(pos, target_pos)
            if step:
                return [step]

    # Grow the animal roster: build next structure -> buy -> pick up -> place.
    slot = next_animal_slot(farm, board_size)
    if slot is not None:
        i, animal_name, structure_kind, corner = slot
        owned_extra = len(farm["unlocked_quadrants"]) - 1
        if owned_extra >= i and day >= 2 and farm["money"] >= ANIMALS[animal_name]["cost"] + ANIMAL_BUY_BUFFER:
            corner_tile = farm["tiles"][corner[1]][corner[0]]
            if corner_tile is None:
                if pos == corner:
                    return [f"BUILD_{structure_kind}"]
                step = move_toward(pos, corner)
                if step:
                    return [step]
            elif is_empty_structure(corner_tile):
                if pos == corner:
                    if inv.get(animal_name, 0) > 0:
                        return ["PLACE", animal_name]
                    if is_shed_adjacent(pos, board_size) and shed.get(animal_name, 0) > 0:
                        return ["PICKUP", animal_name, 1]
                else:
                    step = move_toward(pos, corner)
                    if step:
                        return [step]

    # Nothing urgent: farm the home tile with wheat while waiting to afford
    # the next animal (never plant on a corner still reserved for a coop).
    if is_plant(tile):
        cd = CROPS[tile["crop"]]
        age = day - tile["planted_day"]
        if not tile["watered_today"] and age <= cd["max_yield_day"] + 1:
            return ["WATER"]
        if tile["yield_units"] > 0 and age >= cd["max_yield_day"]:
            return ["HARVEST"]
    elif tile is None and pos == home and (slot is None or slot[0] > 0):
        # home corner's coop is already built/occupied; nothing to farm here
        pass
    elif tile is None and pos == home:
        if private["seeds"].get("WHEAT", 0) > 0:
            return ["PLANT", "WHEAT"]

    if pos != home:
        step = move_toward(pos, home)
        if step:
            return [step]
    return ["PASS"]


# ------------------------------ market policy -------------------------------

def market_orders(farm, private, hour, day, n_target_hands, opponent_money):
    orders = []
    shed = private["shed"]
    seeds = private["seeds"]
    money = farm["money"]

    if hour == 0:
        for _ in range(n_target_hands):
            orders.append(["HIRE"])

    land_buffer = LAND_BUFFER_BEHIND if money < opponent_money else LAND_BUFFER_AHEAD
    n_owned_extra = len(farm["unlocked_quadrants"]) - 1
    if day >= 2 and n_owned_extra < len(LAND_ORDER):
        cost = LAND_PRICES[n_owned_extra]
        if money >= cost + land_buffer:
            orders.append(["BUY_LAND"])

    n_animals = len(all_animal_tiles(farm))
    wheat_reserve = WHEAT_FEED_RESERVE_PER_ANIMAL * max(1, n_animals) if n_animals else 0
    for item in MARKET_BASE:
        have = shed.get(item, 0)
        if item == "WHEAT":
            have -= wheat_reserve
        if have <= 0:
            continue
        orders.append(["SELL", item, have])

    for crop, buf in SEED_BUFFER.items():
        if day > LAST_PLANT_DAY[crop]:
            continue
        need = buf - seeds.get(crop, 0)
        if need > 0 and money >= CROPS[crop]["seed"] * need:
            orders.append(["BUY_SEED", crop, need])

    slot = next_animal_slot(farm, board_size_of(farm))
    if slot is not None:
        i, animal_name, _, _ = slot
        owned_extra = len(farm["unlocked_quadrants"]) - 1
        in_flight = shed.get(animal_name, 0) > 0 or private["inventories"][0].get(animal_name, 0) > 0
        if (owned_extra >= i and day >= 2 and not in_flight
                and money >= ANIMALS[animal_name]["cost"] + ANIMAL_BUY_BUFFER):
            orders.append(["BUY_ANIMAL", animal_name, 1])

    return orders[:MARKET_ORDER_CAP]


# ---------------------------------- agent -----------------------------------

def agent(obs):
    farms = obs.get("farms", [])
    player = obs.get("player", 0)
    if not farms or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    farm = farms[player]
    private = obs.get("private", {}) or {}
    day = obs.get("day", 0)
    hour = obs.get("hour", 0)
    opponent = farms[1 - player] if len(farms) > 1 else None
    opponent_money = opponent["money"] if opponent else farm["money"]

    board_size = board_size_of(farm)
    quadrants = farm["unlocked_quadrants"]
    n_hands_target = min(MAX_HANDS, HANDS_PER_QUADRANT * len(quadrants))

    farmer_op = farmer_action(farm, private, board_size, day)

    # Group hands by quadrant, then split each quadrant into row-bands so
    # hands sharing a quadrant sweep different rows.
    groups = {q: [] for q in quadrants}
    hand_positions = farm["hands"]
    for h_idx in range(len(hand_positions)):
        groups[quadrants[h_idx % len(quadrants)]].append(h_idx)

    zone_for_hand = {}
    for q, idxs in groups.items():
        bands = split_zone_rows(quadrant_bounds(q, board_size), len(idxs))
        for band, h_idx in zip(bands, idxs):
            zone_for_hand[h_idx] = band

    reserved_corners = reserved_animal_corners(farm, board_size)
    seeds = private.get("seeds", {})

    hands_ops = []
    for h_idx, pos in enumerate(hand_positions):
        zone = zone_for_hand.get(h_idx, quadrant_bounds(quadrants[0], board_size))
        pos = tuple(pos)
        tile = farm["tiles"][pos[1]][pos[0]]
        hands_ops.append(hand_action(pos, tile, zone, day, seeds, h_idx, reserved_corners))

    orders = market_orders(farm, private, hour, day, n_hands_target, opponent_money)

    return {"farmer": farmer_op, "hands": hands_ops, "market": orders}
