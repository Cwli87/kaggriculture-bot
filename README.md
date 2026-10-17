# Kaggriculture Bot

A rule-based agent for the Kaggle **Kaggriculture** competition, a two-player farming simulation played on `kaggle_environments`. Each player runs a farm for a 30-day season (720 steps), and the player with more money at the end wins.

> **Note:** I finished this after the submission deadline, so it was never submitted or ranked on the leaderboard. It's published as a portfolio project. Local results come from `tournament.py` and are not official.

## Approach

The agent in `main.py` is a pure function of the observation (`agent(obs)`) with no state carried between turns. It controls one farmer plus hired hands.

- **Crop portfolio:** wheat, carrot, tomato, strawberry and melon, rotated by a fixed order. Each crop has a last-plantable-day cutoff, so seed money is never spent on a crop that can't mature before the season ends.
- **Selling policy:** surplus is sold every turn, keeping only a small wheat reserve for feeding animals. Holding stock for a better price let items get stuck unsold, and a visible opponent can sell to the same market first.
- **Animals:** goose, then cow, then sheep, each placed on a corner next to the shed and unlocked in step with land purchases, so one farmer can tend all three.
- **Labour:** two hands per unlocked quadrant, each assigned its own row-band so they don't duplicate each other's sweep.
- **Land:** bought in a fixed order (NE, SW, SE). The buffer to keep in cash depends on whether I'm ahead of or behind the opponent.
- **Reserved corners:** hands avoid planting on a tile the farmer is about to build on, which fixed an infinite pickup/drop loop.

The game constants at the top of `main.py` mirror the `kaggriculture` environment in `kaggle_environments`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

| Script | What it does |
| --- | --- |
| `python watch.py` | Plays `main.py` against the built-in `starter` bot, prints the final scores and writes `replay.html`, an interactive replay to open in a browser. |
| `python tournament.py` | Round-robin of every bot in the `BOTS` dict, both play orders, across several seeds. Prints a win/loss table. Add more bots to `BOTS` to compare versions. |

## results
[seed 1] mine ($34119)  vs  starter ($3467)   -> mine wins
[seed 2] mine ($34093)  vs  starter ($3313)   -> mine wins
[seed 3] mine ($31681)  vs  starter ($3581)   -> mine wins
[seed 1] mine ($47781)  vs  random ($0)   -> mine wins
[seed 2] mine ($39047)  vs  random ($0)   -> mine wins
[seed 3] mine ($42299)  vs  random ($0)   -> mine wins
[seed 1] starter ($3467)  vs  mine ($34358)   -> mine wins
[seed 2] starter ($3313)  vs  mine ($34093)   -> mine wins
[seed 3] starter ($3581)  vs  mine ($31681)   -> mine wins
[seed 1] starter ($3547)  vs  random ($290)   -> starter wins
[seed 2] starter ($3660)  vs  random ($0)   -> starter wins
[seed 3] starter ($3506)  vs  random ($600)   -> starter wins
[seed 1] random ($0)  vs  mine ($42957)   -> mine wins
[seed 2] random ($10)  vs  mine ($38688)   -> mine wins
[seed 3] random ($0)  vs  mine ($39079)   -> mine wins
[seed 1] random ($120)  vs  starter ($3421)   -> starter wins
[seed 2] random ($0)  vs  starter ($3639)   -> starter wins
[seed 3] random ($0)  vs  starter ($3524)   -> starter wins

=== STANDINGS ===
mine          wins= 12  avg_money=$37,490
starter       wins=  6  avg_money=$3,502
random        wins=  0  avg_money=$85

Step 719  Day 29  Hour 23
Town shops: ['PIZZA_SHOP', 'BRUNCH_SPOT', 'SMOOTHIE_SHOP', 'PIZZA_SHOP', 'BAKERY', 'BAKERY', 'FARMERS_MARKET', 'PIZZA_SHOP']
Prices: WHEAT=$48, CARROT=$28, TOMATO=$182, STRAWBERRY=$274, MELON=$250, EGG=$67, MILK=$341, WOOL=$222, FERTILIZER=$87
Player 0: $33986  farmer=[4, 4]  hands=8  unlocked=['NW', 'NE', 'SW', 'SE']  shed={'WHEAT': 6, 'CARROT': 0, 'TOMATO': 0,'STRAWBERRY': 0, 'MELON': 0, 'EGG': 0, 'MILK': 0, 'WOOL': 0, 'FERTILIZER': 0, 'GOOSE': 0, 'COW': 0, 'SHEEP': 0}  seeds={'WHEAT': 1, 'CARROT': 3, 'TOMATO': 2, 'STRAWBERRY': 2, 'MELON': 2}
  x x x x . x x x x x
  x . . . . . . . x x
  x . . . . t . . . .
  x . . . . w . . . .
  . . w t G C . x x t
  x . t s S w s . s x
  x . x . . . x x x .
  x x x x x t w x s x
  x . x . x . x . m x
  . . . . . . . . . .
Player 1: $3319  farmer=[4, 4]  hands=0  unlocked=['NW']  shed={'WHEAT': 0, 'CARROT': 0, 'TOMATO': 0, 'STRAWBERRY': 0, 'MELON': 0, 'EGG': 0, 'MILK': 0, 'WOOL': 0, 'FERTILIZER': 0, 'GOOSE': 0, 'COW': 0, 'SHEEP': 0}  seeds={'WHEAT': 0, 'CARROT': 1, 'TOMATO': 0, 'STRAWBERRY': 0, 'MELON': 0}
  . . . x . # # # # #
  . . . . x # # # # #
  . . x . . # # # # #
  . . . . x # # # # #
  . . . . c # # # # #
  # # # # # # # # # #
  # # # # # # # # # #
  # # # # # # # # # #
  # # # # # # # # # #
  # # # # # # # # # #


=== FINAL SCORES ===
Player 0: money=$33986  status=DONE
Player 1: money=$3319  status=DONE

## Files

```
main.py         the agent
watch.py        single match + HTML replay
tournament.py   round-robin evaluation
```

`replay.html` is generated by `watch.py` and is not committed (about 28 MB).

## License
https://www.kaggle.com/competitions/kaggriculture/overview
MIT, see [LICENSE](LICENSE).
