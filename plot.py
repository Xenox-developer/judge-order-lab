"""Render only audited metric counts; no model calls or statistical fitting."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
audit=json.loads((ROOT/'results/audit.json').read_text())
assert audit['passed'] and audit['calls']==48
models=['qwen2.5:7b','qwen3:8b']
labels=['Qwen2.5 7B','Qwen3 8B']
metrics=[('main_correct','Correct judgments',16,'Judgments'),
         ('consistent_pair','Consistent pairs',8,'Pairs'),
         ('changed_pair','Changed decisions',8,'Pairs'),
         ('control_correct','Correct TIE controls',8,'Judgments')]
with plt.rc_context({'font.family':'DejaVu Sans','font.size':14,'svg.fonttype':'none'}):
    fig,axes=plt.subplots(2,2,figsize=(10.8,8),layout='constrained')
    for index,(ax,(key,title,n,unit)) in enumerate(zip(axes.flat,metrics)):
        values=[audit['summary'][m][key] for m in models]
        bars=ax.barh(range(2),values,height=.52,color=['#005A8D','#974B16'])
        bars[1].set_hatch('//')
        ax.set_yticks(range(2),labels if index%2==0 else ['',''])
        ax.invert_yaxis()
        ax.set_xlim(0,n*1.32)
        ax.set_xticks([0,n/2,n],[str(0),str(n//2),str(n)])
        ax.set_title(title,fontweight='bold',fontsize=15,pad=15)
        ax.set_xlabel(unit)
        for y,value in enumerate(values):
            ax.text(value+n*.04,y,f'{value}/{n}',va='center',fontsize=16)
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='x',alpha=.18)
        ax.set_axisbelow(True)
    for suffix in ['png','svg']:
        fig.savefig(ROOT/f'results/judge-order.{suffix}',dpi=170,facecolor='white')
    plt.close(fig)
(ROOT/'evidence/chart-environment.json').write_text(json.dumps({'matplotlib':matplotlib.__version__,'source':'results/audit.json','script':'plot.py','transform':'Raw audited numerators with fixed denominators. No smoothing, normalization, confidence intervals or missing-case exclusion.','destination':'LinkedIn results image; factual metric/model names, units and counts only.'},indent=2)+'\n')
