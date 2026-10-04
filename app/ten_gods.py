"""十神關係與使用者約定的五格尾數模型；不是老師完整命名算法。"""
from . import wuge

STEMS = '甲乙丙丁戊己庚辛壬癸'
ELEMENTS = '木火土金水'
GODS = ('比肩', '劫財', '食神', '傷官', '偏財', '正財', '偏官', '正官', '偏印', '正印')
CAUTIONS = ('傷官', '劫財')


def ten_god(reference, target):
    """以 reference 為日主，按五行生剋與陰陽判定 target 十神。"""
    a, b = STEMS.index(reference), STEMS.index(target)
    relation = (b // 2 - a // 2) % 5
    return GODS[relation * 2 + (a % 2 != b % 2)]


def stem_of(number):
    return STEMS[(number % 10 - 1) % 10]


def name_profile(surname_strokes, given_strokes):
    grids = wuge.five_grids(surname_strokes, given_strokes)
    reference = stem_of(grids['人格']['num'])
    entries = []
    for label in ('天格', '人格', '地格', '外格', '總格'):
        number = grids[label]['num']
        stem = stem_of(number)
        god = None if label == '人格' else ten_god(reference, stem)
        entries.append(dict(label=label, number=number, digit=number % 10, stem=stem,
                            element=ELEMENTS[STEMS.index(stem) // 2], ten_god=god,
                            caution=god in CAUTIONS))
    return dict(reference=reference, grids=entries, zong_ten_god=entries[-1]['ten_god'],
                has_caution=any(e['caution'] for e in entries),
                model='五格尾數模型（依對話推導）；康熙筆畫、人格為後天日主')


def natal_profile(pillars, day_master):
    if day_master is None:
        return dict(available=False, reference=None, stem_counts=None, hidden_counts=None,
                    pillars=[], note='日主尚未確定，無法計算十神；請補出生時間。')
    reference = day_master['stem']
    stem_counts, hidden_counts = dict.fromkeys(GODS, 0), dict.fromkeys(GODS, 0)
    entries = []
    for p in pillars:
        if p['ganzhi'] is None:
            entries.append(dict(label=p['label'], stem=None, ten_god=None, hidden=[]))
            continue
        stem = p['ganzhi'][0]
        god = None if p['key'] == 'day' else ten_god(reference, stem)
        if god:
            stem_counts[god] += 1
        hidden = []
        for h in p['hidden_stems']:
            hg = ten_god(reference, h['stem'])
            hidden_counts[hg] += 1
            hidden.append(dict(stem=h['stem'], ten_god=hg))
        entries.append(dict(label=p['label'], stem=stem, ten_god=god, hidden=hidden))
    return dict(available=True, reference=reference, stem_counts=stem_counts,
                hidden_counts=hidden_counts, pillars=entries,
                note='以出生日干為基準；日主本身不計入比肩。天干與藏干分開計次，不加權，次數不代表旺衰或應補項目。')
