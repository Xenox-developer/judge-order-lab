"""Sequential, fixed local requests; no model pulling, repair or retry."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

from evaluation import passes, gold, score, summarize
from request import build

ROOT=Path(__file__).resolve().parent
BASE='http://127.0.0.1:11434'


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def api(route,body=None,timeout=90):
    assert route in ['/api/tags','/api/show','/api/version','/api/ps','/api/chat','/api/generate']
    data=None if body is None else json.dumps(body,allow_nan=False).encode()
    req=urllib.request.Request(BASE+route,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.load(r)


def idle(allowed):
    deadline=time.monotonic()+20
    while True:
        resident=api('/api/ps').get('models',[])
        if all(x.get('name',x.get('model')) in allowed for x in resident):
            return resident
        if time.monotonic()>=deadline:
            raise RuntimeError('Other model resident; do not evict or measure in parallel')
        time.sleep(.25)


def freeze():
    assert not (ROOT/'frozen.json').exists(),'Already frozen'
    models=['qwen2.5:7b','qwen3:8b']
    available={x['name']:x for x in api('/api/tags')['models']}
    assert all(m in available for m in models),'Required installed model absent; do not pull'
    manifest={m:dict(installed=available[m],show=api('/api/show',{'model':m})) for m in models}
    dump(ROOT/'evidence/models.json',manifest)
    dump(ROOT/'evidence/versions.json',dict(ollama=api('/api/version'),python=sys.version,platform=platform.platform(),invariant=subprocess.check_output(['invariant','--version'],text=True).strip()))
    tasks={t['id']:t for t in json.loads((ROOT/'tasks.json').read_text())}
    cases=json.loads((ROOT/'cases.json').read_text())
    for t in tasks.values():
        assert passes(t['valid'],t) and passes(t['alternative'],t) and not passes(t['buggy'],t),t['id']
    truths={c['id']:gold(c,tasks) for c in cases}
    assert all(v==('A' if c['order']=='canonical' else 'B') if c['kind']=='main' else v=='TIE' for c in cases for v in [truths[c['id']]])
    dump(ROOT/'evidence/gold.json',truths)
    assert score('{"winner":"A","reason":"control"}','A')['correct']
    assert not score('{"winner":"B","reason":"control"}','A')['correct']
    assert not score('invalid JSON','A')['schema_valid']
    dump(ROOT/'evidence/scorer-controls.json',dict(positive=True,negative=True,malformed=True))
    files=['PROTOCOL.md','tasks.json','cases.json','schedule.json','make_fixtures.py','request.py','evaluation.py','tests/run_checks.py','run.py','audit.py','evidence/models.json','evidence/versions.json','evidence/gold.json','evidence/scorer-controls.json']
    dump(ROOT/'frozen.json',dict(frozen_at=datetime.now(timezone.utc).isoformat(),planned_calls=48,sha256={f:sha(ROOT/f) for f in files}))
    print('Frozen 48 calls and',len(files),'scientific files',flush=True)


def measure(folder):
    if folder.exists():
        raise FileExistsError('Do not overwrite or replay a measured/uncertain run')
    frozen=json.loads((ROOT/'frozen.json').read_text())
    for name,digest in frozen['sha256'].items():
        assert sha(ROOT/name)==digest,name
    manifest=json.loads((ROOT/'evidence/models.json').read_text())
    installed={m['name']:m['digest'] for m in api('/api/tags')['models']}
    assert all(installed[m]==v['installed']['digest'] for m,v in manifest.items())
    tasks={t['id']:t for t in json.loads((ROOT/'tasks.json').read_text())}
    cases={c['id']:c for c in json.loads((ROOT/'cases.json').read_text())}
    schedule=json.loads((ROOT/'schedule.json').read_text())
    truths=json.loads((ROOT/'evidence/gold.json').read_text())
    folder.mkdir(parents=True)
    (folder/'issued').mkdir()
    state=dict(status='running',planned=48,completed=0,started_at=datetime.now(timezone.utc).isoformat(),implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),frozen_sha256=sha(ROOT/'frozen.json'))
    dump(folder/'run.json',state)
    prior=None
    rows=[]
    try:
        idle(set())
        with (folder/'raw.jsonl').open('x') as output:
            for cell in schedule:
                if prior is not None and prior!=cell['model']:
                    dump(folder/'unload-between.json',api('/api/generate',dict(model=prior,keep_alive=0,stream=False)))
                    idle(set())
                resident=idle({cell['model']})
                case=cases[cell['case_id']]
                request=build(cell,case,tasks[case['task_id']])
                record=dict(cell,task_id=case['task_id'],kind=case['kind'],order=case['order'],request=request,resident_before=resident,issued_at=datetime.now(timezone.utc).isoformat(),status='issued',request_sha256=hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
                dump(folder/'issued'/(cell['id']+'.json'),record)
                start=time.monotonic()
                prior=cell['model']
                try:
                    response=api('/api/chat',request)
                    record.update(response=response,wall_seconds=time.monotonic()-start,status='responded',score=score(response['message']['content'],truths[case['id']]))
                    assert response.get('done') is True and response.get('model')==cell['model'],'Unexpected terminal model metadata'
                except Exception as exc:
                    record.update(status='error',error=type(exc).__name__,detail=str(exc)[:500],wall_seconds=time.monotonic()-start)
                    output.write(json.dumps(record,ensure_ascii=False)+'\n');output.flush()
                    raise
                output.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n');output.flush()
                rows.append(record)
                state['completed']+=1
                dump(folder/'run.json',state)
                print(json.dumps(dict(completed=state['completed'],total=48,model=cell['model'],case_id=cell['case_id'])),flush=True)
        dump(folder/'summary.json',{m:summarize([r for r in rows if r['model']==m]) for m in manifest})
        state['status']='completed'
    except Exception as exc:
        state.update(status='incomplete',error=type(exc).__name__,detail=str(exc)[:500])
        raise
    finally:
        state['finished_at']=datetime.now(timezone.utc).isoformat()
        dump(folder/'run.json',state)
        if prior:
            dump(folder/'unload-final.json',api('/api/generate',dict(model=prior,keep_alive=0,stream=False)))


if __name__=='__main__':
    if sys.argv[1]=='freeze':
        freeze()
    elif sys.argv[1]=='measure':
        measure(ROOT/(sys.argv[2] if len(sys.argv)>2 else 'results/primary'))
    else:
        raise SystemExit('Use freeze or measure')
