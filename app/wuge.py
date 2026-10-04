# -*- coding: utf-8 -*-
"""三才五格計算引擎(康熙筆畫、熊崎氏五格剖象法)"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

with open(os.path.join(DATA_DIR, "shuli_81.json"), encoding="utf-8") as f:
    SHULI = json.load(f)

# 尾數 → 五行:1,2木 3,4火 5,6土 7,8金 9,0水
WUXING_OF_DIGIT = {1: "木", 2: "木", 3: "火", 4: "火", 5: "土",
                   6: "土", 7: "金", 8: "金", 9: "水", 0: "水"}

SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}  # 相生
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}      # 相剋


def wuxing_of(num: int) -> str:
    return WUXING_OF_DIGIT[num % 10]


def shuli_of(num: int) -> dict:
    """81 數理吉凶,超過 81 減 80 循環"""
    n = num
    while n > 81:
        n -= 80
    e = SHULI[str(n)]
    return {"num": num, "rating": e["rating"], "desc": e["desc"]}


def _relation(a: str, b: str) -> str:
    """a 對 b 的關係"""
    if a == b:
        return "比和"
    if SHENG[a] == b:
        return "生"     # a 生 b
    if SHENG[b] == a:
        return "被生"   # b 生 a
    if KE[a] == b:
        return "剋"     # a 剋 b
    return "被剋"       # b 剋 a


def sancai(tian: str, ren: str, di: str) -> dict:
    """三才吉凶:依五行生剋推導(人格為核心)。

    權重:他生人 +2、人生他 +1、比和 +1、人剋他 -1、他剋人 -3;
    天地相生 +0.5、天地比和 +0.5、天地相剋 -0.5
    """
    score = 0.0
    relations = []

    for other, label in ((tian, "天格"), (di, "地格")):
        rel = _relation(other, ren)  # other 對 人格
        if rel == "生":
            score += 2
            relations.append(f"{label}{other}生人格{ren}(吉)")
        elif rel == "被生":
            score += 1
            relations.append(f"人格{ren}生{label}{other}(洩氣,平)")
        elif rel == "比和":
            score += 1
            relations.append(f"{label}{other}與人格{ren}比和(平吉)")
        elif rel == "剋":
            score -= 3
            relations.append(f"{label}{other}剋人格{ren}(凶)")
        else:  # 人剋他
            score -= 1
            relations.append(f"人格{ren}剋{label}{other}(小凶)")

    rel_td = _relation(tian, di)
    if rel_td in ("生", "被生"):
        score += 0.5
        relations.append(f"天格{tian}與地格{di}相生")
    elif rel_td == "比和":
        score += 0.5
        relations.append(f"天格{tian}與地格{di}比和")
    else:
        score -= 0.5
        relations.append(f"天格{tian}與地格{di}相剋")

    if score >= 3:
        rating = "大吉"
    elif score >= 2:
        rating = "吉"
    elif score >= 0:
        rating = "中"
    elif score >= -3:
        rating = "凶"
    else:
        rating = "大凶"

    return {"combo": tian + ren + di, "rating": rating,
            "score": score, "relations": relations}


def five_grids(surname_strokes: list, given_strokes: list) -> dict:
    """五格計算。surname_strokes: 姓各字筆畫; given_strokes: 名各字筆畫。
    支援單姓/複姓 × 單名/雙名。"""
    s, g = surname_strokes, given_strokes
    if not s or not g or len(s) > 2 or len(g) > 2:
        raise ValueError("僅支援一~二字姓 + 一~二字名")

    if len(s) == 1:
        tian = s[0] + 1
    else:
        tian = s[0] + s[1]

    ren = s[-1] + g[0]

    if len(g) == 1:
        di = g[0] + 1
    else:
        di = g[0] + g[1]

    zong = sum(s) + sum(g)

    # 外格
    if len(s) == 1 and len(g) == 1:
        wai = 2
    elif len(s) == 1:
        wai = g[1] + 1
    elif len(g) == 1:
        wai = s[0] + 1
    else:
        wai = s[0] + g[1]

    grids = {"天格": tian, "人格": ren, "地格": di, "外格": wai, "總格": zong}
    out = {}
    for name, num in grids.items():
        out[name] = {
            "num": num,
            "wuxing": wuxing_of(num),
            "shuli": shuli_of(num),
        }
    out["三才"] = sancai(out["天格"]["wuxing"], out["人格"]["wuxing"],
                         out["地格"]["wuxing"])
    return out
