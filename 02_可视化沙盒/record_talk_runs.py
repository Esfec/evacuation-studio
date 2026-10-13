"""Record the paper's design x condition matrix for a talk and embed it in the studio.

Default: D0, D1, D2 under C0 and C1 (6 runs), DeepSeek LLM agents, seed 42.
Cells already present in talk_data.js with the same seed, policy, model and code are kept,
so only missing cells are recorded (use --rerun to record everything again).

Output:
  runs/talk/<run id>/...   full replay, events and research CSV per run
  talk_data.js             window.TALK_RUNS, loaded by index.html ("汇报录制" in the run list)
  疏散沙盒-单文件版.html     rebuilt offline page (skip with --no-bundle)

Real API calls need a key in the named environment variable. --dry-run uses the local
rule policy, makes no API calls and writes talk_data_dryrun.js (never touches talk_data.js).
"""
import argparse
import json
import os
import subprocess
import sys
from studio_server import HERE, IMPLEMENTATION, RunSession

PREFIX = 'window.TALK_RUNS = '


def load_existing(path):
    if not path.is_file():
        return []
    text = path.read_text(encoding='utf-8')
    start = text.find(PREFIX)
    if start < 0:
        return []
    body = text[start + len(PREFIX):].strip().rstrip(';').strip()
    try:
        runs = json.loads(body)
    except json.JSONDecodeError:
        return []
    return runs if isinstance(runs, list) else []


def cell_key(run):
    c = run.get('config', {})
    return (c.get('design_id'), c.get('condition_id'), c.get('seed'), c.get('policy_id'),
            c.get('model') if c.get('policy_id') == 'LLM_Agent' else None, run.get('implementation'))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--provider', default='DeepSeek')
    p.add_argument('--model', default='deepseek-v4-flash', help='按账号实际可用的模型名称填写')
    p.add_argument('--api-key-env', default='DEEPSEEK_API_KEY')
    p.add_argument('--designs', default='D0,D1,D2')
    p.add_argument('--conditions', '--condition', dest='conditions', default='C0,C1')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--steps', type=int, default=30)
    p.add_argument('--concurrency', type=int, default=8)
    p.add_argument('--dry-run', action='store_true', help='使用 Local_Rule 跑通流程，不调用 API，写入 talk_data_dryrun.js')
    p.add_argument('--rerun', action='store_true', help='忽略已有录制，全部重新录制')
    p.add_argument('--no-bundle', action='store_true', help='不重建离线单文件页面')
    p.add_argument('--out', default=None)
    a = p.parse_args(argv)
    out = HERE / (a.out or ('talk_data_dryrun.js' if a.dry_run else 'talk_data.js'))
    key = os.environ.get(a.api_key_env, '')
    if not a.dry_run and not key:
        p.error(f'请先在本终端设置环境变量 {a.api_key_env}')
    policy = 'Local_Rule' if a.dry_run else 'LLM_Agent'
    designs = [d.strip() for d in a.designs.split(',') if d.strip()]
    conditions = [c.strip() for c in a.conditions.split(',') if c.strip()]

    existing = [] if a.rerun else load_existing(out)
    have = {cell_key(r): r for r in existing if r.get('status') == 'completed'}
    runs = []
    for condition in conditions:
        for design in designs:
            want = (design, condition, a.seed, policy, a.model if policy == 'LLM_Agent' else None, IMPLEMENTATION)
            if want in have:
                r = have[want]
                print(f'keep {design}/{condition} seed {a.seed}: {r["id"]} ({r["quality"]})', flush=True)
                runs.append(r)
                continue
            params = dict(policy=policy, design=design, condition=condition, seed=a.seed, steps=a.steps, concurrency=a.concurrency)
            if not a.dry_run:
                params.update(provider=a.provider, model=a.model, api_key=key)
            session = RunSession(params, output=HERE / 'runs' / 'talk')
            print(f'running {design}/{condition} seed {a.seed} ...', flush=True)
            session.run()
            replay = session.replay()
            last = replay['snapshots'][-1]['counts'] if replay['snapshots'] else {}
            print(json.dumps(dict(id=replay['id'], design=design, condition=condition, status=replay['status'],
                                  quality=replay['quality'], counts=last, llm_protocol=replay.get('llm_protocol')),
                             ensure_ascii=False), flush=True)
            if replay['status'] != 'completed':
                raise SystemExit(f'{design}/{condition} 未完成：{replay.get("error")}')
            runs.append(replay)
            # Save after every run so an interruption never loses finished recordings.
            out.write_text(PREFIX + json.dumps(runs + [r for r in existing if cell_key(r) not in {cell_key(x) for x in runs}],
                                               ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
    # Final file: requested cells first (C0 then C1, D0..D2), then any other earlier recordings.
    keys = {cell_key(r) for r in runs}
    final = runs + [r for r in existing if cell_key(r) not in keys]
    out.write_text(PREFIX + json.dumps(final, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
    bad = [f"{r['config']['design_id']}/{r['config']['condition_id']}" for r in runs if r['quality'] != 'clean']
    if bad:
        print('注意：以下运行含规则兜底或无效记录，界面会标记为“含兜底”：' + ', '.join(bad))
    print(f'已写入 {out}（{len(final)} 组录制）')
    if not a.dry_run and not a.no_bundle:
        subprocess.run([sys.executable, str(HERE / 'bundle.py')], check=True, cwd=str(HERE))
    print('完成：刷新页面或双击离线单文件，在录制列表顶部选择“汇报录制”。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
