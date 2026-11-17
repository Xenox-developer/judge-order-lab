import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parent


def fixture(name, contract, valid, buggy, alternative, tests):
    return dict(id=name, contract=contract, valid=valid, buggy=buggy, alternative=alternative, tests=tests, preserve_inputs=name in ('dedup','merge'))


TASKS = [
    fixture('chunks', 'solve(items, n) splits a list into consecutive lists of at most n items, keeping a final short group. Return [] for empty input. For n <= 0 raise ValueError (a subclass is allowed).',
        'def solve(items, n):\n    if n <= 0:\n        raise ValueError(n)\n    return [items[i:i+n] for i in range(0, len(items), n)]\n',
        'def solve(items, n):\n    if n <= 0:\n        raise ValueError(n)\n    return [items[i:i+n] for i in range(0, len(items)-n+1, n)]\n',
        'def solve(items, n):\n    if n < 1:\n        raise ValueError(n)\n    result = []\n    while items:\n        result.append(items[:n])\n        items = items[n:]\n    return result\n',
        [dict(args=[[1,2,3,4,5],2], expected=[[1,2],[3,4],[5]]),dict(args=[[],3],expected=[]),dict(args=[[1],4],expected=[[1]]),dict(args=[[1],0],error='ValueError')]),
    fixture('dedup', 'solve(items) returns unique integers in first-occurrence order. Do not sort. Input is a list; do not mutate it.',
        'def solve(items):\n    result = []\n    for item in items:\n        if item not in result:\n            result.append(item)\n    return result\n',
        'def solve(items):\n    return sorted(set(items))\n',
        'def solve(items):\n    return list(dict.fromkeys(items))\n',
        [dict(args=[[3,1,3,2]],expected=[3,1,2]),dict(args=[[]],expected=[]),dict(args=[[-1,0,-1]],expected=[-1,0])]),
    fixture('overlap', 'solve(a, b) returns whether half-open intervals [a[0],a[1]) and [b[0],b[1]) overlap. Each interval has strictly increasing integer endpoints. Touching endpoints do not overlap.',
        'def solve(a, b):\n    return a[0] < b[1] and b[0] < a[1]\n',
        'def solve(a, b):\n    return a[0] <= b[1] and b[0] <= a[1]\n',
        'def solve(a, b):\n    return max(a[0], b[0]) < min(a[1], b[1])\n',
        [dict(args=[[0,2],[2,4]],expected=False),dict(args=[[0,3],[2,5]],expected=True),dict(args=[[-3,-1],[0,2]],expected=False)]),
    fixture('clamp', 'solve(value, lo, hi) clamps an integer value to the inclusive integer range lo..hi, where lo <= hi. Return the nearest endpoint when outside; otherwise return value.',
        'def solve(value, lo, hi):\n    return min(hi, max(lo, value))\n',
        'def solve(value, lo, hi):\n    return max(hi, min(lo, value))\n',
        'def solve(value, lo, hi):\n    if value < lo:\n        return lo\n    if value > hi:\n        return hi\n    return value\n',
        [dict(args=[5,0,10],expected=5),dict(args=[-2,0,10],expected=0),dict(args=[12,0,10],expected=10),dict(args=[3,3,3],expected=3)]),
    fixture('merge', 'solve(base, override) returns a new dictionary with override values taking precedence, including None, False, zero and empty strings. Do not modify either input dictionary.',
        'def solve(base, override):\n    result = base.copy()\n    result.update(override)\n    return result\n',
        'def solve(base, override):\n    result = base.copy()\n    result.update({k:v for k,v in override.items() if v})\n    return result\n',
        'def solve(base, override):\n    return {**base, **override}\n',
        [dict(args=[{'x':1},{'x':None}],expected={'x':None}),dict(args=[{'x':True,'y':2},{'x':False,'y':0,'z':''}],expected={'x':False,'y':0,'z':''}),dict(args=[{},{}],expected={})]),
    fixture('descendant', 'solve(root, path) checks lexical POSIX containment: root and path are absolute paths, may contain .., and no symlinks are involved. Return True only for a strict descendant after normalizing dot components; root itself is False. No filesystem access.',
        'import posixpath\ndef solve(root, path):\n    root = posixpath.normpath(root)\n    path = posixpath.normpath(path)\n    return path != root and posixpath.commonpath([root, path]) == root\n',
        'import posixpath\ndef solve(root, path):\n    root = posixpath.normpath(root)\n    path = posixpath.normpath(path)\n    return path != root and path.startswith(root)\n',
        'import posixpath\ndef solve(root, path):\n    root = posixpath.normpath(root)\n    path = posixpath.normpath(path)\n    return path != root and path.startswith(root.rstrip("/") + "/")\n',
        [dict(args=['/safe','/safe2/x'],expected=False),dict(args=['/safe','/safe/x'],expected=True),dict(args=['/safe','/safe/../outside'],expected=False),dict(args=['/safe','/safe'],expected=False),dict(args=['/','/a'],expected=True)]),
    fixture('utf8_size', 'solve(text) returns the number of bytes in the UTF-8 encoding of a Python string. It is not the number of Unicode code points.',
        'def solve(text):\n    return len(text.encode("utf-8"))\n',
        'def solve(text):\n    return len(text)\n',
        'def solve(text):\n    encoded = bytes(text, encoding="utf-8")\n    return len(encoded)\n',
        [dict(args=['café'],expected=5),dict(args=['🙂'],expected=4),dict(args=[''],expected=0),dict(args=['abc'],expected=3)]),
    fixture('expiry', 'solve(now, expires) returns True exactly when a timestamp is expired: expiration occurs at expires, including the equality boundary. Both arguments are integer timestamps.',
        'def solve(now, expires):\n    return now >= expires\n',
        'def solve(now, expires):\n    return now > expires\n',
        'def solve(now, expires):\n    return not now < expires\n',
        [dict(args=[10,10],expected=True),dict(args=[9,10],expected=False),dict(args=[11,10],expected=True)])
]

CASES = []
for i, task in enumerate(TASKS):
    for order in ['canonical', 'reversed']:
        options = [task['valid'], task['buggy']]
        if order == 'reversed':
            options.reverse()
        CASES.append(dict(id=task['id']+'-'+order,task_id=task['id'],kind='main',order=order,options=options))
    both_valid = i < 4
    CASES.append(dict(id=task['id']+'-control',task_id=task['id'],kind='both_valid' if both_valid else 'both_buggy',order='control',options=[task['valid'],task['alternative']] if both_valid else [task['buggy'],task['buggy']]))

SCHEDULE = []
for model in ['qwen2.5:7b','qwen3:8b']:
    block = [dict(id=model.split(':')[0]+'-'+c['id'],model=model,case_id=c['id']) for c in CASES]
    random.Random(20261117).shuffle(block)
    SCHEDULE.extend(block)

if __name__ == '__main__':
    for name, value in [('tasks.json',TASKS),('cases.json',CASES),('schedule.json',SCHEDULE)]:
        (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
