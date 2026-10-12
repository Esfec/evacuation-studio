"""Shared, JSON-safe settings used by UI, HTTP service and CLI."""
import copy
import math
from collections import Counter

DEFAULTS=dict(policy='Local_Rule',design='D0',condition='C0',seed=42,steps=30,
    cognitive=10,perceptual=15,follower=23,fire_origin='N01',fire_rate=.1,
    smoke_rate=None,smoke_scale=.9,risky_coeff=3.,blocked_coeff=7.,
    base_edge_capacity=4,step_seconds=5,min_hops_to_exit=3,
    risk_weight=6.,crowd_weight=2.,temperature=.1,concurrency=8,
    provider='OpenAI',model='gpt-4o',initial_distribution=None,initial_positions=None)


def number(data,name,default,lo,hi,integer=False):
    v=data.get(name,default)
    if isinstance(v,bool):
        raise ValueError(f'{name} 不能是布尔值')
    try:
        v=float(v)
    except (ValueError,TypeError):
        raise ValueError(f'{name} 必须是数字') from None
    if not math.isfinite(v) or not lo<=v<=hi or (integer and int(v)!=v):
        raise ValueError(f'{name} 需为 {lo}–{hi} 的'+('整数' if integer else '有限数字'))
    return int(v) if integer else v


def agent_ids(counts):
    result=[]
    for prefix,count in zip(('C','P','F'),counts):
        offset=len(result)
        result.extend(f'{prefix}{offset+j+1:02d}' for j in range(count))
    return result


def validate_positions(data,nodes,counts):
    distribution=data.get('initial_distribution')
    positions=data.get('initial_positions')
    if distribution is not None and positions is not None:
        raise ValueError('只能选择一种初始位置方式')
    if distribution is not None:
        if not isinstance(distribution,dict):
            raise ValueError('initial_distribution 必须是房间→人数的对象')
        distribution={nid:number({'n':v},'n',0,0,120,True) for nid,v in distribution.items()}
        if sum(distribution.values())!=sum(counts):
            raise ValueError('房间分配人数之和不等于总人数')
        occupancy=distribution
    elif positions is not None:
        if not isinstance(positions,dict) or set(positions)!=set(agent_ids(counts)):
            raise ValueError('逐个位置必须包含人数生成的全部 Agent ID')
        if any(not isinstance(n,str) for n in positions.values()):
            raise ValueError('初始位置必须是节点 ID')
        occupancy=Counter(positions.values())
    else:
        return None,None
    for nid,count in occupancy.items():
        node=nodes.get(nid)
        if not node or node.get('type')=='exit' or node.get('scenario_blocked') or node.get('status')=='Blocked':
            raise ValueError(f'初始位置 {nid} 不存在、是出口或已关闭')
        if count>node['capacity']:
            raise ValueError(f'{nid} 初始人数超过容量 {node["capacity"]}')
    return distribution,positions


def validate_profiles(data):
    data=copy.deepcopy(data)
    if not isinstance(data,dict) or not isinstance(data.get('agents'),list):
        raise ValueError('画像必须采用 Agent.json 的完整结构')
    if len(data['agents'])!=3 or {a.get('type') for a in data['agents']}!={'Cognitive','Perceptual','Follower'}:
        raise ValueError('画像必须分别包含三类 Agent，不能缺少或重复')
    for a in data['agents']:
        if not isinstance(a.get('desc'),str):
            raise ValueError('画像需要 desc 文本')
        try:
            p=a['params'];ph=p['physical'];ps=p['psychology'];pe=p['perception']
            for name,lo,hi in [('base_speed',0,5),('stamina',1,100),('stamina_decay_rate',0,30)]:
                ph[name]=number(ph,name,0,lo,hi)
            for name in ('panic_threshold','stress_resistance'):
                ps[name]=number(ps,name,0,0,1)
            for name in ('mistake_prob','ignore_exit_prob','follow_crowd_bias'):
                ps['panic_behavior'][name]=number(ps['panic_behavior'],name,0,0,1)
            pe['noise']=number(pe,'noise',0,0,1)
            for name in ('low_visibility','high_visibility'):
                pe['discovery_bias'][name]=number(pe['discovery_bias'],name,0,0,1)
            p['memory']['memory_prompt_length']=number(p['memory'],'memory_prompt_length',2,0,20,True)
            if not isinstance(p['behavior']['can_backtrack'],bool):
                raise ValueError('can_backtrack 必须为 true/false')
        except (KeyError,TypeError):
            raise ValueError(f'{a["type"]} 画像缺少参数分组') from None
    return data
