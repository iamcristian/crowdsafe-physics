"""Separate multi-floor network model with capacity, travel and visibility.

This is an engineering exploration model, not the 2-D contact engine. Stair
speeds and visibility reductions are explicit user assumptions. Smoke series
may come from an external model; no fire, smoke transport or injury is solved.
"""
import heapq
import math
import numpy as np


def run_building(data):
    nodes={n['id']:n for n in data['nodes']}
    if len(nodes)!=len(data['nodes']) or not nodes:
        raise ValueError('Node IDs must be unique.')
    for node in nodes.values():
        if node.get('kind','room') not in ('room','stair','safe'):
            raise ValueError('Node kind must be room, stair or safe.')
        if not math.isfinite(node.get('floor',0)):
            raise ValueError('Floor must be finite.')
    edges=data['links']
    for e in edges:
        if e['from'] not in nodes or e['to'] not in nodes or any(not math.isfinite(e[k]) or e[k]<=0 for k in ('length','capacity')):
            raise ValueError('Links need existing nodes and positive length/capacity.')
        if e.get('kind','corridor') not in ('corridor','stair'):
            raise ValueError('Link kind must be corridor or stair.')
    dt=float(data.get('dt',.1));horizon=float(data.get('duration',600));speed=float(data.get('speed',1.3));delay=float(data.get('pre_movement_max',0));stair=float(data.get('stair_factor',.65))
    if not .01<=dt<=1 or not 1<=horizon<=3600 or not .1<=speed<=7 or not 0<=delay<=horizon or not 0<stair<=1:
        raise ValueError('Invalid network time, speed, delay or stair factor.')
    smoke=data.get('visibility',[])
    for event in smoke:
        if event['node'] not in nodes or not math.isfinite(event['time']) or event['time']<0 or not math.isfinite(event['meters']) or event['meters']<0:
            raise ValueError('Visibility entries require node, nonnegative time and meters.')
    populations=data['populations']
    if any(p['node'] not in nodes or not isinstance(p['count'],int) or p['count']<0 for p in populations) or sum(p['count'] for p in populations)>2000:
        raise ValueError('Use existing spawn nodes and at most 2000 agents.')
    rng=np.random.default_rng(data.get('seed',7))
    agents=[dict(node=p['node'],ready=float(rng.uniform(0,delay)),exit=None,edge=None,remaining=0.) for p in populations for _ in range(p['count'])]
    tokens=np.zeros(len(edges));departures=np.zeros(len(edges),dtype=int);rows=[]
    safe={key for key,n in nodes.items() if n.get('kind')=='safe'}
    if not safe:
        raise ValueError('At least one safe node is required.')
    outgoing={key:[i for i,e in enumerate(edges) if e['from']==key] for key in nodes}
    def visibility(time):
        result={key:float('inf') for key in nodes}
        for event in sorted(smoke,key=lambda event:event['time']):
            if event['time']<=time:
                result[event['node']]=event['meters']
        return result
    def route(start,vis):
        queue=[(0.,start,())];seen=set()
        while queue:
            cost,node,path=heapq.heappop(queue)
            if node in seen:continue
            seen.add(node)
            if node in safe:return path[0] if path else None
            for i in outgoing[node]:
                e=edges[i]
                if min(vis[e['from']],vis[e['to']])<1:continue
                factor=min(1.,max(.1,min(vis[e['from']],vis[e['to']])/10))
                travel=e['length']/(speed*(stair if e.get('kind')=='stair' else 1)*factor)
                heapq.heappush(queue,(cost+travel,e['to'],path+(i,)))
        return None
    time=0.
    initial_vis=visibility(0)
    unreachable=[node for node in {a['node'] for a in agents} if node not in safe and route(node,initial_vis) is None]
    if unreachable:raise ValueError('Initially unreachable spawn nodes: '+', '.join(unreachable))
    while time<horizon:
        step=min(dt,horizon-time);vis=visibility(time)
        capacities=np.array([e['capacity'] for e in edges])
        tokens=np.minimum(1.+step*capacities,tokens+step*capacities)
        # Complete transit before releasing new agents; no agent crosses two
        # links in a single step. Occupants on closed links stop in place.
        completed_transit=set()
        for index,a in enumerate(agents):
            if a['exit'] is not None:continue
            if a['edge'] is not None:
                e=edges[a['edge']];v=min(vis[e['from']],vis[e['to']])
                if v>=1:
                    factor=min(1.,max(.1,v/10))
                    a['remaining']-=speed*(stair if e.get('kind')=='stair' else 1)*factor*step
                if a['remaining']<=0:
                    a.update(node=e['to'],edge=None,ready=time+step);completed_transit.add(index)
                    if a['node'] in safe:a['exit']=time+step
        for index,a in enumerate(agents):
            if a['exit'] is not None or a['edge'] is not None or a['ready']>time or index in completed_transit:continue
            if a['node'] in safe:a['exit']=time;continue
            chosen=route(a['node'],vis)
            if chosen is not None and tokens[chosen]>=1-1e-12:
                tokens[chosen]-=1;departures[chosen]+=1;a.update(edge=chosen,remaining=edges[chosen]['length'])
        time+=step
        complete = all(a['exit'] is not None for a in agents)
        if len(rows)==0 or time-rows[-1]['time']>=1 or time>=horizon or complete:
            evacuated=sum(a['exit'] is not None for a in agents)
            rows.append(dict(time=time,evacuated=evacuated,remaining=len(agents)-evacuated,
                occupants={node:sum(a['node']==node and a['edge'] is None and a['exit'] is None for a in agents) for node in nodes}))
        if complete:break
    exits=[a['exit'] for a in agents if a['exit'] is not None]
    return dict(model='network-capacity-visibility-v1',config=data,time=time,agents=len(agents),evacuated=len(exits),
        censored=len(exits)<len(agents),completion_time=max(exits) if len(exits)==len(agents) and exits else None,
        exit_times=exits,link_departures=departures.tolist(),telemetry=rows,
        assumptions='Directed capacity network; visibility below 1 m closes a link, 1–10 m scales walking speed linearly. Stair speed = user factor × walking speed. No CFD, toxic dose or physical contact.')
