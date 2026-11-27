"""Тонкая обёртка над mixgen.py для веб-приложения: тот же алгоритм, что и в CLI."""
import json
import os
import random
from collections import Counter

import mixgen

# Если есть кэшированная обработанная база — грузим её (без тяжёлого препроцессинга),
# иначе считаем из сырой базы.
_PROC = "/home/pyodide/processed.json"
if os.path.exists(_PROC):
    with open(_PROC, encoding="utf-8") as f:
        DB = mixgen.load_processed(f.read())
else:
    DB = mixgen.load_db("/home/pyodide/tobacco_flavors.json")
_brand_count = Counter(i["brand"] for i in DB)
_tag_count = Counter(t for i in DB for t in i["tagset"])


def processed_json():
    """Сериализованная обработанная база — для кэша в браузере."""
    return mixgen.dump_db(DB)


def meta():
    return json.dumps({
        "total": len(DB),
        "brands": [b for b, _ in _brand_count.most_common()],
        "tags": [t for t in mixgen.G if _tag_count.get(t)],
    }, ensure_ascii=False)


def run(opts_json):
    o = json.loads(opts_json)
    rng = random.Random(o.get("seed"))
    db = DB
    brands = o.get("brands") or []
    if brands:
        bl = [b.lower() for b in brands]
        db = [i for i in db if any(b in i["brand"].lower() or b in i["line"].lower() for b in bl)]
    if o.get("strength"):
        db = [i for i in db if i.get("strength") == o["strength"]]
    if len(db) < 4:
        return json.dumps({"error": "Слишком мало вкусов после фильтров — ослабьте условия."}, ensure_ascii=False)

    style = o.get("style")
    bold = True if style == "bold" else (False if style == "classic" else None)
    size = o.get("size") or None
    tag = o.get("tag") or None
    count = max(1, min(int(o.get("count", 5)), 20))

    mixes, seen, attempts = [], set(), 0
    while len(mixes) < count and attempts < count * 10:
        attempts += 1
        m = mixgen.generate_mix(db, rng, size=size, bold=bold, require_tag=tag)
        key = frozenset(it["short"] for it in m["items"])
        if key in seen:
            continue
        seen.add(key)
        mixes.append(m)

    out = []
    for m in mixes:
        groups, notes = mixgen.explain(m)
        out.append({
            "line": mixgen.format_mix(m, brands=True),
            "line_plain": mixgen.format_mix(m, brands=False),
            "bold": m["bold"],
            "score": m["score"],
            "groups": groups,
            "notes": notes,
            "items": [{
                "percent": p,
                "display": it["display"],
                "label": it["label"],
                "flavor": it["flavor"],
                "description": (it.get("description") or "")[:220],
                "strength": it.get("strength") or "",
            } for it, p in zip(m["items"], m["parts"])],
        })
    return json.dumps({"mixes": out, "pool": len(db)}, ensure_ascii=False)
