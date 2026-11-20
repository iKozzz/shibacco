#!/usr/bin/env python3
"""
Shibaco — генератор кальянных миксов.

Берёт базу data/tobacco_flavors.json (бренд / линейка / вкус / описание / вкусовые группы)
и собирает случайные, но совместимые миксы из 1–4 вкусов.

Логика:
  1. Количество вкусов: 1 (15%), 2 (40%), 3 (35%), 4 (10%).
  2. Первый вкус — случайный «якорь».
  3. Каждый следующий подбирается по совместимости со ВСЕМИ уже выбранными:
     матрица совместимости вкусовых групп + бонус за классические пары ингредиентов
     (найденные в названии и описании вкуса) − штраф за повторы и конфликты.
  4. Режим «смелый» (≈25% миксов или --bold) — поощряет необычные, но допустимые
     сочетания из разных классов (огурец+дыня, парфюм+цитрус, табак+десерт и т.п.).

Примеры:
  python mixgen.py                     # 10 миксов
  python mixgen.py -n 20 --details     # с брендами, пропорциями и пояснениями
  python mixgen.py --size 3 --bold     # только 3 вкуса, смелые
  python mixgen.py --brand DARKSIDE --brand Bonche
  python mixgen.py --tag цитрус        # в миксе обязательно есть цитрус
  python mixgen.py --strength крепкий --seed 42
"""
import argparse
import json
import math
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "data", "tobacco_flavors.json")

# ---------------------------------------------------------------------------
# Совместимость вкусовых групп: 3 — классика, 2 — хорошо, 1 — смело, 0 — плохо.
# По умолчанию (пары, которых нет в списке) — 0.8.
# ---------------------------------------------------------------------------
G = ["фрукты", "ягоды", "цитрус", "тропики", "десерты", "сладости/конфеты", "напитки",
     "алкоголь", "чай", "холод/мята", "пряности", "травы/хвоя", "цветы", "орехи",
     "табачный/сигарный", "парфюм"]

PAIRS = {
    3: [("ягоды", "цитрус"), ("ягоды", "десерты"), ("тропики", "цитрус"), ("фрукты", "ягоды"),
        ("фрукты", "тропики"), ("цитрус", "напитки"), ("цитрус", "холод/мята"),
        ("ягоды", "холод/мята"), ("пряности", "травы/хвоя"), ("парфюм", "цитрус"),
        ("десерты", "орехи"), ("десерты", "напитки"), ("чай", "цитрус"), ("чай", "ягоды"),
        ("алкоголь", "цитрус"), ("алкоголь", "ягоды"), ("пряности", "десерты"),
        ("табачный/сигарный", "десерты"), ("табачный/сигарный", "орехи"),
        ("табачный/сигарный", "пряности"), ("цветы", "ягоды"), ("цветы", "фрукты"),
        ("сладости/конфеты", "ягоды"), ("сладости/конфеты", "фрукты"), ("напитки", "ягоды"),
        ("тропики", "холод/мята"), ("тропики", "десерты"), ("алкоголь", "тропики")],
    2: [("фрукты", "цитрус"), ("фрукты", "холод/мята"), ("фрукты", "десерты"),
        ("тропики", "напитки"), ("цитрус", "травы/хвоя"), ("цитрус", "пряности"),
        ("ягоды", "травы/хвоя"), ("ягоды", "пряности"), ("чай", "цветы"), ("чай", "пряности"),
        ("чай", "фрукты"), ("чай", "травы/хвоя"), ("парфюм", "цветы"), ("парфюм", "пряности"),
        ("парфюм", "табачный/сигарный"), ("парфюм", "ягоды"), ("алкоголь", "десерты"),
        ("алкоголь", "пряности"), ("алкоголь", "табачный/сигарный"), ("алкоголь", "травы/хвоя"),
        ("орехи", "пряности"), ("орехи", "напитки"), ("цветы", "цитрус"), ("цветы", "травы/хвоя"),
        ("травы/хвоя", "холод/мята"), ("сладости/конфеты", "цитрус"),
        ("сладости/конфеты", "тропики"), ("сладости/конфеты", "напитки"),
        ("сладости/конфеты", "холод/мята"), ("напитки", "холод/мята"), ("напитки", "алкоголь"),
        ("алкоголь", "фрукты"), ("табачный/сигарный", "напитки"), ("цветы", "холод/мята"),
        ("десерты", "сладости/конфеты"), ("напитки", "фрукты"), ("чай", "тропики")],
    1: [("травы/хвоя", "фрукты"), ("пряности", "фрукты"), ("пряности", "тропики"),
        ("орехи", "ягоды"), ("орехи", "фрукты"), ("табачный/сигарный", "ягоды"),
        ("табачный/сигарный", "цитрус"), ("парфюм", "фрукты"), ("парфюм", "тропики"),
        ("цветы", "десерты"), ("цветы", "алкоголь"), ("холод/мята", "десерты"),
        ("чай", "десерты"), ("травы/хвоя", "тропики"), ("травы/хвоя", "алкоголь"),
        ("пряности", "напитки"), ("орехи", "тропики"), ("пряности", "холод/мята"),
        ("парфюм", "алкоголь"), ("табачный/сигарный", "фрукты"), ("цветы", "тропики"),
        ("травы/хвоя", "напитки"), ("чай", "алкоголь"), ("чай", "холод/мята")],
    0: [("орехи", "цитрус"), ("парфюм", "сладости/конфеты"),
        ("табачный/сигарный", "сладости/конфеты"), ("орехи", "холод/мята"),
        ("парфюм", "десерты"), ("орехи", "алкоголь"), ("травы/хвоя", "десерты"),
        ("травы/хвоя", "сладости/конфеты"), ("парфюм", "напитки")],
}
SAME_GROUP = 2.2  # ягода + ягода, цитрус + цитрус — хорошо, но не лучше межклассовой классики
DEFAULT = 0.8

M = {}
for score, pairs in PAIRS.items():
    for a, b in pairs:
        M[(a, b)] = M[(b, a)] = score


def group_compat(a, b):
    if a == b:
        return SAME_GROUP
    return M.get((a, b), DEFAULT)


# ---------------------------------------------------------------------------
# Классические пары ингредиентов (ищутся по корням в названии + описании).
# ---------------------------------------------------------------------------
ING = {
    "лимон": ["лимон", "lemon", "limon", "лемонграсс"], "лайм": ["лайм", "lime"], "апельсин": ["апельсин", "orange"],
    "грейпфрут": ["грейпфрут", "grapefruit"], "мандарин": ["мандарин"], "бергамот": ["бергамот"],
    "юдзу": ["юдзу", "юзу", "yuzu"], "клубника": ["клубни", "strawberr"], "малина": ["малин", "raspberr"],
    "черника": ["черник", "blueberr", "bilberr"], "вишня": ["вишн", "cherry"], "смородина": ["смородин", "currant"],
    "ежевика": ["ежевик", "blackberr"], "клюква": ["клюкв"], "земляника": ["земляник"],
    "облепиха": ["облепих"], "арбуз": ["арбуз", "watermelon"], "дыня": ["дын", "melon"],
    "персик": ["персик", "peach"], "абрикос": ["абрикос"], "яблоко": ["яблок", "apple"], "груша": ["груш", "pear"],
    "виноград": ["виноград", "grape"], "слива": ["слива", "сливы", "сливой", "сливу", "сливов", "чернослив", "plum"], "гранат": ["гранат"], "киви": ["киви", "kiwi"],
    "инжир": ["инжир", "fig"], "манго": ["манго", "mango"], "маракуйя": ["маракуй", "passion"],
    "ананас": ["ананас", "pineapple"], "банан": ["банан", "banana"], "кокос": ["кокос", "coconut"],
    "личи": ["личи", "lychee"], "гуава": ["гуав", "guava"], "фейхоа": ["фейхоа", "feijoa"],
    "мята": ["мят", "mint", "wintergreen"], "газировка": ["газиров", "содов", "soda", "шипучк"], "конфеты": ["конфет", "candy", "драже", "леденц", "тик-так"], "папайя": ["папай", "papaya"], "барбарис": ["барбарис", "barberry"], "крыжовник": ["крыжовн", "gooseberry"], "холодок": ["холод", "арктик", "ice", "лёд", "ледян"], "эвкалипт": ["эвкалипт"],
    "базилик": ["базилик", "basil"], "огурец": ["огур", "cucumber"], "хвоя": ["хвой", "хвоя", "пихт", "сосн", "кедр", "pine"],
    "розмарин": ["розмарин"], "чабрец": ["чабрец"], "лаванда": ["лаванд", "lavender"], "роза": ["роза", "розы", "розой", "rose"],
    "жасмин": ["жасмин", "jasmine"], "бузина": ["бузин"], "корица": ["кориц", "cinnamon"], "кардамон": ["кардамон"],
    "имбирь": ["имбир", "ginger"], "гвоздика": ["гвоздик"], "перец": ["перец", "перц", "pepper"], "чили": ["чили", "chili"],
    "анис": ["анис", "бадьян"], "ваниль": ["ванил", "vanil"], "карамель": ["карамел", "caramel"],
    "шоколад": ["шоколад", "chocolate", "какао", "brownie", "брауни"], "сливки": ["сливк", "сливочн", "cream", "крем"],
    "сливочное масло": ["сливочное масло"], "мёд": ["мёд", "мед", "honey"], "йогурт": ["йогурт"],
    "печенье": ["печень", "cookie", "вафл"], "чизкейк": ["чизкейк", "cheesecake"], "пломбир": ["пломбир", "мороже"],
    "кофе": ["кофе", "coffee", "капучино", "латте"], "кола": ["кола", "cola", "пепси"], "лимонад": ["лимонад", "lemonade"],
    "тоник": ["тоник"], "энергетик": ["энергетик", "energy"], "чай": ["чай", "tea", "улун", "матча"],
    "ром": ["ром ", "ромов", "rum"], "виски": ["виски", "whisk"], "джин": ["джин", "gin "], "вино": ["вино", "вина", "wine"],
    "шампанское": ["шампан", "просекко", "prosecco"], "мохито": ["мохито", "mojito"], "коньяк": ["коньяк", "cognac", "бренди"],
    "орех": ["орех", "nut", "фундук", "миндал"], "арахис": ["арахис", "peanut"], "фисташка": ["фисташ", "pistach"],
    "сигара": ["сигар", "cigar", "хабано"], "парфюм": ["парфюм", "perfume", "parfum", "мускус"],
    "жвачка": ["жвачк", "gum", "баблгам"], "мармелад": ["мармелад", "желе", "jelly"],
}
CLASSIC = [
    ("лимон", "кола"), ("кола", "карамель"), ("кола", "вишня"), ("кола", "ваниль"), ("лайм", "мята"),
    ("лайм", "малина"), ("клубника", "банан"), ("клубника", "сливки"), ("клубника", "шампанское"),
    ("арбуз", "мята"), ("арбуз", "дыня"), ("дыня", "огурец"), ("огурец", "лайм"), ("огурец", "джин"),
    ("манго", "маракуйя"), ("маракуйя", "клюква"), ("маракуйя", "мята"), ("ананас", "кокос"),
    ("ананас", "ром"), ("кокос", "шоколад"), ("банан", "шоколад"), ("банан", "карамель"),
    ("вишня", "шоколад"), ("малина", "шоколад"), ("черника", "лимон"), ("черника", "сливки"),
    ("смородина", "мята"), ("смородина", "хвоя"), ("клюква", "мята"), ("клюква", "хвоя"),
    ("грейпфрут", "малина"), ("грейпфрут", "розмарин"), ("грейпфрут", "тоник"), ("апельсин", "шоколад"),
    ("апельсин", "корица"), ("апельсин", "гвоздика"), ("яблоко", "корица"), ("груша", "корица"),
    ("груша", "сливки"), ("персик", "чай"), ("персик", "маракуйя"), ("персик", "ваниль"),
    ("абрикос", "ваниль"), ("слива", "корица"), ("инжир", "мёд"), ("мёд", "корица"),
    ("сливочное масло", "корица"), ("сливочное масло", "карамель"), ("карамель", "арахис"),
    ("карамель", "кофе"), ("кофе", "ваниль"), ("кофе", "орех"), ("ваниль", "сигара"),
    ("коньяк", "сигара"), ("виски", "сигара"), ("кофе", "сигара"), ("бергамот", "чай"),
    ("лаванда", "черника"), ("лаванда", "лимон"), ("роза", "личи"), ("роза", "малина"),
    ("жасмин", "груша"), ("жасмин", "чай"), ("бузина", "лимон"), ("базилик", "клубника"),
    ("базилик", "лимон"), ("имбирь", "лимон"), ("имбирь", "мёд"), ("перец", "грейпфрут"),
    ("чили", "манго"), ("чили", "шоколад"), ("кардамон", "кофе"), ("парфюм", "бергамот"),
    ("парфюм", "грейпфрут"), ("парфюм", "лимон"), ("юдзу", "мёд"), ("фейхоа", "киви"),
    ("киви", "клубника"), ("гуава", "лайм"), ("личи", "малина"), ("облепиха", "мёд"),
    ("облепиха", "апельсин"), ("эвкалипт", "ананас"), ("мохито", "малина"), ("виноград", "мята"),
    ("гранат", "лимон"), ("энергетик", "клюква"), ("лимонад", "клубника"), ("йогурт", "персик"),
    ("чизкейк", "черника"), ("печенье", "молоко"), ("пломбир", "вишня"), ("жвачка", "арбуз"),
    ("мармелад", "кола"),
]
CLASSIC_SET = {frozenset(p) for p in CLASSIC}

# Явные конфликты ингредиентов (штраф)
CLASH = [("сигара", "жвачка"), ("парфюм", "жвачка"), ("кола", "огурец"), ("йогурт", "лимон"),
         ("сливки", "грейпфрут"), ("сливки", "лайм"), ("энергетик", "сигара"), ("мармелад", "сигара")]
CLASH_SET = {frozenset(p) for p in CLASH}


def find_ingredients_ordered(text):
    """Ингредиенты в порядке появления в тексте."""
    t = " " + text.lower() + " "
    found = {}
    for ing, stems in ING.items():
        pos = None
        for s in stems:
            m = re.search(r"(?<![а-яёa-z])" + re.escape(s), t)
            if m and (pos is None or m.start() < pos):
                pos = m.start()
        if pos is not None:
            found[ing] = pos
    # «сливочное масло» поглощает «сливки», «холодок» не дублирует «мята»
    if "сливочное масло" in found:
        found.pop("сливки", None)
    if "виноград" in found and not re.search(r"(?<![а-яё])вин(о|а|ом|ное|ный|ная)(?![а-яё])|wine", t):
        found.pop("вино", None)  # «виноград» — не вино
    return [k for k, _ in sorted(found.items(), key=lambda kv: kv[1])]


def find_ingredients(text):
    return set(find_ingredients_ordered(text))


# ---------------------------------------------------------------------------
# Подготовка базы
# ---------------------------------------------------------------------------
def short_name(flavor):
    """Короткое человеческое название для вывода: 'Лимонный пирог (Lemon Pie)' -> 'лимонный пирог'."""
    s = flavor.strip()
    m = re.match(r"^(.*?)\s*\((.*?)\)\s*(.*)$", s)
    if m:
        out, inner, tail = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        cyr = lambda x: bool(re.search(r"[а-яё]", x, re.I))
        out = out.strip(" —-")
        if find_ingredients(inner) and not find_ingredients(out):
            s = inner  # «ТОКИО (Клубничная матча)» -> «клубничная матча»
        elif out and cyr(out):
            s = (out + " " + tail).strip()
        elif cyr(inner) and not cyr(out):
            s = inner
        elif not out:
            s = inner
    s = re.sub(r"^[^0-9a-zа-яё]+", "", s, flags=re.I)
    s = re.sub(r"\s+—\s+", "-", s).strip(" —-")
    s = re.sub(r"\s+", " ", s).strip(" ,.-")
    return s.lower() if re.search(r"[а-яё]", s, re.I) else s


# Слова-уточнения, которые не делают вкус составным: «спелая клубника», «ледяной арбуз», «кислый лайм»
MODIFIERS = r"""спел сочн сладк кисл кисло лесн садов дик красн зел[её]н ч[её]рн бел ж[её]лт розов ледян холодн
свеж л[её]гк натурал классич медов молод домашн нежн ярк тёмн темн спелого спелой настоящ сицилийск
сок сочн цедр мякот без косточк
wild ripe sour sweet ice icy fresh green red black white yellow yelow golden juicy pink classic real bitter good
bomb shock juice garden burley terror cigarro aroma fruit dark light afzal brume adalya overdose sapphire"""
MODIFIER_RE = re.compile(r"^(" + "|".join(MODIFIERS.split()) + r")")
# Ингредиенты, которые сами по себе уже микс (коктейли, сборные блюда)
COMPOSITE_INGS = {"мохито"}
COMPOSITE_WORDS = re.compile(r"(коктейл|пунш|микс|mix|купаж|ассорти|смузи|шейк|shake|сангри|глинтвейн|пина|колад|"
                             r"мультифрукт|тутти|фрутти|сад|лето|летн|зимн|тропическ|экзотик|фруктов|ягодн|цитрусов)")
STEMS = sorted({st for sts in ING.values() for st in sts}, key=len, reverse=True)


def stem_match(word, stem):
    """Слово — форма ингредиента: «клубничный» ← «клубни», но «ромашка» ≠ «ром»."""
    if not word.startswith(stem):
        return word == stem
    tail = len(word) - len(stem)
    return len(stem) >= 5 or tail <= (4 if len(stem) == 4 else 3)


def is_simple_flavor(flavor, short, name_ings, desc):
    """Простой (моно) вкус: в названии один ингредиент + допустимые уточнения, без «концептуальных» слов,
    и описание не добавляет новых главных ингредиентов."""
    main = [i for i in name_ings if i != "холодок"]
    if len(main) != 1 or main[0] in COMPOSITE_INGS:
        return False
    text = short.lower()
    if COMPOSITE_WORDS.search(text):
        return False
    for w in re.findall(r"[a-zа-яё]+", text):
        if len(w) <= 2 or MODIFIER_RE.match(w):
            continue
        if any(stem_match(w, st.strip()) for st in STEMS if len(st.strip()) >= 3):
            continue
        return False  # лишнее слово: кодовое/концептуальное название («вишнёвый сад», «мохито йота»)
    # описание-состав (короткое, без советов «с чем миксуется») не должно добавлять 2+ новых ингредиента
    d = desc or ""
    if len(d) < 350 and not re.search(r"миксу|сочета|комбинир", d.lower()):
        extra = [x for x in find_ingredients_ordered(d) if x not in name_ings
                 and x not in ("холодок", "сигара", "сливки", "мёд", "ваниль", "карамель")]
        if len(extra) >= 2:
            return False
    return True


# Линейки, где каждый вкус — уже готовый авторский микс
MIX_LINES = re.compile(r"(shot|шот|гид|hit by blackburn|арктик микс|arctic|matchline|bartender|xperience|"
                       r"brilliant|aroma line|limited|perfume|парфюм)", re.I)


def count_components(r, short, name_ings, desc_ings):
    """Сколько вкусовых компонентов во вкусе: ингредиенты + «лишние» слова названия."""
    main = set(name_ings or [i for i in desc_ings if i != "сигара"][:3]) - {"холодок"}
    n = len(main)
    extra_words = 0
    for w in re.findall(r"[a-zа-яё]+", short.lower()):
        if len(w) <= 2 or MODIFIER_RE.match(w) or any(stem_match(w, st.strip()) for st in STEMS if len(st.strip()) >= 3):
            continue
        extra_words += 1
    if extra_words and n:
        n += 1
    if MIX_LINES.search(r.get("line", "")):
        n = max(n, 3)
    return n


def display_name(short, name_ings, desc_ings, brand):
    """Название для строки микса: понятное по вкусу, без кодов и длинных перечислений."""
    has_cyr = bool(re.search(r"[а-яё]", short, re.I))
    # «с ароматом персика» -> «персик», «садовой клубники» -> «клубника»
    if len(name_ings) == 1 and len(short.split()) <= 2 and name_ings[0] not in short \
            and re.search(r"(ы|а|и|я|ого|ей|ой)$", short):
        return name_ings[0]
    if name_ings:
        if not has_cyr:
            return " ".join(name_ings[:3])
        if len(short) > 30 or short.count(",") >= 2:
            head = re.split(r"[,(]", short)[0].strip()
            head = re.sub(r"\s+(с|и|в|на|со)$", "", head)
            for ing in name_ings:  # обрезаем перед первым ингредиентом, если перед ним «имя»
                m = re.search(r"(?<![а-яёa-z])" + re.escape(ing[:4]), head)
                if m and m.start() > 3:
                    head = re.sub(r"\s+(с|и|в|на|со)$", "", head[:m.start()].strip())
                    break
            ings = ", ".join(name_ings[:4])
            return f"{head} ({ings})" if head and head not in ings else ings
        return short
    extra = [i for i in desc_ings if i not in ("холодок", "сигара")][:3]
    if extra:
        return f"{short} ({', '.join(extra)})"
    return f"{short} [{brand}]"


HG = str.maketrans("аеорсухкмтвнy", "aeopcyxkmtbhy")


def brand_label(brand, line):
    """Бренд + линейка, если линейка что-то уточняет: «DARKSIDE SHOT», «Sebero Арктик Микс», «ХУЛИГАН ПОП»."""
    b, l = brand.strip(), line.strip().replace("Хyлиган", "Хулиган").replace("BONSHE", "BONCHE")
    bn, ln = b.lower().translate(HG), l.lower().translate(HG)
    if ln == bn or not l:
        return b
    if ln.startswith(bn[:4]):
        return l
    return f"{b} {l}"


def load_db(path=DB_PATH):
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    items = []
    for r in rows:
        if r.get("type") in ("капсула", "сигара") or "hookah cigar" in r.get("line", "").lower():
            continue
        tags = [t for t in r.get("tags", "").split(", ") if t]
        name_tags = set(tags)
        text = r["flavor"] + " " + r.get("description", "")
        name_ings = find_ingredients_ordered(r["flavor"])
        desc_ings = find_ingredients_ordered(r.get("description", ""))
        short = short_name(r["flavor"])
        items.append({
            **r,
            "tagset": name_tags,
            "ings": find_ingredients(text),
            "name_ings": set(name_ings) or set(desc_ings[:2]),
            "short": short,
            "display": re.sub(r"\s*\[[^\]]+\]$", "", display_name(short, name_ings, desc_ings, r["brand"])),
            "label": brand_label(r["brand"], r["line"]),
            "complexity": max(1, len(name_ings) or len(desc_ings[:3])),
            # составной вкус: в названии (или в пояснении для кодовых названий) 2+ ингредиента
            # всё, что не простой моно-вкус, считается составным (уже микс сам по себе)
            "n_ings": count_components(r, short, name_ings, desc_ings),
            "composite": not is_simple_flavor(r["flavor"], short, name_ings, r.get("description", "")),
        })
    return [i for i in items if i["tagset"]]


# ---------------------------------------------------------------------------
# Совместимость двух вкусов
# ---------------------------------------------------------------------------
def pair_score(a, b, bold=False):
    tg = [group_compat(x, y) for x in a["tagset"] for y in b["tagset"]]
    best, avg = max(tg), sum(tg) / len(tg)
    score = 0.65 * best + 0.35 * avg

    ia, ib = a["ings"], b["ings"]
    classic = sum(1 for x in ia for y in ib if frozenset((x, y)) in CLASSIC_SET)
    score += min(classic, 2) * 0.8
    if any(frozenset((x, y)) in CLASH_SET for x in ia for y in ib):
        score -= 2.5
    # одинаковый главный ингредиент — повтор (два лимона в одном миксе)
    common = a["name_ings"] & b["name_ings"]
    if common:
        smaller = max(1, min(len(a["name_ings"]), len(b["name_ings"])))
        score -= 1.5 + 3.0 * (len(common) / smaller)
    if a["short"] == b["short"] or a["short"] in b["short"] or b["short"] in a["short"]:
        score -= 3

    if bold:
        # поощряем пересечение разных классов, которые редко встречаются вместе
        cross = [group_compat(x, y) for x in a["tagset"] for y in b["tagset"] if x != y]
        if cross and 0.9 <= max(cross) <= 2.1 and not (a["tagset"] & b["tagset"]):
            score += 1.0
        if a["tagset"] & b["tagset"]:
            score -= 0.7
    return score


# ---------------------------------------------------------------------------
# Генерация
# ---------------------------------------------------------------------------
SIZE_WEIGHTS = {1: 15, 2: 40, 3: 35, 4: 10}
MIN_SCORE = {False: 2.0, True: 1.6}
COMPOSITE_MIN = {False: 3.0, True: 2.6}  # к составному добавляем только то, что с ним хорошо сочетается


def valid_mix(mix):
    """Правила составных вкусов:
    - составной из 3+ компонентов — только соло;
    - составной из 2 компонентов — только в паре с одним простым;
    - в миксах из 3–4 вкусов все вкусы простые."""
    comp = [m for m in mix if m["composite"]]
    if len(mix) == 1:
        return True
    if not comp:
        return True
    return len(mix) == 2 and len(comp) == 1 and comp[0]["n_ings"] <= 2


def weighted_choice(rng, items, weights):
    total = sum(weights)
    x = rng.uniform(0, total)
    acc = 0
    for it, w in zip(items, weights):
        acc += w
        if acc >= x:
            return it
    return items[-1]


def solo_candidates(db):
    """Для моно-микса: вкусы, которые самодостаточны — сложные, авторские, многокомпонентные."""
    res = []
    for i in db:
        line = (i["brand"] + " " + i["line"]).lower()
        complex_name = len(i["name_ings"] - {"холодок"}) >= 2
        signature = any(re.search(r"(?<![a-zа-я])" + w + r"(?![a-zа-я])", line) for w in
                        ["perfume", "парфюм", "гид", "shot", "шот", "hit by blackburn", "matchline",
                         "limited", "xperience", "bartender", "aroma line", "brilliant collection"])
        if complex_name or signature or "парфюм" in i["tagset"]:
            res.append(i)
    return res or db


def proportions(n, rng):
    presets = {1: [[100]], 2: [[50, 50], [60, 40], [70, 30]],
               3: [[40, 40, 20], [50, 30, 20], [40, 30, 30]],
               4: [[30, 30, 20, 20], [40, 30, 20, 10], [35, 25, 25, 15]]}
    return rng.choice(presets[n])


def generate_mix(db, rng, size=None, bold=None, require_tag=None, tries=60):
    if size is None:
        size = weighted_choice(rng, list(SIZE_WEIGHTS), list(SIZE_WEIGHTS.values()))
    if bold is None:
        bold = rng.random() < 0.25

    if size == 1:
        pool = solo_candidates(db)
        if require_tag:
            pool = [i for i in pool if require_tag in i["tagset"]] or pool
        pick = rng.choice(pool)
        return {"items": [pick], "bold": False, "score": None, "parts": [100]}

    best = None
    anchors_all = [i for i in db if not require_tag or require_tag in i["tagset"]] or db
    for _ in range(tries):
        simple_anchors = [i for i in anchors_all if not i["composite"]] or anchors_all
        if size >= 3 or rng.random() < 0.5:
            anchor = rng.choice(simple_anchors)  # 3–4 вкуса — только из простых
        else:
            anchor = rng.choice(anchors_all)
        target = size
        if anchor["composite"]:
            if anchor["n_ings"] >= 3:
                continue  # готовый микс из 3+ компонентов — только соло, не дополняем
            target = 2    # составной из 2 компонентов + ровно один простой
        mix = [anchor]
        ok = True
        while len(mix) < target:
            cand = rng.sample(db, min(500, len(db)))
            scored = []
            for c in cand:
                if c in mix:
                    continue
                if c["composite"]:
                    # составной допустим только вторым вкусом в миксе из двух и только из 2 компонентов
                    if target != 2 or c["n_ings"] >= 3 or any(m["composite"] for m in mix):
                        continue
                s = [pair_score(c, m, bold) for m in mix]
                with_comp = c["composite"] or any(m["composite"] for m in mix)
                need = COMPOSITE_MIN[bold] if with_comp else MIN_SCORE[bold] - 0.6
                if min(s) < need:
                    continue
                total = sum(s) / len(s) + 0.25 * min(s)
                scored.append((total, c))
            if not scored:
                ok = False
                break
            scored.sort(key=lambda x: -x[0])
            top = scored[:25]
            temp = 0.6 if bold else 0.45
            weights = [math.exp((t - top[0][0]) / temp) for t, _ in top]
            mix.append(weighted_choice(rng, [c for _, c in top], weights))
        if not ok or not valid_mix(mix):
            continue
        pairs = [pair_score(x, y, bold) for i, x in enumerate(mix) for y in mix[i + 1:]]
        mscore = sum(pairs) / len(pairs)
        if min(pairs) >= MIN_SCORE[bold] - 0.3 and mscore >= MIN_SCORE[bold]:
            best = (mix, mscore)
            break
        if best is None or mscore > best[1]:
            best = (mix, mscore)

    if best is None:  # не нашли — пробуем микс только из простых вкусов
        simple_db = [i for i in db if not i["composite"]]
        return generate_mix(simple_db, rng, size=size, bold=bold, require_tag=require_tag, tries=tries)
    mix, mscore = best
    parts = rng.choice([[60, 40], [70, 30]]) if any(m["composite"] for m in mix) else proportions(len(mix), rng)
    return {"items": mix, "bold": bold, "score": round(mscore, 2), "parts": parts}


def explain(mix):
    items = mix["items"]
    notes = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            cl = [f"{x}+{y}" for x in a["ings"] for y in b["ings"] if frozenset((x, y)) in CLASSIC_SET]
            if cl:
                notes.append("классика: " + ", ".join(sorted(set(cl))[:2]))
    groups = sorted({t for it in items for t in it["tagset"]})
    return groups, sorted(set(notes))


def format_mix(mix, details=False, brands=True):
    items = mix["items"]
    if brands:
        line = " \\ ".join(f"{it['display']} [{it['label']}]" for it in items)
    else:
        line = " \\ ".join(it["display"] for it in items)
    if not details:
        return line
    out = [line + ("   [смелый]" if mix["bold"] else "")]
    for it, p in zip(items, mix["parts"]):
        out.append(f"   {p:>3}%  {it['label']} — {it['flavor']}")
        if it.get("description"):
            out.append(f"         {it['description'][:140]}")
    groups, notes = explain(mix)
    tail = "   группы: " + ", ".join(groups)
    if mix["score"] is not None:
        tail += f" | совместимость: {mix['score']}"
    out.append(tail)
    for n in notes:
        out.append("   " + n)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Генератор кальянных миксов Shibaco")
    ap.add_argument("-n", "--count", type=int, default=10, help="сколько миксов (по умолчанию 10)")
    ap.add_argument("--size", type=int, choices=[1, 2, 3, 4], help="фиксированное число вкусов")
    ap.add_argument("--bold", action="store_true", help="только смелые миксы")
    ap.add_argument("--classic", action="store_true", help="только классические миксы")
    ap.add_argument("--brand", action="append", help="ограничить брендами (можно несколько раз)")
    ap.add_argument("--tag", help="обязательная вкусовая группа, напр. цитрус, парфюм, пряности")
    ap.add_argument("--strength", choices=["лёгкий", "средний", "крепкий"], help="фильтр по крепости линейки")
    ap.add_argument("--seed", type=int, help="seed для повторяемости")
    ap.add_argument("--details", action="store_true", help="подробный вывод: бренды, пропорции, описания")
    ap.add_argument("--json", action="store_true", help="вывод в JSON")
    ap.add_argument("--no-brand", action="store_true", help="не показывать бренды в строке микса")
    ap.add_argument("--db", default=DB_PATH, help="путь к базе tobacco_flavors.json")
    a = ap.parse_args()

    rng = random.Random(a.seed)
    db = load_db(a.db)
    if a.brand:
        bl = [b.lower() for b in a.brand]
        db = [i for i in db if any(b in i["brand"].lower() or b in i["line"].lower() for b in bl)]
    if a.strength:
        db = [i for i in db if i.get("strength") == a.strength]
    if len(db) < 4:
        raise SystemExit("Слишком мало вкусов после фильтров.")

    bold = True if a.bold else (False if a.classic else None)
    mixes, seen = [], set()
    attempts = 0
    while len(mixes) < a.count and attempts < a.count * 10:
        attempts += 1
        m = generate_mix(db, rng, size=a.size, bold=bold, require_tag=a.tag)
        key = frozenset(it["short"] for it in m["items"])
        if key in seen:
            continue
        seen.add(key)
        mixes.append(m)

    if a.json:
        print(json.dumps([{
            "mix": format_mix(m, brands=not a.no_brand),
            "bold": m["bold"],
            "score": m["score"],
            "components": [{"percent": p, "brand": it["brand"], "line": it["line"], "flavor": it["flavor"],
                            "url": it["url"]} for it, p in zip(m["items"], m["parts"])],
        } for m in mixes], ensure_ascii=False, indent=1))
        return
    sep = "\n\n" if a.details else "\n"
    print(sep.join(format_mix(m, a.details, not a.no_brand) for m in mixes))


if __name__ == "__main__":
    main()
