"""Run the same settings as the UI. Credentials are read only from the environment."""
import argparse
import json
import os
from pathlib import Path
from settings import DEFAULTS
from studio_server import DEFAULT_REPO, RunSession, read_json


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,help='UI 导出的 settings.json')
    p.add_argument('--output',type=Path,default=Path('runs'))
    p.add_argument('--repo',type=Path,default=DEFAULT_REPO)
    p.add_argument('--profile-file',type=Path)
    p.add_argument('--positions-file',type=Path,help='{"C01":"N03", ...}')
    p.add_argument('--distribution-file',type=Path,help='{"N03":10,"N04":...}')
    p.add_argument('--api-key-env',help='API 密钥环境变量名（不接收命令行明文密钥）')
    p.add_argument('--validate-only',action='store_true')
    p.add_argument('--write-defaults',type=Path)
    for name,default in DEFAULTS.items():
        if name in ('initial_distribution','initial_positions'):
            continue
        p.add_argument('--'+name.replace('_','-'),default=argparse.SUPPRESS,
                       type=float if name=='smoke_rate' else type(default))
    args=p.parse_args(argv)
    if args.write_defaults:
        args.write_defaults.write_text(json.dumps(DEFAULTS,ensure_ascii=False,indent=2),encoding='utf8')
        return 0
    params=read_json(args.config) if args.config else {}
    params.update({name:getattr(args,name) for name in DEFAULTS if hasattr(args,name)})
    for arg,key in (('profile_file','agent_profiles'),('positions_file','initial_positions'),('distribution_file','initial_distribution')):
        if getattr(args,arg):
            params[key]=read_json(getattr(args,arg))
    if args.api_key_env:
        params['api_key']=os.environ.get(args.api_key_env,'')
    try:
        run=RunSession(params,args.repo,args.output)
        if args.validate_only:
            print(json.dumps({'valid':True,'config':run.cfg.to_dict()},ensure_ascii=True))
            return 0
        run.run()
        print(json.dumps({'id':run.id,'status':run.status,'error':run.error,
                          'replay':str(run.output/'replay.json'),
                          'counts':run.snapshots[-1]['counts'] if run.snapshots else {}},ensure_ascii=True))
        return 0 if run.status=='completed' else 1
    except (ValueError,TypeError,KeyError) as exc:
        p.error(str(exc))


if __name__=='__main__':
    raise SystemExit(main())
