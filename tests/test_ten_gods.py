import io
import json
import unittest
from urllib.parse import urlencode
from app import core, ten_gods
from app.bazi import LunarUtil
from server import Handler


class TenGodTests(unittest.TestCase):
    def test_all_stem_pairs_against_calendar_table(self):
        translate = {'正财':'正財', '偏财':'偏財', '伤官':'傷官', '劫财':'劫財', '七杀':'偏官'}
        for a in ten_gods.STEMS:
            for b in ten_gods.STEMS:
                expected = LunarUtil.SHI_SHEN[a+b]
                self.assertEqual(ten_gods.ten_god(a,b), translate.get(expected, expected))
        self.assertEqual(''.join(ten_gods.stem_of(n) for n in range(1,11)), ten_gods.STEMS)
        self.assertEqual(ten_gods.stem_of(20), '癸')

    def test_conversation_examples(self):
        cases = [([9,7], '丁', ['食神','食神','偏財','正印']),
                 ([9,8], '丁', ['食神','正財','正官','偏印']),
                 ([5,12], '癸', ['偏官','正印','正財','食神']),
                 ([3,14], '辛', ['偏印','劫財','正印','偏財'])]
        for strokes, reference, expected in cases:
            p=ten_gods.name_profile([15],strokes)
            self.assertEqual(p['reference'],reference)
            self.assertEqual([g['ten_god'] for g in p['grids'] if g['label']!='人格'],expected)
        for surname,given in [([8,15],[9]),([8,15],[9,8]),([15],[9])]:
            p=ten_gods.name_profile(surname,given)
            self.assertEqual(len(p['grids']),5)
            self.assertIsNone(p['grids'][1]['ten_god'])

    def test_caution_and_filters(self):
        args=dict(surname='郭',fixed_first='士',fixed_second='嘉',luck=0)
        result=core.suggest_names(exclude_unfavorable=False,**args)['names'][0]
        self.assertEqual(result['sancai']['rating'],'大吉')
        self.assertTrue(result['name_ten_gods']['has_caution'])
        self.assertEqual(core.suggest_names(exclude_unfavorable=True,**args)['total'],0)
        self.assertEqual(core.suggest_names(zong_ten_gods='食神,偏財',exclude_unfavorable=False,**args)['total'],1)
        self.assertEqual(core.suggest_names(zong_ten_gods='食神',**args)['total'],0)
        # Ten-god and element constraints intersect; neither is relaxed.
        self.assertEqual(core.suggest_names(zong_ten_gods='偏財',zong_elements='水',**args)['total'],0)
        for kwargs in [dict(zong_ten_gods='無'),dict(zong_ten_gods=['食神']),dict(exclude_unfavorable='false')]:
            with self.assertRaises(ValueError): core.suggest_names('郭',**kwargs)

    def test_natal_uses_day_stem_and_separates_hidden(self):
        d=core.analyze_bazi('2026-09-25','21:30')['ten_gods']
        self.assertTrue(d['available'])
        self.assertEqual(sum(d['stem_counts'].values()),3)
        self.assertIsNone(d['pillars'][2]['ten_god'])
        self.assertGreater(sum(d['hidden_counts'].values()),3)
        partial=core.analyze_bazi('2026-09-25')['ten_gods']
        self.assertEqual(sum(partial['stem_counts'].values()),2)
        unknown=core.analyze_bazi('2026-09-25',day_boundary='zi')['ten_gods']
        self.assertFalse(unknown['available'])
        self.assertIsNone(unknown['stem_counts'])

    def test_http_get_and_post(self):
        for method in ['GET','POST']:
            args=dict(surname='郭',fixed_first='士',fixed_second='嘉',zong_ten_gods='偏財',exclude_unfavorable=True)
            h=object.__new__(Handler);result=[]
            h._json=lambda obj,status=200:result.append((status,obj))
            h.path='/api/suggest-names'
            if method=='GET':
                args['exclude_unfavorable']='true'
                h.path+='?'+urlencode(args);h.do_GET()
            else:
                data=json.dumps(args).encode();h.headers={'Content-Length':str(len(data))};h.rfile=io.BytesIO(data);h.do_POST()
            self.assertEqual(result[0][0],200)
            self.assertEqual(result[0][1]['total'],0)

class RelaxationTests(unittest.TestCase):
    def test_crown_name_requires_phonetic_relaxation(self):
        args=dict(surname='郭',fixed_first='冠',fixed_second='昇',luck=0)
        self.assertEqual(core.suggest_names(**args)['total'],0)
        d=core.suggest_names(relax_phonetic=True,required_ten_gods='食神,正財,正官,偏印',**args)
        self.assertEqual([n['given'] for n in d['names']],['冠昇'])
        self.assertLess(d['names'][0]['phonetic'],0)
        self.assertTrue(d['names'][0]['notes'])
        self.assertEqual(core.suggest_names(relax_zodiac=True,**args)['total'],0)
        self.assertEqual(core.suggest_names(relax_phonetic=True,required_ten_gods='食神,正財',**args)['total'],1)
        self.assertEqual(core.suggest_names(relax_phonetic=True,required_ten_gods='食神,比肩',**args)['total'],0)
        self.assertEqual(core.suggest_names(relax_phonetic=True,required_ten_gods='食神,比肩',match_all_ten_gods=False,**args)['total'],1)

    def test_zodiac_relaxation_keeps_warnings(self):
        c=core._conn()
        try:
            strict=core._candidate_pool(c,'馬','m')
            relaxed=core._candidate_pool(c,'馬','m',relax_zodiac=True)
            old={e['char'] for e in strict}
            self.assertTrue(old.issubset({e['char'] for e in relaxed}))
            added=[e for e in relaxed if e['char'] not in old]
            self.assertTrue(added)
            self.assertTrue(all(e['avoid_notes'] for e in added))
        finally: c.close()

    def test_unfavorable_default_and_invalid_values(self):
        args=dict(surname='郭',fixed_first='士',fixed_second='嘉')
        self.assertEqual(core.suggest_names(**args)['total'],0)
        self.assertEqual(core.suggest_names(exclude_unfavorable=False,**args)['total'],1)
        for kwargs in [dict(relax_zodiac='true'),dict(relax_phonetic=1),dict(required_ten_gods='星星'),dict(match_all_ten_gods=None)]:
            with self.assertRaises(ValueError): core.suggest_names('郭',**kwargs)

    def test_http_relaxation_and_force_match(self):
        for method in ['GET','POST']:
            args=dict(surname='郭',fixed_first='冠',fixed_second='昇',relax_phonetic=True,
                      relax_zodiac=True,required_ten_gods='食神,正財,正官,偏印',match_all_ten_gods=True)
            h=object.__new__(Handler);result=[]
            h._json=lambda obj,status=200:result.append((status,obj))
            h.path='/api/suggest-names'
            if method=='GET':
                args={k:('true' if v is True else v) for k,v in args.items()}
                h.path+='?'+urlencode(args);h.do_GET()
            else:
                data=json.dumps(args).encode();h.headers={'Content-Length':str(len(data))};h.rfile=io.BytesIO(data);h.do_POST()
            self.assertEqual(result[0][0],200)
            self.assertEqual(result[0][1]['total'],1)
            self.assertEqual(result[0][1]['names'][0]['given'],'冠昇')
