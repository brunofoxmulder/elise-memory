"""Compare deux mesures du banc vectoriel et écrit un tableau markdown."""
import json
import sys

a = json.load(open(sys.argv[1]))
b = json.load(open(sys.argv[2]))
lines = [
    f"dev.3 — Hit@1={a['hit1']}/10, Hit@2={a['hit2']}/10",
    f"dev.4 — Hit@1={b['hit1']}/10, Hit@2={b['hit2']}/10",
    "",
    "| Question | famille | dev.3 | dev.4 |",
    "|---|---|---|---|",
]
for x, y in zip(a["results"], b["results"]):
    lines.append(f"| {x['q']} | {x['family']} | {x['rank']} | {y['rank']} |")

gains, regs = [], []
for x, y in zip(a["results"], b["results"]):
    if x["rank"] == y["rank"]:
        continue
    entry = f"{x['q']} ({x['rank']}→{y['rank']})"
    if (y["rank"] or 99) < (x["rank"] or 99):
        gains.append(entry)
    else:
        regs.append(entry)
lines += ["", f"Gains : {', '.join(gains) or 'aucun'}", f"Régressions : {', '.join(regs) or 'aucune'}"]
print("\n".join(lines))
