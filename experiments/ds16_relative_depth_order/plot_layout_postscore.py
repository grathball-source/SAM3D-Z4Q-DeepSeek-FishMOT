"""Postscore layout-only rerender; frozen generator and original figures retained."""
from common import *
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    report=read(HERE/'SUMMARY.json');verify_item(report['metrics'])
    names=['fishsa_development_8400','fishsa_validation_2888','Feeding_pooled1471','L3','LW']
    labels=['FishSA 8400','FishSA 2888','Feeding 1471','L3 (weak ref)','LW (weak ref)']
    colors=['#777777','#235ca8','#ce4545','#dfac35','#17836c','#8a53a2']
    values=report['main_units'];fig,axes=plt.subplots(1,2,figsize=(15,5))
    x=np.arange(5);width=.12
    for j,(arm,color) in enumerate(zip(ARMS,colors)):
        y=[values[n][arm]['IDF1'] for n in names]
        axes[0].bar(x+(j-2.5)*width,y,width,label=arm,color=color)
    axes[0].set_ylim(0,105);axes[0].set_ylabel('IDF1 (%)');axes[0].set_title('Same-source, all masks retained')
    axes[0].set_xticks(x,labels,rotation=15);axes[0].legend(fontsize=7,ncol=2)
    for j,base in enumerate(('Z4Q_FROZEN','ORDER_OFF')):
        y=[values[n]['DEPTH_ORDER']['IDF1']-values[n][base]['IDF1'] for n in names]
        bars=axes[1].bar(x+(j-.5)*.3,y,.3,label='DEPTH minus '+base,color=colors[1 if j==0 else 3])
        for b,v in zip(bars,y):axes[1].annotate(f'{v:+.3f}',(b.get_x()+b.get_width()/2,v),
            xytext=(0,4+j*12 if v==0 else 4 if v>0 else -12),textcoords='offset points',ha='center',fontsize=8)
    axes[1].set_ylim(-3.5,10.5)  # Leave room for negative labels.
    axes[1].axhline(0,color='#444444',linewidth=.8);axes[1].set_ylabel('IDF1 change (percentage points)')
    axes[1].set_xticks(x,labels,rotation=15);axes[1].set_title('Relative-order increment and original Z4Q contrast');axes[1].legend(fontsize=8)
    fig.suptitle('DS16: six frozen branches, 20,098 frames, zero model calls')
    fig.text(.03,.02,'Single exposed-data replay; L3/LW references are prediction-dependent. No blind-generalization or depth-necessity claim.',fontsize=9)
    fig.tight_layout(rect=(0,.06,1,.94))
    path=HERE/'FINAL_RESULTS_PLOT.svg'
    with path.open('x',encoding='utf-8') as stream:fig.savefig(stream,format='svg')
    png=HERE/'FINAL_RESULTS_PLOT.png'
    with png.open('xb') as stream:fig.savefig(stream,format='png',dpi=150)
    plt.close(fig)
    text=path.read_text(encoding='utf-8');path.write_text('\n'.join(line.rstrip() for line in text.splitlines())+'\n',encoding='utf-8',newline='\n')
    write_new(HERE/'FINAL_RESULTS_PLOT_PROVENANCE.json',dict(summary=artifact(HERE/'SUMMARY.json'),
        plot=artifact(path),numeric_plot_png=artifact(png),generator=artifact(__file__),private_or_GT_pixels_read=False))


if __name__=='__main__':main()
