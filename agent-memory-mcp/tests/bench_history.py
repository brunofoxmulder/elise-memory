"""Compare le classement de dix questions entre deux versions, mêmes réglages.

    python3 bench_history.py <url_mcp> <sortie.json>

Les dix questions et le corpus de départ sont identiques pour les deux versions.
Seuls des appels `recall` sont émis après l'amorçage ; aucun souvenir n'est
supprimé. Le corpus est fictif : il mesure le comportement du code, pas la
qualité de la base réelle (celle-ci exige une sauvegarde de production).
"""
import json
import re
import sys
import time
import urllib.request

QUESTIONS = [
    ("Q1", "À quelle heure le volet du salon se ferme-t-il le soir ?", "salon"),
    ("Q2", "Où partent mes sauvegardes automatiques chaque nuit ?", "sauvegardes"),
    ("Q3", "À partir de quelle luminosité le volet du salon corrige sa position ?", "salon"),
    ("Q4", "Quelles dates de deuil dois-je garder en tête cette année ?", "deuil"),
    ("Q5", "Que dois-je vérifier avant de dire qu'une modification est réellement installée ?", "installation"),
    ("Q6", "À quelle heure le volet de la terrasse se ferme-t-il ?", "terrasse"),
    ("Q7", "Quels volets se ferment le soir, et à quel moment ?", "terrasse"),
    ("Q8", "Quel volet calcule sa position selon le soleil ?", "salon"),
    ("Q9", "Le volet de la terrasse corrige-t-il sa position selon la luminosité ?", "terrasse"),
    ("Q10", "Le volet du salon a-t-il un calcul d'azimut ?", "salon"),
]

CORPUS = [
    ("Volets salon — règles", "Le volet du salon se ferme 45 minutes après le coucher. Le calcul de position du volet du salon utilise azimut, élévation et lux supérieur à 15000, avec une correction de moins dix appliquée aux mêmes conditions.", "semantic"),
    ("Volets terrasse — règles", "Le volet de la terrasse se ferme 45 minutes après le coucher. Le volet de la terrasse ne calcule aucune position selon azimut, élévation ou lux : sa protection est thermique, sous 3 degrés ou au-dessus de 28 degrés.", "semantic"),
    ("Sauvegardes — destinations", "Les sauvegardes automatiques partent vers quatre destinations : local, Google Drive, OneDrive personnel et OneDrive entreprise.", "semantic"),
    ("Dates de deuil", "Le père de Bruno est décédé le 22 septembre 2026 et a été enterré le 1er octobre 2026. Ces deux dates sont à commémorer.", "semantic"),
    ("Règle d'installation", "Ne jamais confondre installation et fonctionnement observé : une installation n'est pas une preuve d'exécution.", "procedural"),
    ("Séance fictive", "Séance de test : amorçage du corpus de référence pour la comparaison des versions.", "episodic"),
]


def call(url, tool, args, ident):
    body = json.dumps({"jsonrpc": "2.0", "id": ident, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(req, timeout=30) as res:
        raw = res.read().decode()
    if raw.lstrip().startswith("data:"):
        raw = "\n".join(l[5:].strip() for l in raw.splitlines() if l.startswith("data:"))
    data = json.loads(raw)
    if "error" in data or data.get("result", {}).get("isError"):
        raise RuntimeError(str(data))
    return data["result"]["content"][0]["text"]


def wait_ready(url):
    for _ in range(60):
        try:
            call(url, "memory", {"action": "stats"}, 1)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("instance MCP indisponible")


def seed(url):
    ids = {}
    for i, (title, content, kind) in enumerate(CORPUS, start=10):
        out = call(url, "memory", {"action": "store", "title": title,
                                   "content": content, "type": kind}, i)
        m = re.search(r"(?m)^- ID:\s*(\S+)", out)
        if m:
            ids[title] = m.group(1)
    return ids


def main(url, dest):
    wait_ready(url)
    seed(url)
    results = []
    for tag, query, family in QUESTIONS:
        text = call(url, "memory", {"action": "recall", "query": query, "limit": 5}, 100)
        rows = []
        for line in text.splitlines():
            m = re.match(r"\s*(\d+)\.\s+\*\*(.+?)\*\*\s*\(relevance:\s*([0-9.]+)\)", line)
            if m:
                rows.append({"rank": int(m.group(1)), "title": m.group(2),
                             "score": float(m.group(3))})
        rank = next((r["rank"] for r in rows if family in r["title"].lower()), None)
        results.append({"q": tag, "family": family, "rank": rank,
                        "score": next((r["score"] for r in rows if family in r["title"].lower()), None),
                        "top": rows[:3]})
        print(f"{tag}: family={family} rank={rank}")
    hit1 = sum(1 for r in results if r["rank"] == 1)
    hit2 = sum(1 for r in results if r["rank"] and r["rank"] <= 2)
    payload = {"url": url, "hit1": hit1, "hit2": hit2, "results": results}
    json.dump(payload, open(dest, "w"), ensure_ascii=False, indent=1)
    print(f"Hit@1={hit1}/10 Hit@2={hit2}/10 -> {dest}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
