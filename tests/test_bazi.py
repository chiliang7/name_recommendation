import io
import json
import unittest

from app.bazi import analyze_bazi
from server import Handler


class BaziTests(unittest.TestCase):
    def test_reference_chart(self):
        # Published upstream reference: 6tail/lunar-python test/EightCharTest.py.
        d = analyze_bazi("2005-12-23", "08:37")
        self.assertEqual([p["ganzhi"] for p in d["pillars"]], ["乙酉", "戊子", "辛巳", "壬辰"])
        self.assertEqual(d["day_master"], {"stem": "辛", "element": "金", "polarity": "陰"})
        self.assertEqual(d["element_counts"], {"木": 1, "火": 1, "土": 2, "金": 2, "水": 2})
        self.assertIsNone(d["naming"]["favorable_elements"])

    def test_lichun_changes_year_and_month(self):
        before = analyze_bazi("2026-02-04", "04:01")["pillars"]
        after = analyze_bazi("2026-02-04", "04:03")["pillars"]
        self.assertEqual([p["ganzhi"] for p in before[:2]], ["乙巳", "己丑"])
        self.assertEqual([p["ganzhi"] for p in after[:2]], ["丙午", "庚寅"])
        self.assertEqual(before[2], after[2])

    def test_jingzhe_changes_only_month(self):
        before = analyze_bazi("2026-03-05", "21:58")["pillars"]
        after = analyze_bazi("2026-03-05", "22:00")["pillars"]
        self.assertEqual(before[1]["ganzhi"], "庚寅")
        self.assertEqual(after[1]["ganzhi"], "辛卯")
        self.assertEqual(before[0], after[0])

    def test_unknown_time_does_not_invent_pillars(self):
        d = analyze_bazi("2005-12-23")
        self.assertFalse(d["complete"])
        self.assertEqual(d["counted_characters"], 6)
        self.assertIsNone(d["pillars"][3]["ganzhi"])
        d = analyze_bazi("2026-02-04")
        self.assertIsNone(d["pillars"][0]["ganzhi"])
        self.assertEqual(d["pillars"][0]["alternatives"], ["乙巳", "丙午"])
        self.assertIsNone(d["pillars"][1]["ganzhi"])
        self.assertEqual(d["counted_characters"], 2)

    def test_day_boundary_options_and_midnight(self):
        early = analyze_bazi("1988-02-15", "22:59")
        late = analyze_bazi("1988-02-15", "23:30")
        zi = analyze_bazi("1988-02-15", "23:30", day_boundary="zi")
        next_day = analyze_bazi("1988-02-16", "00:00")
        self.assertEqual(early["pillars"][2]["ganzhi"], "庚子")
        self.assertEqual(late["pillars"][2]["ganzhi"], "庚子")
        self.assertEqual(late["pillars"][3]["ganzhi"], "戊子")
        self.assertEqual(zi["pillars"][2]["ganzhi"], "辛丑")
        self.assertEqual(zi["pillars"][2], next_day["pillars"][2])
        unknown = analyze_bazi("1988-02-15", day_boundary="zi")
        self.assertIsNone(unknown["day_master"])
        self.assertEqual(unknown["pillars"][2]["alternatives"], ["庚子", "辛丑"])

    def test_hidden_elements_are_separate(self):
        d = analyze_bazi("2022-08-28", "01:50")
        self.assertEqual([p["ganzhi"] for p in d["pillars"]], ["壬寅", "戊申", "癸丑", "癸丑"])
        self.assertIn("火", d["visible_absent"])
        self.assertNotIn("火", d["absent_including_hidden"])
        self.assertEqual(d["counted_characters"], 8)

    def test_validation_and_leap_day(self):
        self.assertTrue(analyze_bazi("2024-02-29", "00:00")["complete"])
        for date in (None, 2026, "", "2026-2-03", "2023-02-29", "2026-04-31", "1899-12-31", "2101-01-01"):
            with self.subTest(date=date), self.assertRaises(ValueError):
                analyze_bazi(date)
        for time in ("24:00", "12:60", "8:30", "12:30:00", 0, False, [], {}):
            with self.subTest(time=time), self.assertRaises(ValueError):
                analyze_bazi("2026-01-01", time)
        for kwargs in ({"timezone": "Asia/Taipei"}, {"timezone": None}, {"day_boundary": "invalid"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                analyze_bazi("2026-01-01", **kwargs)
        for time in (None, ""):
            self.assertFalse(analyze_bazi("2026-01-01", time)["complete"])


class ApiTests(unittest.TestCase):
    def post(self, payload):
        handler = object.__new__(Handler)
        body = json.dumps(payload).encode()
        handler.path = "/api/bazi"
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        result = []
        handler._json = lambda obj, status=200: result.append((status, obj))
        handler.do_POST()
        return result[0]

    def test_stdlib_success_and_validation(self):
        status, d = self.post({"birth_date": "2005-12-23", "birth_time": "08:37"})
        self.assertEqual(status, 200)
        self.assertEqual(d["pillars"][2]["ganzhi"], "辛巳")
        for payload in ({}, [], None, {"birth_date": "2026-02-30"}, {"birth_date": "2026-01-01", "birth_time": 0}):
            with self.subTest(payload=payload):
                status, d = self.post(payload)
                self.assertEqual(status, 400)
                self.assertIn("detail", d)


if __name__ == "__main__":
    unittest.main()
