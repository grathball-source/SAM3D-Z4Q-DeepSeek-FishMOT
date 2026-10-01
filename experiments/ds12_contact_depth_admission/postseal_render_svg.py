"""Render six existing numeric SVGs for actual visual QA, without data reads."""
from pathlib import Path
import json,subprocess
from common import HERE,artifact,write_new,read


def main():
    assert (HERE/'run/SCORING_SEALED.json').is_file()
    inventory=read(HERE/'diagnosis/postseal_VISUALIZATION_INVENTORY.json')
    selected=[c for c in inventory['cases'] if c['query_global_frame'] in (65,170,1886)]
    assert len(selected)==6
    destination=HERE/'private/numeric_svg_QA';destination.mkdir()
    node=Path('C:/Users/19430/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    sharp=Path('C:/Users/19430/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp')
    script="const sharp=require(process.argv[1]); sharp(process.argv[2],{density:144}).resize({width:2200}).png().toFile(process.argv[3]).catch(e=>{console.error(e);process.exit(1)});"
    result=[]
    for case in selected:
        source=case['public_numeric_svg'];assert artifact(source['path'])==source
        target=destination/(Path(source['path']).stem+'.png')
        command=[str(node),'-e',script,str(sharp),source['path'],str(target)]
        completed=subprocess.run(command,text=True,capture_output=True)
        assert completed.returncode==0,completed.stderr
        result.append(dict(source_svg=source,rendered_numeric_png=artifact(target),command=command,exit_code=completed.returncode))
    output=HERE/'diagnosis/postseal_SVG_RENDER_RECORD.json'
    write_new(output,dict(status='PASS_NUMERIC_SVG_RENDER; ACTUAL_VIEW_PENDING',code=artifact(Path(__file__)),
        node_runtime=str(node),renderer=str(sharp),inventory=artifact(HERE/'diagnosis/postseal_VISUALIZATION_INVENTORY.json'),
        rendered=result,SVG_sources_modified=False,GT_reads=0,RGB_reads=0,raw_data_pixels_read=0))
    print(json.dumps(artifact(output)))


if __name__=='__main__':main()
