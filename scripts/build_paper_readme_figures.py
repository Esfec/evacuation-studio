"""Redraw README figures using manuscript-reported statistics.

Run: python scripts/build_paper_readme_figures.py
Optional full export: python scripts/build_paper_readme_figures.py --exports
Source: media/readme/paper-source-data.json (reported rounding is retained).
Default output: five README PNGs. --exports writes PNG/SVG/PDF, CSVs and an
export manifest to ignored local-exports/paper-figures/. The archival audit remains reproducible via
build_formal_readme_figures.py. No API calls or simulation runs are made.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'media/readme'
SOURCE = OUT / 'paper-source-data.json'
INK, MUTED, GRID = '#283840', '#66747A', '#E6EBED'
BLUE, ROSE, GREEN = '#648397', '#B17D83', '#6E9688'
PALE = '#F4F7F8'
POSITION = {
    'N15':(0,3), 'N17':(1.2,3), 'N01':(2.4,3), 'N03':(3.6,3),
    'N02':(5,3), 'N07':(6.2,3), 'N04':(0,1.65), 'N06':(1.2,1.65),
    'N05':(2.4,1.65), 'N13':(5,1.65), 'N08':(6.2,1.65), 'N18':(7.4,1.65),
    'N11':(0,.3), 'N10':(1.2,.3), 'N09':(2.4,.3), 'N14':(5,.3),
    'N16':(6.2,.3), 'N12':(1.2,-.95),
}
NAMES = {'N01':'Main hall','N02':'Passage','N03':'Gallery room','N04':'Classroom',
         'N05':'Central\ncorridor','N06':'Impression\ngallery','N07':'North corridor',
         'N08':'Temporary\nhall','N09':'Fire door','N10':'Emergency\npassage',
         'N11':'Side exit','N12':'Courtyard garden','N13':'Temporary\ngallery',
         'N14':'Rear corridor','N15':'Enclosed\ncourtyard','N16':'Storage',
         'N17':'West gallery','N18':'Staff exit'}
EXPORTS = []
FORMATS = ('png',)


def configure():
    plt.rcParams.update({
        'font.family':'sans-serif', 'font.sans-serif':['Arial','DejaVu Sans'],
        'font.size':7.5, 'axes.titlesize':8.5, 'axes.titleweight':'medium',
        'axes.labelsize':7.5, 'xtick.labelsize':7, 'ytick.labelsize':7,
        'text.color':INK, 'axes.labelcolor':INK, 'axes.edgecolor':'#A6B1B6',
        'xtick.color':MUTED, 'ytick.color':MUTED, 'axes.linewidth':.65,
        'axes.spines.top':False, 'axes.spines.right':False,
        'xtick.major.width':.6, 'ytick.major.width':.6,
        'xtick.major.size':3, 'ytick.major.size':3,
        'figure.facecolor':'white', 'axes.facecolor':'white',
        'legend.frameon':False, 'legend.fontsize':7,
        'svg.fonttype':'none', 'pdf.fonttype':42,
        'svg.hashsalt':'evacuation-paper-readme',
    })


def title(ax, letter, label):
    ax.annotate(letter,xy=(0,1),xycoords='axes fraction',xytext=(-13,10),textcoords='offset points',
                fontsize=9,fontweight='bold',va='bottom')
    ax.annotate(label,xy=(0,1),xycoords='axes fraction',xytext=(0,10),textcoords='offset points',
                fontsize=8.5,va='bottom')


def grid(ax, axis='y'):
    ax.set_axisbelow(True)
    ax.grid(axis=axis,color=GRID,lw=.6)


def save(fig, name):
    fig.canvas.draw()
    # Fail if a figure-level label falls outside the canvas before export.
    renderer = fig.canvas.get_renderer()
    for text in fig.texts:
        box = text.get_window_extent(renderer)
        if box.x0 < -2 or box.y0 < -2 or box.x1 > fig.bbox.width+2 or box.y1 > fig.bbox.height+2:
            raise ValueError(f'Figure label outside canvas: {name}: {text.get_text()}')
    for ext in FORMATS:
        target = OUT / f'{name}.{ext}'
        metadata = {'Date':None} if ext=='svg' else ({'CreationDate':None,'ModDate':None} if ext=='pdf' else {})
        fig.savefig(target,dpi=360,facecolor='white',metadata=metadata)
        if ext=='svg':
            target.write_text('\n'.join(line.rstrip() for line in target.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')
        EXPORTS.append(dict(file=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    plt.close(fig)


def network(ax, data, names=False, effects=False):
    topology=data['topology']
    deltas={r['node']:r['delta'] for r in data['spatial_nodes']} if effects else {}
    for u,v in topology['edges']:
        closed='N10' in (u,v)
        widened=set((u,v))=={'N06','N10'} and not effects
        directed=[u,v] in topology['exit_directed']
        ax.add_patch(FancyArrowPatch(POSITION[u],POSITION[v],
            arrowstyle='-|>' if directed else '-',mutation_scale=7,
            shrinkA=12,shrinkB=12,lw=2 if widened else .9,
            color=ROSE if widened else '#BFCAD0',
            linestyle=(0,(2,2)) if closed and effects else '-',zorder=1))
    ax.add_patch(FancyArrowPatch(POSITION['N06'],POSITION['N08'],
        connectionstyle='arc3,rad=-.20',arrowstyle='<->',mutation_scale=8,
        shrinkA=12,shrinkB=12,lw=1.6,linestyle=(0,(4,3)),color=GREEN,zorder=2))
    for node,(x,y) in POSITION.items():
        value=deltas.get(node)
        edge = GREEN if value is not None and value<0 else ROSE if value is not None else '#859BA8'
        fill = '#E5EFEB' if value is not None and value<0 else '#F3E8E9' if value is not None else PALE
        if not effects and node=='N01': fill,edge='#F3E8E9',ROSE
        if node in ('N11','N18'): fill,edge='#E5EFEB',GREEN
        ax.add_patch(Circle((x,y),.19,facecolor=fill,edgecolor=edge,lw=1.1,zorder=3))
        ax.text(x,y,node,ha='center',va='center',fontsize=6.6,fontweight='medium',zorder=4)
        if names:
            ax.text(x,y-.34,NAMES[node],ha='center',va='top',fontsize=6,color=MUTED,
                    bbox=dict(fc='white',ec='none',pad=.5),zorder=4)
        if value is not None:
            ax.text(x,y-.34,f'{value:+d}',ha='center',va='top',fontsize=8.5,fontweight='bold',color=edge)
    ax.set(xlim=(-.55,7.85),ylim=(-1.55,3.72),aspect='equal')
    ax.axis('off')


def topology_figure(data):
    fig=plt.figure(figsize=(7.2,4.05))
    ax=fig.add_axes([.04,.20,.92,.71])
    network(ax,data,names=True)
    ax.text(2.4,3.40,'FIRE ORIGIN',ha='center',color=ROSE,fontsize=6.5,fontweight='bold')
    ax.text(0,.73,'EXIT',ha='center',color=GREEN,fontsize=6.5,fontweight='bold')
    ax.text(7.4,2.08,'EXIT',ha='center',color=GREEN,fontsize=6.5,fontweight='bold')
    ax.text(3.7,2.33,'D2  ·  added N06–N08 link',ha='center',color=GREEN,fontsize=7,
            bbox=dict(fc='white',ec='none',pad=1))
    ax.text(1.55,.67,'D1\ncapacity 4 → 8',ha='left',color=ROSE,fontsize=6.5,
            bbox=dict(fc='white',ec='none',pad=1))
    ax.annotate('C1: N10 closed',xy=(1.2,.3),xytext=(3.2,-.75),fontsize=7,color=ROSE,
                arrowprops=dict(arrowstyle='-',lw=.8,color=ROSE),ha='center')
    fig.text(.045,.95,'Museum topology and design interventions',fontsize=10,fontweight='medium')
    fig.text(.045,.102,'D0  original network     D1  capacity enhancement     D2  topological redundancy',fontsize=7.2)
    fig.text(.045,.052,'C0  initially open   /   C1  N10 closed from step 0     ·     18 spaces, 22 baseline connections',fontsize=6.8,color=MUTED)
    save(fig,'paper-topology')


def results_figure(data):
    fig=plt.figure(figsize=(7.2,4.95))
    gs=fig.add_gridspec(2,2,left=.09,right=.93,bottom=.17,top=.90,wspace=.92,hspace=.64,width_ratios=[1,1.22])
    for row,(metric,scale,ylabel,limits,heading) in enumerate([
        ('escape_rate',100,'Escape rate (%)',(35,70),'Escape outcomes'),
        ('rmet30',1,'RMET30 (steps)',(13,22),'Time to escape')]):
        ax=fig.add_subplot(gs[row,0]); grid(ax)
        for c,color,marker in [('C0',BLUE,'o'),('C1',ROSE,'s')]:
            cells=[next(r for r in data['cells'] if r['condition']==c and r['design']==d) for d in ['D0','D1','D2']]
            ax.errorbar(np.arange(3)+(-.045 if c=='C0' else .045),[r[metric]*scale for r in cells],
                yerr=[r[metric+'_sd']*scale for r in cells],color=color,marker=marker,markersize=4,
                lw=1.15,elinewidth=.9,capsize=2.5,label=c)
        ax.set(xticks=range(3),xticklabels=['D0','D1','D2'],ylabel=ylabel,ylim=limits,xlim=(-.30,2.30))
        title(ax,'a' if row==0 else 'b',heading)
        if row==0: ax.legend(loc='upper right',ncol=2,handlelength=1,columnspacing=1)
    ax=fig.add_subplot(gs[:,1]); grid(ax,'x')
    rows=data['effects']
    ax.axvline(0,color='#A2AFB5',lw=.9,ls=(0,(3,3)))
    ax.axhspan(3.55,4.45,color='#F0F5F3',zorder=0)
    for i,r in enumerate(rows):
        color=ROSE if i==0 else GREEN if i>=3 else BLUE
        ax.errorbar(r['mean']*100,i,xerr=[[100*(r['mean']-r['low'])],[100*(r['high']-r['mean'])]],
            fmt='o',color=color,markersize=4.7,lw=1.4,capsize=2.5)
        ax.text(1.02,i,f'{r["mean"]*100:+.1f}',transform=ax.get_yaxis_transform(),va='center',ha='left',fontsize=7)
    ax.set(yticks=range(len(rows)),yticklabels=[r['label'] for r in rows],ylim=(5.65,-.65),xlim=(-16,10),
           xticks=[-15,-10,-5,0,5,10],xlabel='Escape-rate difference (percentage points)')
    ax.spines['left'].set_visible(False); ax.tick_params(axis='y',length=0,pad=6)
    title(ax,'c','Paired design effects')
    fig.text(.09,.075,'a,b  Mean ± SD; 20 runs per cell.   c  Reported mean difference and 95% bootstrap CI; 20 seed pairs.',fontsize=6.5,color=MUTED)
    fig.text(.09,.035,'D2 interaction = (D2 − D0) in C1 minus (D2 − D0) in C0. Source: manuscript Table 3 and Figure 3.',fontsize=6.5,color=MUTED)
    save(fig,'paper-results')


def spatial_figure(data):
    fig=plt.figure(figsize=(7.2,3.72))
    ax=fig.add_axes([.035,.24,.59,.62]); network(ax,data,effects=True)
    title(ax,'a','Where terminal failures changed')
    ax.text(3.7,2.38,'183 link traversals',ha='center',fontsize=7,color=GREEN,bbox=dict(fc='white',ec='none',pad=1))
    ax.text(3.7,2.05,'172 from N06 → N08',ha='center',fontsize=6.3,color=MUTED,bbox=dict(fc='white',ec='none',pad=1))
    ax.text(1.2,-.06,'closed',ha='center',fontsize=6,color=MUTED)
    ax=fig.add_axes([.74,.26,.22,.58]); grid(ax)
    ax.axhline(0,color='#A2AFB5',lw=.8)
    for x,value,bottom,color in [(0,-81,0,GREEN),(1,60,-81,ROSE),(2,-21,0,BLUE)]:
        ax.bar(x,value,bottom=bottom,color=color,width=.60,zorder=3)
        label_y=-42 if x==0 else -51 if x==1 else -10.5
        ax.text(x,label_y,f'{value:+d}',ha='center',va='center',fontsize=9,color='white',fontweight='bold')
    ax.plot([.3,.7],[-81,-81],color='#A2AFB5',lw=.8)
    ax.plot([1.3,1.7],[-21,-21],color='#A2AFB5',lw=.8)
    ax.set(xticks=[0,1,2],xticklabels=['N04','Other\nrooms','Total'],ylim=(-95,15),yticks=[-80,-60,-40,-20,0],
           ylabel='Change in terminal failures')
    title(ax,'b','Local relief, net gain')
    fig.text(.06,.12,'D2 − D0 under C1 · counts pooled across 20 runs',fontsize=7,fontweight='medium')
    fig.text(.06,.063,'Negative = fewer terminal failures; positive = more. Node labels show reported changes, not evacuation paths.',fontsize=6.3,color=MUTED)
    save(fig,'paper-spatial')


def policies_figure(data):
    fig,axes=plt.subplots(1,2,figsize=(7.2,3.55),gridspec_kw={'width_ratios':[1,1]})
    fig.subplots_adjust(left=.20,right=.94,top=.84,bottom=.23,wspace=.33)
    rows=data['policies']; y=np.arange(len(rows))
    for j,(ax,key,scale,heading,xlabel) in enumerate(zip(axes,
        ['escape_delta','rmet30_delta'],[100,1],['Escape-rate gain','Change in time to escape'],
        ['D2 − D0 (percentage points)','D2 − D0 RMET30 (steps)'])):
        grid(ax,'x');ax.axvline(0,color='#A2AFB5',lw=.8)
        for i,r in enumerate(rows):
            color=GREEN if i==0 else BLUE if i==1 else '#A8B9C3'
            value=r[key]*scale
            ax.hlines(i,0,value,color=color,lw=2.2)
            ax.plot(value,i,'o',color=color,markersize=5)
            ax.annotate(f'{value:+.1f}' if j==0 else f'{value:+.2f}',(value,i),
                        xytext=(5 if j==0 else -5,0),textcoords='offset points',va='center',
                        ha='left' if j==0 else 'right',fontsize=7,color=INK)
        ax.set(yticks=y,yticklabels=[r['policy'] for r in rows] if j==0 else [],ylim=(5.6,-.6),xlabel=xlabel)
        ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
        if j==0: ax.set(xlim=(0,24),xticks=[0,5,10,15,20])
        else: ax.set(xlim=(-5.5,.25),xticks=[-5,-4,-3,-2,-1,0])
        title(ax,chr(97+j),heading)
    fig.text(.20,.10,'C1 · 20 seed pairs per policy · mean differences reported in manuscript Table 4',fontsize=6.5,color=MUTED)
    fig.text(.20,.05,'LLM-off uses the LLM runs’ initial agent states. Other policy campaigns have their own seeded states.',fontsize=6.2,color=MUTED)
    save(fig,'paper-policies')


def profiles_figure(data):
    fig,axes=plt.subplots(2,2,figsize=(7.2,4.3))
    fig.subplots_adjust(left=.15,right=.97,top=.90,bottom=.18,wspace=.50,hspace=.67)
    for i,(ax,key,scale,heading,lim) in enumerate(zip(axes.flat,
        ['escape_rate','smoke_exposure','backtracks','final_panic'],[100,1,1,1],
        ['Escape rate (%)','Cumulative smoke exposure','Backtracks per agent','Final panic'],
        [(0,112),(0,5.1),(0,3.1),(0,1.18)])):
        grid(ax,'x')
        for y,(r,color) in enumerate(zip(data['profiles'],[BLUE,GREEN,ROSE])):
            value=r[key]*scale
            ax.barh(y,value,color=color,height=.5)
            ax.annotate(f'{value:.1f}' if i==0 else f'{value:.3f}',(value,y),xytext=(4,0),textcoords='offset points',va='center',fontsize=7)
        ax.set(yticks=range(3),yticklabels=[r['profile'] for r in data['profiles']],ylim=(2.6,-.6),xlim=lim)
        ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
        title(ax,chr(97+i),heading)
    fig.text(.15,.09,'Pooled outcomes across 120 LLM runs · 10 Cognitive, 15 Perceptual and 23 Follower agents per run',fontsize=6.4,color=MUTED)
    fig.text(.15,.045,'Point estimates reproduce manuscript Figure 5; the profiles describe the frozen synthetic population.',fontsize=6.4,color=MUTED)
    save(fig,'paper-profiles')


def write_tables(data):
    for name,key in [('paper-cell-summary','cells'),('paper-design-effects','effects'),
                     ('paper-policy-effects','policies'),('paper-profile-summary','profiles'),
                     ('paper-spatial-nodes','spatial_nodes'),('paper-spatial-summary','spatial_totals')]:
        rows=data[key]
        fields=list(dict.fromkeys(k for r in rows for k in r))
        with (OUT/f'{name}.csv').open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n')
            writer.writeheader();writer.writerows(rows)


def validate(data):
    assert len(data['cells'])==6 and all(r['n']==20 for r in data['cells'])
    assert len(data['effects'])==6 and all(r['low'] <= r['mean'] <= r['high'] for r in data['effects'])
    assert len(data['topology']['nodes'])==18 and len(data['topology']['edges'])==22
    assert len(data['policies'])==6 and sum(r['n'] for r in data['profiles'])==48
    total=data['spatial_totals']
    for key in ('d0','d2'): assert total[0][key]+total[1][key]==total[2][key]
    assert total[0]['d2']-total[0]['d0']==-81 and total[2]['d2']-total[2]['d0']==-21


def main():
    global OUT, FORMATS
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exports',action='store_true',help='Write the full figure bundle to local-exports/paper-figures/')
    args=parser.parse_args()
    if args.exports:
        OUT=ROOT/'local-exports'/'paper-figures'
        FORMATS=('png','svg','pdf')
    OUT.mkdir(parents=True,exist_ok=True)
    data=json.loads(SOURCE.read_text(encoding='utf-8'))
    validate(data);configure()
    if args.exports: write_tables(data)
    for draw in (topology_figure,results_figure,spatial_figure,policies_figure,profiles_figure): draw(data)
    manifest=dict(source_file=SOURCE.name,source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        manuscript_sha256=data['source']['sha256'],analysis_mode='paper_reported_20_seed',
        exports=EXPORTS,style=dict(width_mm=182.88,font='Arial',raster_dpi=360,background='white',
                                  vector_formats=['svg','pdf']),audit_reference=data['audit_reference'])
    if args.exports:
        (OUT/'paper-figure-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(figures=5,exports=len(EXPORTS),mode=manifest['analysis_mode'])))


if __name__=='__main__':
    main()
