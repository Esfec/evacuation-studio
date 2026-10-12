"""Build recorded examples by actually executing the revised local engine."""
import base64
import json
from studio_server import HERE, RunSession


def main():
    runs=[]
    for design in ('D0','D1','D2'):
        for condition in ('C0','C1'):
            session=RunSession(dict(policy='Local_Rule',design=design,condition=condition,
                                    seed=42,steps=30),output=HERE/'runs'/'examples')
            session.run()
            if session.status!='completed':
                raise RuntimeError(session.error)
            replay=session.replay()
            runs.append(replay)
            f=replay['snapshots'][-1]
            print(design,condition,len(replay['snapshots']),'frames',f['counts'])
    (HERE/'studio_data.js').write_text('window.STUDIO_RUNS = '+json.dumps(runs,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    font=base64.b64encode((HERE/'font'/'fusion-pixel-12px-proportional-sc.woff2').read_bytes()).decode()
    css="@font-face{font-family:'FusionPixel';src:url(data:font/woff2;base64,"+font+") format('woff2');font-display:swap;font-weight:400}"
    (HERE/'font_data.js').write_text('window.FONT_CSS = '+json.dumps(css)+';',encoding='utf-8')


if __name__=='__main__':
    main()
