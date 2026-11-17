import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from evaluation import passes, gold, score, summarize

TASKS = {t['id']:t for t in json.loads((ROOT/'tasks.json').read_text())}
CASES = json.loads((ROOT/'cases.json').read_text())


def records(strategy='correct'):
    out=[]
    for case in CASES:
        if case['kind']!='main':
            winner='TIE'
        elif strategy=='correct':
            winner='A' if case['order']=='canonical' else 'B'
        elif strategy=='wrong':
            winner='B' if case['order']=='canonical' else 'A'
        else:
            winner=strategy
        expected=('A' if case['order']=='canonical' else 'B') if case['kind']=='main' else 'TIE'
        out.append({k:case[k] for k in ['task_id','kind','order']} | {'case_id':case['id'],'score':dict(schema_valid=True,winner=winner,correct=winner==expected)})
    return out


class Checks(unittest.TestCase):
    def test_execution_fixtures(self):
        for task in TASKS.values():
            self.assertIs(passes(task['valid'],task),True,task['id'])
            self.assertIs(passes(task['alternative'],task),True,task['id'])
            self.assertIs(passes(task['buggy'],task),False,task['id'])
        self.assertIs(passes('def solve(:',TASKS['chunks']),False)
        self.assertIs(passes('x = 1',TASKS['chunks']),False)

    def test_exception_subclass_and_mutation(self):
        child=TASKS['chunks']['valid'].replace('def solve','class Child(ValueError):\n    pass\n\ndef solve').replace('raise ValueError(n)','raise Child(n)')
        self.assertTrue(passes(child,TASKS['chunks']))
        self.assertFalse(passes(TASKS['chunks']['valid'].replace('raise ValueError(n)','raise TypeError(n)'),TASKS['chunks']))
        mutated='def solve(items):\n    result = list(dict.fromkeys(items))\n    items.clear()\n    return result\n'
        self.assertFalse(passes(mutated,TASKS['dedup']))

    def test_gold_main_and_controls(self):
        for c in CASES:
            expected=('A' if c['order']=='canonical' else 'B') if c['kind']=='main' else 'TIE'
            self.assertEqual(gold(c,TASKS),expected,c['id'])

    def test_strict_json(self):
        self.assertEqual(score('{"winner":"A","reason":"edge case"}','A'),dict(schema_valid=True,winner='A',correct=True))
        self.assertEqual(score('{"winner":"B","reason":"wrong"}','A'),dict(schema_valid=True,winner='B',correct=False))
        for text in ['[]','null','oops','{"winner":"a","reason":"x"}','{"winner":true,"reason":"x"}','{"winner":"A"}','{"winner":"A","reason":5}','{"winner":"A","reason":"x","extra":1}']:
            self.assertEqual(score(text,'A'),dict(schema_valid=False,winner=None,correct=False))

    def test_correct_pairs(self):
        s=summarize(records())
        for key,n in [('schema_valid',24),('main_correct',16),('control_correct',8),('correct_when_valid_first',8),('correct_when_valid_second',8),('consistent_pair',8),('both_correct_pair',8),('both_valid',4),('both_buggy',4),('changed_pair',0),('invalid_pair',0),('consistent_wrong_pair',0),('persistent_tie_pair',0),('always_A_pair',0),('always_B_pair',0),('total_calls',24),('main_calls',16),('control_calls',8),('pairs',8)]:
            self.assertEqual(s[key],n,key)

    def test_positional_pairs(self):
        for choice,first,second in [('A',8,0),('B',0,8)]:
            s=summarize(records(choice))
            self.assertEqual(s['main_correct'],8)
            self.assertEqual(s['changed_pair'],8)
            self.assertEqual(s['consistent_pair'],0)
            self.assertEqual(s['always_'+choice+'_pair'],8)
            self.assertEqual(s['correct_when_valid_first'],first)
            self.assertEqual(s['correct_when_valid_second'],second)

    def test_consistent_wrong_and_tie(self):
        s=summarize(records('wrong'))
        self.assertEqual(s['consistent_pair'],8)
        self.assertEqual(s['consistent_wrong_pair'],8)
        self.assertEqual(s['main_correct'],0)
        s=summarize(records('TIE'))
        self.assertEqual(s['persistent_tie_pair'],8)
        self.assertEqual(s['consistent_pair'],8)
        self.assertEqual(s['both_correct_pair'],0)

    def test_invalid_missing_and_duplicate(self):
        r=records()
        r[0]['score']=dict(schema_valid=False,winner=None,correct=False)
        s=summarize(r)
        self.assertEqual(s['invalid_pair'],1)
        self.assertEqual(s['consistent_pair'],7)
        self.assertEqual(s['schema_valid'],23)
        for broken in [r[:-1],r+[copy.deepcopy(r[0])],r[:-1]+[copy.deepcopy(r[0])]]:
            with self.assertRaises(ValueError):
                summarize(broken)


if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    Path('check-report.json').write_text(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),passed=r.wasSuccessful())))
    raise SystemExit(not r.wasSuccessful())
