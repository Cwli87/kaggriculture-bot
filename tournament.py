"""
Local tournament runner. Put every bot's file in the same folder (rename
each teammate's file so they don't collide, e.g. main_alex.py, main_sam.py),
list them below, and this plays every bot against every other bot twice
(both play orders) so nobody gets an unfair first-move-style advantage,
then prints a win/loss table.

Usage:
    python tournament.py
"""

from itertools import permutations
from kaggle_environments import make

# Add every bot you want in the tournament here: {"display name": "filename.py"}
BOTS = {
    "mine": "main.py",
    "starter": "starter",   # built-in reference bot
    "random": "random",     # built-in random-action bot
    # "alex": "main_alex.py",
    # "sam": "main_sam.py",
}

EPISODE_STEPS = 720  # 30 in-game days; lower this for quicker smoke tests
SEEDS = [1, 2, 3]     # run each matchup across a few seeds for stability


def play(bot_a_file, bot_b_file, seed):
    env = make("kaggriculture", configuration={"episodeSteps": EPISODE_STEPS, "seed": seed})
    result = env.run([bot_a_file, bot_b_file])
    final = result[-1]
    return final[0]["reward"], final[1]["reward"]


def main():
    names = list(BOTS.keys())
    wins = {n: 0 for n in names}
    totals = {n: 0.0 for n in names}
    games = 0

    for a, b in permutations(names, 2):
        for seed in SEEDS:
            ra, rb = play(BOTS[a], BOTS[b], seed)
            games += 1
            totals[a] += ra
            totals[b] += rb
            winner = a if ra > rb else (b if rb > ra else None)
            if winner:
                wins[winner] += 1
            print(f"[seed {seed}] {a} (${ra:.0f})  vs  {b} (${rb:.0f})"
                  + (f"   -> {winner} wins" if winner else "   -> tie"))

    print("\n=== STANDINGS ===")
    for n in sorted(names, key=lambda x: -wins[x]):
        avg_money = totals[n] / (games * 2 / len(names)) if games else 0
        print(f"{n:12s}  wins={wins[n]:3d}  avg_money=${avg_money:,.0f}")


if __name__ == "__main__":
    main()
