"""Record paired runs for a talk (default: D0 and D2 under C1, same seed) and embed them.

The runs use the same engine and validation as the UI. Output:
  runs/talk/<run id>/...          full replay, events and research CSV per run
  talk_data.js                    window.TALK_RUNS, loaded by index.html before the demo runs

Real API calls are made only with --policy LLM_Agent and a key in the named environment
variable. Use --dry-run first to check the pipeline with the local rule policy (no API).
"""
import argparse
import json
import os
from studio_server import HERE, RunSession


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--provider',default='DeepSeek')
    p.add_argument('--model',default='deepseek-v4-flash',help='按账号实际可用的模型名称填写')
    p.add_argument('--api-key-env',default='DEEPSEEK_API_KEY')
    p.add_argument('--designs',default='D0,D2')
    p.add_argument('--condition',default='C1')
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--steps',type=int,default=30)
    p.add_argument('--concurrency',type=int,default=8)
    p.add_argument('--dry-run',action='store_true',help='使用 Local_Rule 跑通流程，不调用 API')
    p.add_argument('--out',default='talk_data.js')
    a=p.parse_args(argv)
    key=os.environ.get(a.api_key_env,'')
    if not a.dry_run and not key:
        p.error(f'请先在本终端设置环境变量 {a.api_key_env}')
    runs=[]
    for design in [d.strip() for d in a.designs.split(',') if d.strip()]:
        params=dict(policy='Local_Rule' if a.dry_run else 'LLM_Agent',design=design,condition=a.condition,
                    seed=a.seed,steps=a.steps,concurrency=a.concurrency)
        if not a.dry_run:
            params.update(provider=a.provider,model=a.model,api_key=key)
        session=RunSession(params,output=HERE/'runs'/'talk')
        print(f'running {design}/{a.condition} seed {a.seed} ...',flush=True)
        session.run()
        replay=session.replay()
        last=replay['snapshots'][-1]['counts'] if replay['snapshots'] else {}
        print(json.dumps(dict(id=replay['id'],design=design,status=replay['status'],quality=replay['quality'],
                              counts=last,llm_protocol=replay.get('llm_protocol')),ensure_ascii=False),flush=True)
        if replay['status']!='completed':
            raise SystemExit(f'{design} 未完成：{replay.get("error")}')
        runs.append(replay)
    bad=[r['config']['design_id'] for r in runs if r['quality']!='clean']
    if bad:
        print('注意：以下运行含规则兜底或无效记录，界面会标记为 degraded：'+', '.join(bad))
    (HERE/a.out).write_text('window.TALK_RUNS = '+json.dumps(runs,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    print(f'已写入 {HERE/a.out}；刷新页面后在录制列表顶部选择“汇报录制”。')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
