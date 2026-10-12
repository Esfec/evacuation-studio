"""Versioned local event service; never puts credentials in URLs or recordings."""
import argparse
import hashlib
import json
import os
import sys
import threading
import time
import uuid
from collections import Counter
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from settings import DEFAULTS, number, validate_positions, validate_profiles

HERE = Path(__file__).resolve().parent
DEFAULT_REPO = HERE.parent / '01_研究源码'
PROTOCOL = 'evacuation.events.v1'
REPLAY = 'evacuation.replay.v1'
IMPLEMENTATION = 'studio-1.4-context-ui'
_ENG = None
_LOCK = threading.RLock()
RUNS = {}


def load_engine(repo=DEFAULT_REPO):
    global _ENG
    with _LOCK:
        if _ENG is None:
            sys.path.insert(0, str(repo))
            from engine import SimulationEngine
            from run_config import RunConfig, AgentCounts, POLICY_IDS
            from scenarios import apply_scenario
            from config import LLM_PROVIDERS
            from recorder import save_run_v4
            _ENG = dict(engine=SimulationEngine, config=RunConfig, counts=AgentCounts,
                        scenario=apply_scenario, providers=LLM_PROVIDERS,
                        policies=POLICY_IDS, save=save_run_v4)
        return _ENG


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def validate(params, repo):
    E = load_engine(repo)
    unknown=set(params)-set(DEFAULTS)-{'api_key','autoplay','agent_profiles'}
    if unknown:
        raise ValueError('未知配置参数: '+', '.join(sorted(unknown)))
    policy = params.get('policy', 'Local_Rule')
    design, condition = params.get('design', 'D0'), params.get('condition', 'C0')
    if policy not in E['policies'] or design not in ('D0','D1','D2') or condition not in ('C0','C1'):
        raise ValueError('无效的策略、设计或火情条件')
    provider = str(params.get('provider', 'OpenAI'))
    if provider not in E['providers']:
        raise ValueError('不支持的 API 服务商')
    key = str(params.get('api_key') or os.environ.get(E['providers'][provider]['env_key'], '')).strip()
    if policy == 'LLM_Agent' and not key:
        raise ValueError('LLM_Agent 需要 API Key；请选择本地策略或历史录制回放')
    def integer(name, default, low, high):
        v = params.get(name, default)
        if isinstance(v, bool) or str(v).strip() != str(int(v)):
            raise ValueError(f'{name} 必须为整数')
        v = int(v)
        if not low <= v <= high:
            raise ValueError(f'{name} 范围 {low}–{high}')
        return v
    counts = E['counts'](integer('cognitive',10,0,100), integer('perceptual',15,0,100), integer('follower',23,0,100))
    if counts.total > 120:
        raise ValueError('展示服务最多 120 人')
    mapped,_=E['scenario'](read_json(Path(repo)/'Map.json'),design,condition,4)
    nodes={n['id']:n for n in mapped['nodes']}
    fire_origin=params.get('fire_origin','N01')
    if fire_origin not in nodes or nodes[fire_origin].get('type')=='exit' or nodes[fire_origin].get('scenario_blocked'):
        raise ValueError('起火点必须为存在且未被场景关闭的非出口节点')
    distribution,positions=validate_positions(params,nodes,(counts.cognitive,counts.perceptual,counts.follower))
    extra={name:number(params,name,DEFAULTS[name],lo,hi,ints) for name,lo,hi,ints in (
        ('fire_rate',.01,1,False),('smoke_scale',0,1,False),('risky_coeff',.1,30,False),
        ('blocked_coeff',.1,60,False),('base_edge_capacity',1,100,True),
        ('step_seconds',1,60,True),('min_hops_to_exit',1,18,True),
        ('risk_weight',0,100,False),('crowd_weight',0,100,False),('temperature',0,2,False))}
    extra['smoke_rate']=None if params.get('smoke_rate') in (None,'') else number(params,'smoke_rate',.1,.01,1)
    cfg = E['config'](seed=integer('seed',42,0,2147483647), policy_id=policy,
                      design_id=design, condition_id=condition, fire_origin=fire_origin,
                      max_steps=integer('steps',30,1,300), agent_counts=counts,
                      llm_concurrency=integer('concurrency',8,1,32),
                      provider=provider, model=str(params.get('model') or E['providers'][provider]['models'][0])[:160],
                      initial_distribution=distribution,initial_positions=positions,**extra)
    return cfg, key if policy == 'LLM_Agent' else ''


def snapshot(eng, initial=False):
    rows = {} if initial else {r['agent_id']:r for r in eng.agent_step_log if r['step']==eng.current_step-1}
    agents = []
    for a in eng.agents:
        r = rows.get(a['id'], {})
        agents.append(dict(id=a['id'], type=a['type'], node=a['current_node'], status=a['status'],
                           panic=a['panic_level'], stamina=a['stamina'], health=a['health'],
                           from_node=r.get('from_node',a['current_node']), target=r.get('proposed_target',''),
                           action=r.get('action_result','INITIAL'), mode=r.get('decision_mode',''),
                           summary=r.get('brief_justification',''),
                           observation=json.loads(r.get('visible_options_json','[]')),
                           context=json.loads(r['context_json']) if r.get('context_json') else eng.observable_context(a),
                           decision_targets=r.get('decision_targets',''),
                           smoke_exposure=a.get('cumulative_smoke_exposure',0)))
    counts = Counter(a['status'] for a in eng.agents)
    return dict(step=eng.current_step-1, completed_steps=eng.current_step,
                sim_time_s=eng.current_step*eng.run_config.step_seconds,
                agents=agents, nodes=[dict(id=nid,risk=n['risk_level'],smoke=n['smoke_density'],
                occupancy=n['current_count'],capacity=n['capacity'],status=n['status'],
                blocked=bool(n.get('scenario_blocked'))) for nid,n in eng.nodes.items()],
                edges=[] if initial else [dict(r) for r in eng.edge_step_log if r['step']==eng.current_step-1],
                counts=dict(active=counts['Active'],escaped=counts['Escaped'],dead=counts['Dead'],exhausted=counts['Exhausted']),
                llm_calls=len(eng.llm_call_log), fallback_count=eng.fallback_count, valid=eng.valid_run)


class RunSession:
    def __init__(self, params, repo=DEFAULT_REPO, output=None):
        self.repo = Path(repo)
        self.cfg, self.key = validate(params, self.repo)
        self.agent_data=validate_profiles(params.get('agent_profiles') or read_json(self.repo/'Agent.json'))
        self.settings={**DEFAULTS,**{k:v for k,v in params.items() if k not in ('api_key','autoplay')}}
        self.settings['agent_profiles']=self.agent_data
        self.id = uuid.uuid4().hex
        self.output = Path(output or HERE / 'runs') / self.id
        self.output.mkdir(parents=True)
        self.condition = threading.Condition(threading.RLock())
        self.events, self.snapshots = [], []
        self.status, self.cancelled, self.budget = 'starting', False, 0
        self.paused = not bool(params.get('autoplay', True))
        self.engine = None
        self.error = None
        self.source = 'live_llm' if self.cfg.policy_id=='LLM_Agent' else 'live_local'
        self.topology = {}

    def emit(self, kind, data):
        with self.condition:
            event = dict(protocol=PROTOCOL, run_id=self.id, seq=len(self.events)+1,
                         type=kind, step=data.get('step', self.engine.current_step if self.engine else -1),
                         timestamp=time.time(), data=data)
            self.events.append(event)
            with (self.output/'events.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps(event,ensure_ascii=False)+'\n')
            self.condition.notify_all()

    def control(self, action):
        with self.condition:
            if self.status in ('completed','failed','cancelled'):
                raise ValueError('运行已经结束；可以使用时间轴回放')
            if action == 'pause':
                self.paused, self.budget = True, 0
            elif action == 'resume':
                self.paused, self.budget = False, 0
            elif action == 'step':
                self.paused = True
                self.budget += 1
            elif action == 'stop':
                self.cancelled = True
            else:
                raise ValueError('未知控制动作')
            self.emit('run.control',dict(action=action, effect='next_step_boundary'))
            self.condition.notify_all()

    def replay(self):
        with self.condition:
            return dict(schema=REPLAY, implementation=IMPLEMENTATION, id=self.id,
                        source=self.source, config=self.cfg.to_dict(), topology=self.topology,
                        status=self.status, error=self.error, snapshots=list(self.snapshots),
                        events=list(self.events), valid=bool(self.engine and self.engine.valid_run),
                        fallback_count=self.engine.fallback_count if self.engine else 0,
                        quality=('invalid' if self.status=='failed' or (self.engine and not self.engine.valid_run) else
                                 'degraded' if self.engine and self.engine.fallback_count else 'clean'),
                        provenance=getattr(self,'provenance',{}),settings=self.settings)

    def run(self):
        E = load_engine(self.repo)
        try:
            mapped, manifest = E['scenario'](read_json(self.repo/'Map.json'),self.cfg.design_id,self.cfg.condition_id,self.cfg.base_edge_capacity)
            mapped['fire_origin'] = self.cfg.fire_origin
            self.topology = mapped
            self.provenance = {n:hashlib.sha256((self.repo/n).read_bytes()).hexdigest()
                               for n in ('Map.json','Agent.json','engine.py','movement.py','llm_api.py','run_config.py')}
            self.provenance['effective_agent_profiles']=hashlib.sha256(json.dumps(self.agent_data,sort_keys=True).encode()).hexdigest()
            (self.output/'settings.json').write_text(json.dumps(self.settings,ensure_ascii=False,indent=2),encoding='utf-8')
            self.engine = E['engine'](mapped,self.agent_data,api_key=self.key,
                api_provider=self.cfg.provider, api_model=self.cfg.model, seed=self.cfg.seed,
                temperature=self.cfg.temperature, fire_origin=self.cfg.fire_origin,
                fire_rate=self.cfg.fire_rate, risky_coeff=self.cfg.risky_coeff,blocked_coeff=self.cfg.blocked_coeff,
                run_config=self.cfg,intervention_manifest=manifest,event_sink=self.emit)
            self.engine.initialize_agents(self.cfg.agent_counts.cognitive,self.cfg.agent_counts.perceptual,
                                          self.cfg.agent_counts.follower,min_hops_to_exit=self.cfg.min_hops_to_exit)
            self.engine.update_environment_v4(0)
            self.status='running'
            self.emit('run.started',dict(config=self.cfg.to_dict(),source=self.source,topology=mapped,
                                        implementation=IMPLEMENTATION,manifest=manifest,
                                        provenance=self.provenance,settings=self.settings))
            initial=snapshot(self.engine,True)
            self.snapshots.append(initial)
            self.emit('snapshot',initial)
            while self.engine.current_step < self.cfg.max_steps and self.engine.valid_run and any(a['status']=='Active' for a in self.engine.agents):
                with self.condition:
                    while self.paused and self.budget==0 and not self.cancelled:
                        self.status='paused'
                        self.condition.wait(1)
                    if self.cancelled:
                        break
                    if self.budget:
                        self.budget-=1
                    self.status='running'
                t0=time.monotonic()
                self.engine.run_step()
                frame=snapshot(self.engine)
                frame['wall_seconds']=round(time.monotonic()-t0,3)
                with self.condition:
                    self.snapshots.append(frame)
                self.emit('snapshot',frame)
            self.status='cancelled' if self.cancelled else ('completed' if self.engine.valid_run else 'failed')
            if not self.engine.valid_run:
                self.error=self.engine.invalid_reason
        except Exception as exc:
            self.status='failed'
            self.error=str(exc).replace(self.key,'***') if self.key else str(exc)
            if self.engine:
                self.engine.valid_run = False
                self.engine.invalid_reason = 'runtime_error:' + type(exc).__name__
        finally:
            if self.engine:
                try:
                    E['save'](self.engine,self.output/'research')
                except Exception as exc:
                    self.status='failed'
                    self.error='研究日志保存失败: '+type(exc).__name__
                    self.engine.valid_run = False
                    self.engine.invalid_reason = 'persistence_error:' + type(exc).__name__
                self.engine.session.close()
                self.engine.api_key=''
            self.key=''
            self.emit('run.ended',dict(status=self.status,error=self.error,
                       valid=bool(self.engine and self.engine.valid_run),
                       fallback_count=self.engine.fallback_count if self.engine else 0))
            (self.output/'replay.json').write_text(json.dumps(self.replay(),ensure_ascii=False),encoding='utf-8')


class Handler(SimpleHTTPRequestHandler):
    repo=DEFAULT_REPO
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(HERE),**kwargs)
    def log_message(self,*args):
        pass
    def _json(self,obj,status=200):
        data=json.dumps(obj,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def do_POST(self):
        try:
            origin=self.headers.get('Origin')
            if origin and urlparse(origin).netloc != self.headers.get('Host'):
                return self._json({'error':'仅允许本地同源请求'},403)
            size=int(self.headers.get('Content-Length',0))
            if size<=0 or size>262144:
                raise ValueError('请求正文大小无效')
            data=json.loads(self.rfile.read(size))
            path=urlparse(self.path).path
            if path=='/api/runs':
                with _LOCK:
                    if sum(r.status not in ('completed','cancelled','failed') for r in RUNS.values())>=4:
                        return self._json({'error':'最多同时运行 4 场，请先停止已有运行'},409)
                    run=RunSession(data,self.repo)
                    RUNS[run.id]=run
                    threading.Thread(target=run.run,daemon=True).start()
                return self._json({'id':run.id,'protocol':PROTOCOL},201)
            parts=path.strip('/').split('/')
            if len(parts)==4 and parts[:2]==['api','runs'] and parts[3]=='control' and parts[2] in RUNS:
                RUNS[parts[2]].control(data.get('action'))
                return self._json({'ok':True})
            return self._json({'error':'不存在'},404)
        except (ValueError,TypeError,KeyError) as exc:
            return self._json({'error':str(exc)},400)
    def do_GET(self):
        parsed=urlparse(self.path)
        path=parsed.path
        if path=='/api/meta':
            E=load_engine(self.repo)
            return self._json(dict(protocol=PROTOCOL,implementation=IMPLEMENTATION,
                policies=sorted(E['policies']),topology=read_json(self.repo/'Map.json'),
                defaults=DEFAULTS,agent_profiles=read_json(self.repo/'Agent.json'),
                providers={k:dict(models=v['models'],has_key=bool(os.environ.get(v['env_key']))) for k,v in E['providers'].items()}))
        if path=='/api/ping':
            return self._json({'ok':True,'repo_exists':self.repo.is_dir()})
        parts=path.strip('/').split('/')
        if len(parts)==4 and parts[:2]==['api','runs']:
            run=RUNS.get(parts[2])
            if run is None:
                if parts[3]=='replay' and len(parts[2])==32 and all(c in '0123456789abcdef' for c in parts[2]):
                    saved=HERE/'runs'/parts[2]/'replay.json'
                    if saved.is_file():
                        return self._json(read_json(saved))
                return self._json({'error':'运行不存在'},404)
            if parts[3]=='replay':
                return self._json(run.replay())
            if parts[3]=='events':
                try:
                    cursor=int(self.headers.get('Last-Event-ID') or parse_qs(parsed.query).get('after',['0'])[0])
                    if cursor<0:
                        raise ValueError()
                except ValueError:
                    return self._json({'error':'无效的事件序号'},400)
                self.send_response(200)
                self.send_header('Content-Type','text/event-stream; charset=utf-8')
                self.send_header('Cache-Control','no-cache')
                self.send_header('Connection','close')
                self.end_headers()
                try:
                    while True:
                        with run.condition:
                            batch=run.events[cursor:]
                            done=any(e['type']=='run.ended' for e in run.events)
                            if not batch and not done:
                                run.condition.wait(1)
                        for e in batch:
                            self.wfile.write(('id: '+str(e['seq'])+'\ndata: '+json.dumps(e,ensure_ascii=False)+'\n\n').encode('utf-8'))
                            cursor=e['seq']
                        self.wfile.write(b': heartbeat\n\n')
                        self.wfile.flush()
                        if done and cursor>=len(run.events):
                            break
                except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
                    pass
                self.close_connection=True
                return
        if path.startswith('/api/'):
            return self._json({'error':'接口不存在；使用 POST /api/runs'},404)
        if path.startswith('/runs/') or path.endswith('.py') or path.startswith('/.'):
            return self._json({'error':'请通过回放下载接口访问'},403)
        return super().do_GET()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--repo',type=Path,default=DEFAULT_REPO)
    args=parser.parse_args()
    Handler.repo=args.repo.resolve()
    load_engine(Handler.repo)
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    print(f'Evacuation Studio http://{args.host}:{args.port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=='__main__':
    main()
