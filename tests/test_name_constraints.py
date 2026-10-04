import io
import json
import unittest
from urllib.parse import urlencode

from app import core
from server import Handler


class ConstraintTests(unittest.TestCase):
    def recommend(self, **kwargs):
        return core.suggest_names('郭', luck=0, limit=1000, **kwargs)

    def test_exact_kangxi_first_and_second(self):
        for fixed, target in [({'fixed_first': '柏'}, 31), ({'fixed_second': '昇'}, 32)]:
            d = self.recommend(max_strokes=target, strokes_operator='=', strokes_basis='kangxi', **fixed)
            self.assertGreater(d['total'], 1)
            for n in d['names']:
                self.assertEqual(n['zong'], target)
                if 'fixed_first' in fixed:
                    self.assertTrue(n['given'].startswith('柏'))
                else:
                    self.assertTrue(n['given'].endswith('昇'))
        d = self.recommend(fixed_first='柏', fixed_second='均', max_strokes=31,
                           strokes_operator='=', strokes_basis='kangxi')
        self.assertEqual([n['given'] for n in d['names']], ['柏均'])

    def test_modern_exact_and_legacy_upper_bound(self):
        exact = self.recommend(fixed_first='柏', max_strokes=27, strokes_operator='=')
        upper = self.recommend(fixed_first='柏', max_strokes=27)
        self.assertTrue(exact['names'])
        self.assertTrue(all(n['total_modern'] == 27 for n in exact['names']))
        self.assertTrue(all(n['total_modern'] <= 27 for n in upper['names']))
        self.assertGreaterEqual(upper['total'], exact['total'])
        self.assertTrue(any(n['zong'] != 27 for n in exact['names']))

    def test_likes_bans_and_no_relaxation_of_locks(self):
        self.assertEqual([n['given'] for n in self.recommend(fixed_first='柏', like='均')['names']], ['柏均'])
        self.assertNotIn('柏均', [n['given'] for n in self.recommend(fixed_first='柏', dislike='均')['names']])
        self.assertEqual(self.recommend(fixed_first='柏', fixed_second='均', max_strokes=32,
                                       strokes_operator='=', strokes_basis='kangxi')['total'], 0)
        self.assertEqual(self.recommend(fixed_first='柏', fixed_second='均', like='昇')['total'], 0)

    def test_single_name_and_validation(self):
        d = self.recommend(length=1, fixed_first='柏')
        self.assertTrue(all(n['given'] == '柏' for n in d['names']))
        for kwargs in [dict(length=1, fixed_second='昇'), dict(fixed_first='柏均'),
                       dict(fixed_second='A'), dict(fixed_first='柏', dislike='柏'),
                       dict(strokes_operator='>'), dict(strokes_basis='bad'),
                       dict(max_strokes=-1), dict(max_strokes=2.5), dict(strokes_operator='=')]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.recommend(**kwargs)

    def test_next_batch_obeys_locks(self):
        args = dict(fixed_first='柏', max_strokes=31, strokes_operator='=', strokes_basis='kangxi')
        first = core.suggest_names('郭', luck=0, limit=3, **args)
        seen = {n['given'] for n in first['names']}
        second = core.suggest_names('郭', luck=0, limit=3, exclude=','.join(seen), **args)
        self.assertEqual(len(second['names']), 3)
        self.assertFalse(seen & {n['given'] for n in second['names']})
        self.assertTrue(all(n['given'].startswith('柏') and n['zong'] == 31 for n in second['names']))

    def test_http_get_and_post(self):
        params = dict(surname='郭', fixed_first='柏', fixed_second='均', max_strokes=31,
                      strokes_operator='=', strokes_basis='kangxi', luck=0, zong_elements='木')
        for method in ('GET', 'POST'):
            handler = object.__new__(Handler)
            handler.path = '/api/suggest-names'
            result = []
            handler._json = lambda obj, status=200: result.append((status, obj))
            if method == 'GET':
                handler.path += '?' + urlencode(params)
                handler.do_GET()
            else:
                body = json.dumps(params).encode()
                handler.headers = {'Content-Length': str(len(body))}
                handler.rfile = io.BytesIO(body)
                handler.do_POST()
            self.assertEqual(result[0][0], 200)
            self.assertEqual([n['given'] for n in result[0][1]['names']], ['柏均'])

class ElementTests(unittest.TestCase):
    def test_elements_intersect_strokes_and_fixed_position(self):
        args = dict(surname='郭', fixed_first='柏', strokes_basis='kangxi',
                    strokes_operator='=', max_strokes=31, luck=0)
        good = core.suggest_names(zong_elements='木水', **args)
        self.assertTrue(good['names'])
        self.assertTrue(all(n['zong_element'] == '木' and n['zong'] == 31 and n['given'][0] == '柏' for n in good['names']))
        self.assertEqual(core.suggest_names(zong_elements='水', **args)['total'], 0)
        modern = core.suggest_names('郭', fixed_first='柏', max_strokes=27, strokes_operator='=', zong_elements='木水')
        self.assertTrue(modern['names'])
        self.assertTrue(all(n['total_modern'] == 27 and core.wuge.wuxing_of(n['zong']) in '木水' for n in modern['names']))
        for bad in ('木,水', '風', None, ['木']):
            with self.assertRaises(ValueError):
                core.suggest_names('郭', zong_elements=bad)

    def test_count_suggestion_is_not_favorable_elements(self):
        d = core.analyze_bazi('2022-08-28', '01:50')
        self.assertEqual(d['count_suggestion']['elements'], ['木', '火', '金'])
        self.assertIsNone(d['naming']['favorable_elements'])
        self.assertFalse(d['count_suggestion']['provisional'])
        d = core.analyze_bazi('2026-02-04')
        self.assertTrue(d['count_suggestion']['provisional'])
        self.assertEqual(d['count_suggestion']['elements'], ['木', '火', '水'])

    def test_all_python_modules_compile(self):
        from pathlib import Path
        for path in list(Path('app').glob('*.py')) + [Path('server.py')]:
            compile(path.read_text(), str(path), 'exec')
