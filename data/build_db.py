# -*- coding: utf-8 -*-
"""建立字庫 SQLite:康熙筆畫(kRSUnicode 部首歸正推導)+ 現代筆畫 + 部件(IDS 遞迴展開)。

用法:python3 data/build_db.py
輸入:data/unihan/*.txt, data/ids.txt, data/overrides.json
輸出:db/naming.sqlite3
"""
import json
import os
import re
import sqlite3
import sys
import unicodedata
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UNIHAN = os.path.join(HERE, "unihan")
DB_PATH = os.path.join(ROOT, "db", "naming.sqlite3")

# 214 康熙部首(索引 1-214)
RADICALS = (
    "一丨丶丿乙亅二亠人儿入八冂冖冫几凵刀力勹匕匚匸十卜卩厂厶又"
    "口囗土士夂夊夕大女子宀寸小尢尸屮山巛工己巾干幺广廴廾弋弓彐彡彳"
    "心戈戶手支攴文斗斤方无日曰月木欠止歹殳毋比毛氏气水火爪父爻爿片牙牛犬"
    "玄玉瓜瓦甘生用田疋疒癶白皮皿目矛矢石示禸禾穴立"
    "竹米糸缶网羊羽老而耒耳聿肉臣自至臼舌舛舟艮色艸虍虫血行衣襾"
    "見角言谷豆豕豸貝赤走足身車辛辰辵邑酉釆里"
    "金長門阜隶隹雨青非面革韋韭音頁風飛食首香馬骨高髟鬥鬯鬲鬼"
    "魚鳥鹵鹿麥麻黃黍黑黹黽鼎鼓鼠鼻齊齒龍龜龠"
)
assert len(RADICALS) == 214

# 部首康熙筆畫(依部首編號分組)
_GROUPS = [(6, 1), (29, 2), (60, 3), (94, 4), (117, 5), (146, 6), (166, 7),
           (175, 8), (186, 9), (194, 10), (200, 11), (204, 12), (208, 13),
           (210, 14), (211, 15), (213, 16), (214, 17)]


def radical_strokes(idx: int) -> int:
    for last, strokes in _GROUPS:
        if idx <= last:
            return strokes
    raise ValueError(idx)


def parse_unihan_field(path, field):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or "\t" not in line:
                continue
            cp, fld, val = line.rstrip("\n").split("\t", 2)
            if fld == field:
                out[chr(int(cp[2:], 16))] = val
    return out


def strip_tone(pinyin: str) -> str:
    s = unicodedata.normalize("NFD", pinyin)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("ü", "u")


CJK_RE = re.compile(r"[㐀-鿿豈-﫿\U00020000-\U0003FFFF⺀-⿟]")
IDC = set("⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿼⿽⿾⿿")


def load_ids(path):
    """char -> IDS 拆解字串(多欄時優先取含 T 標記者)"""
    ids_map = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.split()  # tab 或空格分隔皆可
            if len(parts) < 3:
                continue
            ch = parts[1]
            if len(ch) != 1:
                continue
            fields = parts[2:]
            chosen = fields[0]
            for fld in fields:
                m = re.search(r"\[([A-Z]+)\]$", fld)
                if m and "T" in m.group(1):
                    chosen = fld
                    break
            chosen = re.sub(r"\[[A-Z]+\]$", "", chosen)
            chosen = re.sub(r"&[A-Za-z0-9-]+;", "", chosen)  # 未編碼部件
            ids_map[ch] = chosen
    return ids_map


def expand_components(ch, ids_map, memo, stack=None):
    """遞迴展開部件,含中間層,回傳 Counter"""
    if ch in memo:
        return memo[ch]
    if stack is None:
        stack = set()
    stack.add(ch)
    counter = Counter()
    ids = ids_map.get(ch, ch)
    tokens = [t for t in ids if t not in IDC and CJK_RE.match(t) and t != ch]
    for t in tokens:
        counter[t] += 1
        if t not in stack:
            counter += expand_components(t, ids_map, memo, stack)
    stack.discard(ch)
    memo[ch] = counter
    return counter


def load_cns_strokes():
    """CNS11643 全字庫:CNS碼→台灣官方筆畫,經對照表轉成 unicode char→筆畫。
    同一字多個 CNS 碼時取字面較前者(常用字面優先)。"""
    cns_dir = os.path.join(HERE, "cns")
    strokes = {}
    with open(os.path.join(cns_dir, "CNS_stroke.txt"), encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) == 2 and parts[1].isdigit():
                strokes[parts[0]] = int(parts[1])
    out = {}
    best_code = {}
    for fname in ("CNS2UNICODE_BMP.txt", "CNS2UNICODE_U2.txt", "CNS2UNICODE_U15.txt"):
        path = os.path.join(cns_dir, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) != 2 or parts[0] not in strokes:
                    continue
                try:
                    ch = chr(int(parts[1], 16))
                except ValueError:
                    continue
                if ch not in best_code or parts[0] < best_code[ch]:
                    best_code[ch] = parts[0]
                    out[ch] = strokes[parts[0]]
    return out


def main():
    print("讀取 Unihan …")
    irg = os.path.join(UNIHAN, "Unihan_IRGSources.txt")
    rs = parse_unihan_field(irg, "kRSUnicode")
    total = parse_unihan_field(irg, "kTotalStrokes")
    big5 = parse_unihan_field(os.path.join(UNIHAN, "Unihan_OtherMappings.txt"), "kBigFive")
    mandarin = parse_unihan_field(os.path.join(UNIHAN, "Unihan_Readings.txt"), "kMandarin")
    grade = parse_unihan_field(os.path.join(UNIHAN, "Unihan_DictionaryLikeData.txt"),
                               "kGradeLevel")  # 香港小學字級 1-6,粗略常用度

    # 台灣官方現代筆畫:CNS11643 全字庫(kTotalStrokes 是中國算法,阝辶艹者等差 1-2 劃)
    tw_strokes = load_cns_strokes()

    with open(os.path.join(HERE, "overrides.json"), encoding="utf-8") as f:
        ov = json.load(f)
    overrides = dict(ov.get("kangxi_overrides", {}))
    if ov.get("numerals_by_value", True):
        overrides.update(ov.get("numerals", {}))

    print("解析 IDS …")
    ids_map = load_ids(os.path.join(HERE, "ids.txt"))
    memo = {}

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""CREATE TABLE chars(
        char TEXT PRIMARY KEY, kangxi INTEGER, modern INTEGER,
        radical TEXT, radical_num INTEGER,
        pinyin TEXT, pinyin_plain TEXT, big5 TEXT, big5level INTEGER,
        grade INTEGER)""")
    cur.execute("CREATE TABLE components(char TEXT, comp TEXT, count INTEGER)")
    cur.execute("CREATE INDEX idx_comp_char ON components(char)")
    cur.execute("CREATE INDEX idx_comp_comp ON components(comp)")

    n_chars = 0
    for ch, code in big5.items():
        if ch not in rs:
            continue
        # Big5 分級:A440–C67E 常用(1),C940–F9D5 次常用(2)
        code = code.strip("'\" ")
        c = int(code, 16)
        level = 1 if c <= 0xC67E else 2
        first = rs[ch].split(" ")[0]
        rad_s, res_s = first.split(".")
        rad_num = int(rad_s.rstrip("'"))
        kangxi = radical_strokes(rad_num) + int(res_s)
        if ch in overrides:
            kangxi = overrides[ch]
        # 現代筆畫:台灣全字庫優先,查無再退回 Unihan kTotalStrokes
        modern = tw_strokes.get(ch) or int(total.get(ch, "0").split(" ")[0])
        pys = mandarin.get(ch, "").split(" ")
        py = pys[-1] if pys else ""  # 兩值時後者為台灣讀音
        g = grade.get(ch)
        cur.execute("INSERT OR REPLACE INTO chars VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (ch, kangxi, modern, RADICALS[rad_num - 1], rad_num,
                     py, strip_tone(py), code, level,
                     int(g) if g else None))
        comps = expand_components(ch, ids_map, memo)
        rows = [(ch, ch, 1)] + [(ch, comp, cnt) for comp, cnt in comps.items()]
        cur.executemany("INSERT INTO components VALUES(?,?,?)", rows)
        n_chars += 1

    con.commit()
    n_comp = cur.execute("SELECT COUNT(*) FROM components").fetchone()[0]
    print(f"完成:{n_chars} 字、{n_comp} 部件關聯 → {DB_PATH}")

    # 驗證常見字筆畫
    expected = {"鴻": 17, "酒": 10, "淑": 12, "芳": 10, "育": 10, "琳": 13,
                "陳": 16, "林": 8, "黃": 12, "蔡": 17, "鄭": 19, "謝": 17,
                "洪": 10, "郭": 15, "游": 13, "雅": 12, "婷": 12, "怡": 9,
                "君": 7, "志": 7, "明": 8, "俊": 9, "宏": 7, "龍": 16,
                "馬": 10, "駿": 17, "王": 4, "一": 1, "十": 10}
    bad = []
    for ch, exp in expected.items():
        row = cur.execute("SELECT kangxi FROM chars WHERE char=?", (ch,)).fetchone()
        got = row[0] if row else None
        if got != exp:
            bad.append(f"{ch}: 期望{exp} 得到{got}")
    if bad:
        print("⚠ 筆畫驗證失敗:", "; ".join(bad))
    else:
        print(f"✓ {len(expected)} 個驗證字康熙筆畫全部正確")

    # 驗證台灣現代筆畫(教育部國語辭典標準)
    # 注意:台灣標準字體「者」無點 → 現代 8 劃(康熙舊字形有點才是 9)
    expected_tw = {"陳": 11, "華": 12, "都": 11, "草": 10, "芳": 8, "蔡": 15,
                   "道": 13, "郭": 11, "黃": 12, "者": 8, "建": 9, "蓮": 15,
                   "睿": 14, "程": 12, "方": 4, "駿": 17}
    bad_tw = []
    for ch, exp in expected_tw.items():
        row = cur.execute("SELECT modern FROM chars WHERE char=?", (ch,)).fetchone()
        got = row[0] if row else None
        if got != exp:
            bad_tw.append(f"{ch}: 期望{exp} 得到{got}")
    if bad_tw:
        print("⚠ 台灣現代筆畫驗證失敗:", "; ".join(bad_tw))
    else:
        print(f"✓ {len(expected_tw)} 個驗證字台灣現代筆畫全部正確")
    con.close()
    if bad or bad_tw:
        sys.exit(1)  # CI 品質關卡:驗證失敗不部署


if __name__ == "__main__":
    main()
