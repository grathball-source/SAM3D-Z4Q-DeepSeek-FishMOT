"""Aggregate numeric figures only, after all prediction seals and official scores."""
from common import *
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    m=read(RUN/'METRICS.json');assert read(RUN/'SCORE_PROVENANCE.json')['reference_opened_after_all_seals']
    units={'Feeding1471':m['feeding_pooled']['metrics']}
    for name in ('fishsa_development_8400','fishsa_validation_2888','L3','LW'):units[name]=m['segments'][name]['metrics']
    names=list(units);x=np.arange(len(names));arms=ARMS[1:]
    fig,axes=plt.subplots(2,2,figsize=(14,9))
    for ax,field in zip(axes.ravel(),('IDF1','HOTA','AssA','IDSW')):
        for i,arm in enumerate(arms):
            values=[units[name][arm][field]-units[name]['SAM3_NATIVE'][field] for name in names]
            ax.bar(x+(i-2)*.15,values,width=.145,label=arm)
        ax.axhline(0,color='black',lw=.7);ax.set_title(field+' change versus identical-source SAM3_NATIVE')
        ax.set_xticks(x,names,rotation=12,fontsize=8);ax.grid(axis='y',alpha=.2)
        ax.set_ylabel('percentage points' if field!='IDSW' else 'switch count')
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=3,fontsize=9)
    fig.suptitle('DS18: fixed raw sources, own-state full replays; L3/LW weak preannotation',fontsize=13)
    fig.tight_layout(rect=(0,.085,1,.95))
    png=HERE/'METRIC_COMPARISON.png';svg=HERE/'METRIC_COMPARISON.svg';fig.savefig(png,dpi=150);fig.savefig(svg);plt.close(fig)
    write_new(HERE/'PUBLIC_PLOTS.json',dict(status='AGGREGATE_NUMERIC_ONLY_NO_PRIVATE_PIXELS',figures=[artifact(png),artifact(svg)],metric_source=artifact(RUN/'METRICS.json')))
if __name__=='__main__':main()
