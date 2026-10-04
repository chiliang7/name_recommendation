# -*- coding: utf-8 -*-
"""生肖姓名學:地支關係(三合/六合/沖/害/刑)+ 傳統喜忌字根"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

with open(os.path.join(DATA_DIR, "zodiac_extra.json"), encoding="utf-8") as f:
    EXTRA = json.load(f)

ANIMALS = ["鼠", "牛", "虎", "兔", "龍", "蛇", "馬", "羊", "猴", "雞", "狗", "豬"]
BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 各生肖對應的代表字根(用於三合/六合/沖/害的喜忌判斷)
ANIMAL_ROOTS = {
    "鼠": ["鼠", "子"],
    "牛": ["牛", "牜", "丑"],
    "虎": ["虎", "虍", "寅"],
    "兔": ["兔", "卯"],
    "龍": ["龍", "辰", "竜"],
    "蛇": ["巳", "虫", "辶", "廴", "弓", "它"],
    "馬": ["馬", "午"],
    "羊": ["羊", "未", "𦍌"],
    "猴": ["申", "猴", "袁", "侯"],
    "雞": ["酉", "隹", "鳥", "羽", "雞"],
    "狗": ["犬", "犭", "戌", "狗"],
    "豬": ["豕", "亥", "豬"],
}

SANHE = [["猴", "鼠", "龍"], ["蛇", "雞", "牛"], ["虎", "馬", "狗"], ["豬", "兔", "羊"]]
LIUHE = {"鼠": "牛", "牛": "鼠", "虎": "豬", "豬": "虎", "兔": "狗", "狗": "兔",
         "龍": "雞", "雞": "龍", "蛇": "猴", "猴": "蛇", "馬": "羊", "羊": "馬"}
# 六沖:相隔六位
CHONG = {a: ANIMALS[(i + 6) % 12] for i, a in enumerate(ANIMALS)}
HAI = {"鼠": "羊", "羊": "鼠", "牛": "馬", "馬": "牛", "虎": "蛇", "蛇": "虎",
       "兔": "龍", "龍": "兔", "猴": "豬", "豬": "猴", "雞": "狗", "狗": "雞"}
# 三刑(略去自刑)
XING = {"鼠": ["兔"], "兔": ["鼠"],
        "虎": ["蛇", "猴"], "蛇": ["虎", "猴"], "猴": ["虎", "蛇"],
        "牛": ["狗", "羊"], "狗": ["牛", "羊"], "羊": ["牛", "狗"]}

# 字根別名:規則寫本字,元件可能以偏旁出現
ALIASES = {
    "水": ["水", "氵", "氺"], "艹": ["艹", "艸"], "心": ["心", "忄"],
    "犬": ["犬", "犭"], "肉": ["肉", "月"], "示": ["示", "礻"],
    "衣": ["衣", "衤"], "人": ["人", "亻"], "金": ["金", "釒"],
    "火": ["火", "灬"], "足": ["足", "⻊"], "手": ["手", "扌"],
}


def _expand(roots):
    out = set()
    for r in roots:
        out.update(ALIASES.get(r, [r]))
    return out


def year_to_zodiac(year: int) -> str:
    """西元年 → 生肖(以立春為界的精確判斷不在此,取農曆年近似)"""
    return ANIMALS[(year - 4) % 12]


def rules_for(zodiac: str) -> dict:
    """組合該生肖的所有喜忌規則(地支關係自動推導 + 傳統喜忌)"""
    favor, avoid = [], []

    for group in SANHE:
        if zodiac in group:
            for partner in group:
                if partner != zodiac:
                    favor.append({
                        "roots": ANIMAL_ROOTS[partner], "level": "major",
                        "reason": f"{'、'.join(group)}三合,{partner}相關字根為貴人助力",
                        "tag": f"三合({partner})",
                    })
    liuhe = LIUHE[zodiac]
    favor.append({"roots": ANIMAL_ROOTS[liuhe], "level": "major",
                  "reason": f"{zodiac}與{liuhe}六合,相輔相成",
                  "tag": f"六合({liuhe})"})

    chong = CHONG[zodiac]
    avoid.append({"roots": ANIMAL_ROOTS[chong], "level": "major",
                  "reason": f"{zodiac}與{chong}正沖,衝突對立",
                  "tag": f"對沖({chong})"})
    hai = HAI[zodiac]
    avoid.append({"roots": ANIMAL_ROOTS[hai], "level": "major",
                  "reason": f"{zodiac}與{hai}相害,暗中損耗",
                  "tag": f"相害({hai})"})
    for x in XING.get(zodiac, []):
        avoid.append({"roots": ANIMAL_ROOTS[x], "level": "minor",
                      "reason": f"{zodiac}與{x}相刑,易有刑剋",
                      "tag": f"相刑({x})"})

    extra = EXTRA.get(zodiac, {})
    for r in extra.get("favor", []):
        favor.append({**r, "tag": "傳統喜用"})
    for r in extra.get("avoid", []):
        avoid.append({**r, "tag": "傳統忌用"})

    return {"favor": favor, "avoid": avoid}


def check_char(char: str, comp_counts: dict, zodiac: str) -> dict:
    """comp_counts: {部件: 出現次數},應包含字本身與部首。
    回傳該字對此生肖的喜忌命中。"""
    rules = rules_for(zodiac)
    hits = {"favor": [], "avoid": []}
    for kind in ("favor", "avoid"):
        for rule in rules[kind]:
            need = rule.get("min_count", 1)
            matched = [c for c in _expand(rule["roots"]) if comp_counts.get(c, 0) > 0]
            total = sum(comp_counts.get(c, 0) for c in matched)
            if matched and total >= need:
                hits[kind].append({
                    "matched": matched, "tag": rule["tag"],
                    "level": rule["level"], "reason": rule["reason"],
                })
    return hits


def score_char(hits: dict) -> int:
    """粗略分數:major favor +2 / minor +1;major avoid -3 / minor -1"""
    s = 0
    for h in hits["favor"]:
        s += 2 if h["level"] == "major" else 1
    for h in hits["avoid"]:
        s -= 3 if h["level"] == "major" else 1
    return s
