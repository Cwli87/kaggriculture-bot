from kaggle_environments import make

env = make("kaggriculture", configuration={"episodeSteps": 720})
result = env.run(["main.py", "starter"])   # your bot vs the built-in starter bot

# text render of the final board
print(env.render(mode="ansi"))

print("\n=== FINAL SCORES ===")
for i, s in enumerate(result[-1]):
    print(f"Player {i}: money=${s['reward']:.0f}  status={s['status']}")

# save an interactive HTML replay you can open in a browser
with open("replay.html", "w", encoding="utf-8") as f:
    f.write(env.render(mode="html"))
print("\nWrote replay.html — open it in a browser to watch the match visually.")
