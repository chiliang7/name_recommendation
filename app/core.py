# -*- coding: utf-8 -*-
"""共用核心:字庫查詢 + 完整分析/推薦邏輯(FastAPI 與 stdlib server 共用)"""
import json
import os
import random
import sqlite3
import unicodedata

from . import wuge, zodiac

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "db", "naming.sqlite3")
DATA_DIR = os.path.join(ROOT, "data")

with open(os.path.join(DATA_DIR, "name_pool.json"), encoding="utf-8") as f:
    NAME_POOL = json.load(f)["chars"]
POOL_GLOSS = {e["c"]: e["gloss"] for e in NAME_POOL}
with open(os.path.join(DATA_DIR, "english_names.json"), encoding="utf-8") as f:
    ENGLISH = json.load(f)


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def get_char_info(con, ch):
    row = con.execute("SELECT * FROM chars WHERE char=?", (ch,)).fetchone()
    return dict(row) if row else None


def get_comp_counts(con, ch):
    rows = con.execute("SELECT comp, count FROM components WHERE char=?", (ch,)).fetchall()
    return {r["comp"]: r["count"] for r in rows}


def _merge_radical(comp, radical):
    """部首併入部件(原子字如「由」拆不出「田」,靠部首補上);
    已有等價偏旁(氵=水)時不重複加,避免 min_count 規則重複計數"""
    aliases = zodiac.ALIASES.get(radical, [radical])
    if not any(a in comp for a in aliases):
        comp[radical] = 1


def english_for(chars_info):
    """依名字各字的拼音與字義推薦英文名"""
    out = []
    seen = set()
    for i, info in enumerate(chars_info):
        py = info.get("pinyin_plain") or ""
        for m in ENGLISH["by_meaning"].get(info["char"], []):
            key = m["name"]
            if key not in seen:
                seen.add(key)
                out.append({**m, "match": f"字義「{info['char']}」",
                            "priority": 0 if i == 0 else 1})
        for m in ENGLISH["by_pinyin"].get(py, []):
            key = m["name"]
            if key not in seen:
                seen.add(key)
                out.append({**m, "match": f"音近「{info['char']}({py})」",
                            "priority": 0 if i == 0 else 1})
    out.sort(key=lambda x: x["priority"])
    return out[:10]


def analyze(surname: str, given: str, year: int = 2026, use_modern: bool = False):
    surname = surname.strip()
    given = given.strip()
    if not (1 <= len(surname) <= 2 and 1 <= len(given) <= 2):
        raise ValueError("僅支援一~二字姓 + 一~二字名")

    con = _conn()
    try:
        all_chars = list(surname + given)
        infos, missing = [], []
        for ch in all_chars:
            info = get_char_info(con, ch)
            if info is None:
                missing.append(ch)
            infos.append(info)
        if missing:
            raise ValueError(f"字庫查無:{'、'.join(missing)}(限 Big5 繁體字)")

        key = "modern" if use_modern else "kangxi"
        s_strokes = [infos[i][key] for i in range(len(surname))]
        g_strokes = [infos[len(surname) + i][key] for i in range(len(given))]

        grids = wuge.five_grids(s_strokes, g_strokes)

        zo = zodiac.year_to_zodiac(year)
        zodiac_checks = []
        for i, ch in enumerate(given):
            comp = get_comp_counts(con, ch)
            comp.setdefault(ch, 1)
            _merge_radical(comp, infos[len(surname) + i]["radical"])
            hits = zodiac.check_char(ch, comp, zo)
            zodiac_checks.append({"char": ch, "hits": hits,
                                  "score": zodiac.score_char(hits)})

        given_infos = infos[len(surname):]
        return {
            "surname": surname, "given": given, "year": year, "zodiac": zo,
            "stroke_basis": "現代筆畫" if use_modern else "康熙筆畫",
            "chars": [{"char": c["char"], "kangxi": c["kangxi"],
                       "modern": c["modern"], "radical": c["radical"],
                       "pinyin": c["pinyin"]} for c in infos],
            "grids": grids,
            "zodiac_checks": zodiac_checks,
            "english": english_for(given_infos),
        }
    finally:
        con.close()


def suggest_chars(year: int = 2026, gender: str = ""):
    """從精選字庫挑字並分級:
    佳   — 有生肖喜用字根且無任何忌用
    次佳 — 中性(無喜忌),或僅有輕微小忌但有喜用可抵(總分不為負)
    犯重忌(major avoid)或總分為負者剔除。"""
    zo = zodiac.year_to_zodiac(year)
    con = _conn()
    try:
        best, good = [], []
        seen = set()
        for entry in NAME_POOL:
            ch = entry["c"]
            if ch in seen:
                continue
            if gender and entry["gender"] not in (gender, "n"):
                continue
            seen.add(ch)
            info = get_char_info(con, ch)
            if info is None:
                continue
            comp = get_comp_counts(con, ch)
            comp.setdefault(ch, 1)
            _merge_radical(comp, info["radical"])
            hits = zodiac.check_char(ch, comp, zo)
            score = zodiac.score_char(hits)
            if any(h["level"] == "major" for h in hits["avoid"]):
                continue  # 犯重忌剔除
            if score < 0:
                continue  # 小忌無喜用可抵,亦不推薦
            item = {
                "char": ch, "gloss": entry["gloss"], "gender": entry["gender"],
                "kangxi": info["kangxi"], "modern": info["modern"],
                "radical": info["radical"], "pinyin": info["pinyin"],
                "score": score,
                "favor": [h["tag"] for h in hits["favor"]],
                "caveat": [f"{h['tag']}:{h['reason']}" for h in hits["avoid"]],
            }
            if hits["favor"] and not hits["avoid"]:
                best.append(item)
            else:
                good.append(item)
        key = lambda x: (-x["score"], x["kangxi"])
        best.sort(key=key)
        good.sort(key=key)
        return {"year": year, "zodiac": zo, "best": best, "good": good}
    finally:
        con.close()


def zodiac_rules(year: int = 2026):
    zo = zodiac.year_to_zodiac(year)
    return {"year": year, "zodiac": zo, "rules": zodiac.rules_for(zo)}


# ── 音韻(平仄)分析 ──────────────────────────────────────────

_TONE_MARKS = {"\u0304": 1, "\u0301": 2, "\u030c": 3, "\u0300": 4}
_INITIALS = ["zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l",
             "g", "k", "h", "j", "q", "x", "r", "z", "c", "s", "y", "w"]
# 開口響亮的韻母(ㄚ/ㄤ/ㄥ 系)
_OPEN_FINALS = {"a", "ai", "ao", "an", "ang", "ia", "iao", "ian", "iang",
                "ua", "uai", "uan", "uang", "ong", "iong", "eng", "ing"}


# ── 護照拼音:威妥瑪(外交部護照慣用式,不標送氣符/變音符,ㄅㄆ同為 p)──
# 對照依據:注音符號與羅馬拼音對照表(文藻外語大學,護照式威妥瑪)
_WG_WHOLE = {
    "zhi": "chih", "chi": "chih", "shi": "shih", "ri": "jih",
    "zi": "tzu", "ci": "tsu", "si": "szu", "er": "erh", "he": "ho",
    "yan": "yen", "ye": "yeh", "you": "yu", "yong": "yung", "yue": "yueh",
}
_WG_INITIALS = [  # 依序比對,zh/ch/sh 需在 z/c/s 之前
    ("zh", "ch"), ("ch", "ch"), ("sh", "sh"), ("b", "p"), ("p", "p"),
    ("m", "m"), ("f", "f"), ("d", "t"), ("t", "t"), ("n", "n"), ("l", "l"),
    ("g", "k"), ("k", "k"), ("h", "h"), ("j", "ch"), ("q", "ch"),
    ("x", "hs"), ("r", "j"), ("z", "ts"), ("c", "ts"), ("s", "s"),
]


def _wg_final(initial, final):
    if final == "ian":
        return "ien"
    if final == "ie":
        return "ieh"
    if final == "ue":
        return "ueh"
    if final == "ong":
        return "ung"
    if final == "iong":
        return "iung"
    if final == "uo":
        return "uo" if initial in ("g", "k", "h", "sh") else "o"
    if final == "ui" and initial in ("g", "k"):
        return "uei"
    return final


def to_wade(plain: str) -> str:
    """無調漢語拼音 → 護照式威妥瑪(如 jun→chun, xin→hsin, si→szu)"""
    if plain in _WG_WHOLE:
        return _WG_WHOLE[plain]
    for h, w in _WG_INITIALS:
        if plain.startswith(h):
            return w + _wg_final(h, plain[len(h):])
    return plain  # 零聲母(a/an/ai…)與 y/w 系多數不變


def _syllable(info):
    """由字庫的拼音欄位取出 聲調/聲母/韻母"""
    tone = 5
    for c in unicodedata.normalize("NFD", info["pinyin"] or ""):
        if c in _TONE_MARKS:
            tone = _TONE_MARKS[c]
            break
    plain = info["pinyin_plain"] or ""
    initial, final = "", plain
    for i in _INITIALS:
        if plain.startswith(i):
            initial, final = i, plain[len(i):]
            break
    return {"tone": tone, "initial": initial, "final": final, "plain": plain}


def phonetic_score(sylls):
    """依音韻原則打分:同調/全平全仄扣分、平仄相間加分、
    尾字響亮加分、疊聲母疊韻母同音扣分、三聲連讀提示變調"""
    score = 0
    notes = []
    tones = [s["tone"] for s in sylls]
    pz = ["平" if t in (1, 2) else "仄" for t in tones]

    if len(set(tones)) == 1:
        score -= 3
        notes.append(f"三字同調({'-'.join(map(str, tones))}),平板")
    # 平仄只取其精神:有平有仄、避免單調即可,不苛求嚴格相間
    if len(set(pz)) == 1:
        score -= 1
        notes.append(f"全{pz[0]},缺乏節奏")
    else:
        score += 2
        notes.append("有平有仄,聲調有起伏")

    last = sylls[-1]
    if last["tone"] in (1, 2):
        score += 1
    elif last["tone"] == 3:
        score -= 1
        notes.append("尾字三聲,叫喚偏沉")
    if last["final"] in _OPEN_FINALS:
        score += 1
        notes.append("尾字開口音,響亮")

    for a, b in zip(sylls, sylls[1:]):
        if a["plain"] and a["plain"] == b["plain"]:
            score -= 2
            notes.append(f"「{a['plain']}」同音相連")
            continue
        if a["initial"] and a["initial"] == b["initial"]:
            score -= 1
            notes.append(f"聲母 {a['initial']}- 相連易拗口")
        if a["final"] and a["final"] == b["final"]:
            score -= 1
            notes.append(f"疊韻(-{a['final']})連讀含糊")
        if a["tone"] == 3 and b["tone"] == 3:
            notes.append("兩個三聲連讀,前字實唸二聲")
    return score, notes


def _rare_of(info):
    """常用度 1(最常見)~5(最冷門):香港小學字級 1-6 為主,Big5 分級後備"""
    g = info.get("grade")
    if g:
        return 1 if g <= 2 else (2 if g <= 4 else 3)
    return 4 if info.get("big5level") == 1 else 5


def _char_entry(con, ch, zo, gloss, strict=True):
    """單一候選字的完整資料;strict 時剔除生肖重忌/總分為負者,
    非 strict(使用者指定字)一律保留並附忌用警語"""
    info = get_char_info(con, ch)
    if info is None or not info["pinyin_plain"]:
        return None
    comp = get_comp_counts(con, ch)
    comp.setdefault(ch, 1)
    _merge_radical(comp, info["radical"])
    hits = zodiac.check_char(ch, comp, zo)
    zscore = zodiac.score_char(hits)
    if strict and (any(h["level"] == "major" for h in hits["avoid"]) or zscore < 0):
        return None
    return {
        "char": ch, "gloss": gloss, "kangxi": info["kangxi"],
        "modern": info["modern"], "rare": _rare_of(info),
        "pinyin": info["pinyin"], "syll": _syllable(info),
        "zscore": zscore, "favor": [h["tag"] for h in hits["favor"]],
        "avoid_notes": [f"「{ch}」{h['tag']}:{h['reason']}"
                        for h in hits["avoid"]],
    }


def _candidate_pool(con, zo, gender):
    """通過生肖檢查(無重忌、總分不為負)的候選字,附音節資訊"""
    out = []
    seen = set()
    for entry in NAME_POOL:
        ch = entry["c"]
        if ch in seen:
            continue
        if gender and entry["gender"] not in (gender, "n"):
            continue
        seen.add(ch)
        e = _char_entry(con, ch, zo, entry["gloss"], strict=True)
        if e:
            out.append(e)
    return out


def _parse_chars(text: str, max_chars=4):
    """解析使用者輸入的字清單:只留漢字,逗號/頓號/空白/注音符號等分隔一律忽略"""
    out = []
    for c in text or "":
        if "一" <= c <= "鿿" and c not in out:
            out.append(c)
    return out[:max_chars]


def suggest_names(surname: str, year: int = 2026, gender: str = "",
                  length: int = 2, limit: int = 40,
                  rarity: int = 1, luck: int = 1, max_strokes: int = 0,
                  like: str = "", dislike: str = ""):
    """組合推薦完整名字:生肖合格字 × 音韻(平仄)評分 × 三才五格過濾。

    rarity 冷門度:0 常見優先 / 1 均衡 / 2 偏冷門(調整冷門字的抽樣權重)
    luck 吉度門檻:2 嚴選(三才大吉且人地總數理皆吉)/ 1 吉以上(三才大吉或吉,預設)
                  / 0 寬鬆(排除大凶即可);無符合時自動逐級放寬並回報
    max_strokes 全名總筆畫上限(現代筆畫、實際書寫),0 = 不限
    like 想用的字(如「程,睿」):推薦的名字必含其中至少一字;
         指定字不受性別/生肖忌用剔除,但有忌用會附警語(最多取 4 字)
    dislike 不想用的字:推薦一律排除(最多 200 字,超過報錯);與 like 衝突時報錯"""
    surname = surname.strip()
    if not 1 <= len(surname) <= 2:
        raise ValueError("僅支援一~二字姓")
    if length not in (1, 2):
        raise ValueError("名字長度僅支援 1 或 2 字")

    con = _conn()
    try:
        s_infos = []
        for ch in surname:
            info = get_char_info(con, ch)
            if info is None:
                raise ValueError(f"字庫查無:{ch}(限 Big5 繁體字)")
            s_infos.append(info)
        s_strokes = [i["kangxi"] for i in s_infos]
        s_sylls = [_syllable(i) for i in s_infos]
        s_modern = sum(i["modern"] for i in s_infos)

        zo = zodiac.year_to_zodiac(year)
        pool = _candidate_pool(con, zo, gender)

        banned_list = _parse_chars(dislike, max_chars=201)
        if len(banned_list) > 200:
            raise ValueError("不想用的字太多(上限 200 字)")
        banned = set(banned_list)
        liked_chars = _parse_chars(like)
        conflict = banned & set(liked_chars)
        if conflict:
            raise ValueError(f"「{'、'.join(conflict)}」同時在想用與不想用清單,請擇一")
        if banned:
            pool = [e for e in pool if e["char"] not in banned]
        liked, missing_like = [], []
        for ch in liked_chars:
            e = _char_entry(con, ch, zo, POOL_GLOSS.get(ch, "指定用字"),
                            strict=False)
            (liked.append(e) if e else missing_like.append(ch))
        if liked_chars and not liked:
            raise ValueError(f"想用的字查無:{'、'.join(missing_like)}(限 Big5 繁體字)")

        if liked:
            # 名字必含至少一個指定字;雙名時前後位置都試,指定字互配也算
            if length == 1:
                combos = [(L,) for L in liked]
            else:
                combos, seen_combo = [], set()
                partners = pool + liked
                for L in liked:
                    for p in partners:
                        if p["char"] == L["char"]:
                            continue
                        for pair in ((L, p), (p, L)):
                            key = (pair[0]["char"], pair[1]["char"])
                            if key not in seen_combo:
                                seen_combo.add(key)
                                combos.append(pair)
        else:
            combos = ([(c,) for c in pool] if length == 1 else
                      ((a, b) for a in pool for b in pool if a["char"] != b["char"]))

        results = []
        for combo in combos:
            total_modern = s_modern + sum(c["modern"] for c in combo)
            if max_strokes and total_modern > max_strokes:
                continue
            grids = wuge.five_grids(s_strokes, [c["kangxi"] for c in combo])
            sc = grids["三才"]
            if sc["rating"] == "大凶":
                continue
            if any(grids[k]["shuli"]["rating"] == "凶" for k in ("人格", "地格", "總格")):
                continue
            # 三才凶不硬剔除(某些姓氏+字數結構上必凶),改為降序並標示
            # 吉度分層:2=三才大吉且人地總數理皆吉, 1=三才吉以上, 0=其餘
            if sc["rating"] == "大吉" and all(
                    grids[k]["shuli"]["rating"] == "吉"
                    for k in ("人格", "地格", "總格")):
                tier = 2
            elif sc["rating"] in ("大吉", "吉"):
                tier = 1
            else:
                tier = 0
            sylls = s_sylls + [c["syll"] for c in combo]
            ph, notes = phonetic_score(sylls)
            if ph < 0:
                continue
            notes = notes + [w for c in combo for w in c.get("avoid_notes", [])]
            ztotal = sum(c["zscore"] for c in combo)
            rr = sum(c["rare"] for c in combo) / len(combo)  # 1 常見 ~ 5 冷門
            rank = ph * 2 + ztotal + sc["score"]
            if rarity == 2:
                rank += (rr - 1) * 1.5   # 偏好冷門字
            elif rarity == 0:
                rank -= (rr - 1) * 1.5   # 偏好常見字
            results.append({
                "given": "".join(c["char"] for c in combo),
                "full": surname + "".join(c["char"] for c in combo),
                "tones": "-".join(str(s["tone"]) for s in sylls),
                "pingze": "".join("平" if s["tone"] in (1, 2) else "仄" for s in sylls),
                "wade": "-".join(to_wade(c["syll"]["plain"]).capitalize()
                                 for c in combo),
                "hanyu": "-".join(c["syll"]["plain"].capitalize()
                                  for c in combo),
                "phonetic": ph, "notes": notes,
                "sancai": {"combo": sc["combo"], "rating": sc["rating"]},
                "zong": grids["總格"]["num"],
                "zong_rating": grids["總格"]["shuli"]["rating"],
                "zscore": ztotal,
                "favor": sorted({t for c in combo for t in c["favor"]}),
                "gloss": " / ".join(c["gloss"] for c in combo),
                "total_modern": total_modern,
                "rare": round(rr, 1),
                "tier": tier,
                "rank": rank,
            })

        # 依吉度門檻過濾;無符合時逐級放寬
        want = luck
        filtered = [n for n in results if n["tier"] >= want]
        while not filtered and want > 0:
            want -= 1
            filtered = [n for n in results if n["tier"] >= want]
        filtered.sort(key=lambda x: (x["sancai"]["rating"] == "凶",
                                     -x["rank"], x["zong"]))
        all_bad = bool(filtered) and all(
            n["sancai"]["rating"] == "凶" for n in filtered)
        picked = _weighted_sample(filtered, limit,
                                  liked={e["char"] for e in liked})
        return {"surname": surname, "year": year, "zodiac": zo,
                "length": length, "total": len(filtered),
                "sancai_warning": all_bad,
                "luck_relaxed": want < luck,
                "liked": [e["char"] for e in liked],
                "disliked": banned_list,
                "missing_like": missing_like,
                "liked_unmatched": [
                    e["char"] for e in liked
                    if not any(e["char"] in n["given"] for n in filtered)],
                "names": picked}
    finally:
        con.close()


def _weighted_sample(results, limit, pool_size=1000, max_char_repeat=3,
                     liked=frozenset()):
    """從高分候選中加權隨機抽樣:分數越高越容易被抽中,但每次結果不同。
    多樣性限制:同一個字最多 max_char_repeat 次(指定字除外)、
    同一種平仄型態最多佔一半(避免整批都是平仄平)、
    多個指定字時名額平均分配(避免高分指定字整批獨占)"""
    if len(results) <= limit:
        return results
    pool = results[:pool_size]
    min_rank = min(n["rank"] for n in pool)
    weights = [n["rank"] - min_rank + 1 for n in pool]
    max_pattern = max(limit // 2, 1)
    liked_cap = -(-limit // len(liked)) if liked else 0  # ceil

    picked = []
    char_used = {}
    pattern_used = {}
    liked_used = {}
    idxs = list(range(len(pool)))
    overflow = []  # 被多樣性限制擋下的高分者,不足時回補
    while idxs and len(picked) < limit:
        total_w = sum(weights[i] for i in idxs)
        r = random.uniform(0, total_w)
        acc = 0.0
        chosen = idxs[-1]
        for i in idxs:
            acc += weights[i]
            if acc >= r:
                chosen = i
                break
        idxs.remove(chosen)
        n = pool[chosen]
        in_liked = [c for c in n["given"] if c in liked]
        if (any(char_used.get(c, 0) >= max_char_repeat
                for c in n["given"] if c not in liked)
                or pattern_used.get(n["pingze"], 0) >= max_pattern
                or (in_liked and all(liked_used.get(c, 0) >= liked_cap
                                     for c in in_liked))):
            overflow.append(n)
            continue
        for c in n["given"]:
            if c in liked:
                liked_used[c] = liked_used.get(c, 0) + 1
            else:
                char_used[c] = char_used.get(c, 0) + 1
        pattern_used[n["pingze"]] = pattern_used.get(n["pingze"], 0) + 1
        picked.append(n)
    for n in overflow:  # 候選不足時放寬限制補滿
        if len(picked) >= limit:
            break
        picked.append(n)
    picked.sort(key=lambda x: (x["sancai"]["rating"] == "凶", -x["rank"]))
    return picked
