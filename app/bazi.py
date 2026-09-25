"""八字基礎排盤。UTC+8 標準時；不以五行個數推斷喜用神。"""
from datetime import datetime
from pathlib import Path
import re
import sys

_ARCHIVE = str(Path(__file__).resolve().parent.parent / "vendor" / "lunar_python-1.4.8.zip")
if _ARCHIVE not in sys.path:
    sys.path.insert(0, _ARCHIVE)
from lunar_python import Solar
from lunar_python.util import LunarUtil

ELEMENTS = "木火土金水"
PARTS = (("year", "Year", "年柱"), ("month", "Month", "月柱"),
         ("day", "Day", "日柱"), ("hour", "Time", "時柱"))
IMAGERY = {"木": "草木、生長、仁和", "火": "光明、溫暖、明朗", "土": "安定、承載、信實",
           "金": "堅毅、精純、果決", "水": "涵養、流動、智慧"}


def _chart(date, time, day_boundary, second=0):
    dt = datetime.strptime(date + " " + time, "%Y-%m-%d %H:%M")
    chart = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, second).getLunar().getEightChar()
    chart.setSect(2 if day_boundary == "midnight" else 1)
    return chart


def analyze_bazi(birth_date, birth_time=None, timezone="UTC+08:00", day_boundary="midnight"):
    """Return stable pillars only; unknown-time boundary alternatives remain explicit."""
    if not isinstance(birth_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", birth_date):
        raise ValueError("請輸入西元出生日期，格式為 YYYY-MM-DD。")
    try:
        date = datetime.strptime(birth_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("出生日期不存在，請檢查年月日。")
    if not 1900 <= date.year <= 2100:
        raise ValueError("目前支援 1900–2100 年。")
    if timezone != "UTC+08:00":
        raise ValueError("目前僅支援 UTC+08:00 標準時間，尚未支援其他時區或夏令時間。")
    if day_boundary not in ("midnight", "zi"):
        raise ValueError("換日規則須為 midnight（00:00）或 zi（23:00）。")
    known_time = birth_time is not None and birth_time != ""
    if known_time and (not isinstance(birth_time, str) or
                       not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", birth_time)):
        raise ValueError("出生時間格式須為 HH:MM（00:00–23:59）。")
    charts = [_chart(birth_date, birth_time, day_boundary)] if known_time else [
        _chart(birth_date, "00:00", day_boundary), _chart(birth_date, "23:59", day_boundary, 59)]
    pillars = []
    counts = dict.fromkeys(ELEMENTS, 0)
    hidden_counts = dict.fromkeys(ELEMENTS, 0)
    warnings = []
    for key, method, label in PARTS:
        values = list(dict.fromkeys(getattr(c, "get" + method)() for c in charts))
        stable = len(values) == 1 and (key != "hour" or known_time)
        pillar = {"key": key, "label": label, "ganzhi": None,
                  "alternatives": values if key != "hour" and not stable else [],
                  "elements": [], "hidden_stems": []}
        if stable:
            gan, zhi = values[0]
            elements = [LunarUtil.WU_XING_GAN[gan], LunarUtil.WU_XING_ZHI[zhi]]
            hidden = [{"stem": g, "element": LunarUtil.WU_XING_GAN[g]}
                      for g in LunarUtil.ZHI_HIDE_GAN[zhi]]
            pillar.update(ganzhi=values[0], elements=elements, hidden_stems=hidden)
            for e in elements:
                counts[e] += 1
            for h in hidden:
                hidden_counts[h["element"]] += 1
        elif key != "hour":
            warnings.append(label + "在當日有交界，須提供出生時間才能確定。")
        pillars.append(pillar)
    if not known_time:
        warnings.insert(0, "未提供出生時間：不推算時柱；五行統計僅包含可確定的柱，不能視為完整八字。")
    day = pillars[2]["ganzhi"]
    day_master = None if day is None else {
        "stem": day[0], "element": LunarUtil.WU_XING_GAN[day[0]],
        "polarity": "陽" if "甲乙丙丁戊己庚辛壬癸".index(day[0]) % 2 == 0 else "陰"}
    absent = [e for e in ELEMENTS if counts[e] == 0]
    absent_including_hidden = [e for e in absent if hidden_counts[e] == 0]
    return {
        "birth_date": birth_date, "birth_time": birth_time if known_time else None,
        "timezone": timezone, "day_boundary": day_boundary,
        "complete": known_time, "pillars": pillars, "day_master": day_master,
        "element_counts": counts, "hidden_element_counts": hidden_counts,
        "visible_absent": absent, "absent_including_hidden": absent_including_hidden,
        "counted_characters": sum(counts.values()), "warnings": warnings,
        "method": "年柱以立春交節換年，月柱以十二節交節換月；採 UTC+8 標準時，未校正真太陽時或歷史夏令時間。",
        "count_method": "天干及地支本氣各計一次；藏干另列出現次數，不加權、不與表層個數合併，個數不代表旺衰。",
        "naming": {
            "status": "requires_interpretation", "favorable_elements": None,
            "summary": "五行未出現不等於喜用神。取名補益需再看月令、日主旺衰、干支作用與調候；本版不自動判定格局或喜用神。",
            "directions": [{"element": e, "imagery": IMAGERY[e]} for e in ELEMENTS],
            "next_step": "確認喜用五行後，可用相應字義作為取名方向，再搭配現有的音韻、字義與筆畫篩選。字義意象不等同於字的五行定論。"},
        "disclaimer": "八字屬傳統命理文化參考，不能據此確定個性、命運或保證改名效果。",
    }
