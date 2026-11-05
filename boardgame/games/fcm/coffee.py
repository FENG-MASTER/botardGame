"""Coffee routing: shortest tile distance, then most cups, then common stops.

Road lanes remain separate at bridges. Search states include the set of shops
already served, so zero-cost travel inside a tile cannot yield repeated cups.
"""
from collections import Counter, deque
from itertools import combinations, product
from . import board as geo


def stops(engine,s,house,winner):
    b=s['board'];locations=[]
    for pid in engine.living(s):
        p=s['players'][pid]
        if not p['inventory']['coffee']:continue
        for r in p['restaurants']:
            if r['open']:
                drive=any(e['kind'] in ('local_manager','regional_manager') for e in engine.active(p))
                locations.append(dict(id=r['id'],player=pid,cells=r['cells'] if drive else [r['entrance']]))
        for r in p['coffee_shops']:locations.append(dict(r,player=pid))
    if not locations:return []
    costs=geo.distances(b,house['cells'],s['roadworks'])
    barriers=Counter(map(tuple,s['roadworks']))
    adjacent={}
    for node in costs:
        x,y,lane=node
        adjacent[node]=[i for i,v in enumerate(locations) if any(
            abs(x-p[0])+abs(y-p[1])==1 and (not lane or lane==('h' if x!=p[0] else 'v'))
            for p in v['cells'])]
    destinations=[];best=999
    p=s['players'][winner]
    drive=any(e['kind'] in ('local_manager','regional_manager') for e in engine.active(p))
    for r in p['restaurants']:
        if not r['open']:continue
        ends=r['cells'] if drive else [r['entrance']]
        for end in ends:
            for q in geo.neighbors(end):
                lane=('h' if q[0]!=end[0] else 'v') if geo.road(b,q) and b['cells'][q[1]][q[0]]=='bridge' else ''
                node=(*q,lane);d=costs.get(node,999)+int(geo.tile(end)!=geo.tile(q))
                if d<best:best=d;destinations=[]
                if d==best:destinations.append((r['id'],node))
    if best>=999:return []
    by_destination={}
    for rid,node in destinations:by_destination.setdefault(rid,set()).add(node)
    final=[]
    for rid,ends in by_destination.items():
        start_nodes=[]
        for p0 in house['cells']:
            for q in geo.neighbors(p0):
                lane=('h' if q[0]!=p0[0] else 'v') if geo.road(b,q) and b['cells'][q[1]][q[0]]=='bridge' else ''
                node=(*q,lane)
                if costs.get(node,999)==int(geo.tile(p0)!=geo.tile(q))+barriers[q]:start_nodes.append(node)
        queue=deque((v,0,()) for v in start_nodes);seen=set()
        while queue:
            node,mask,path=queue.popleft()
            if (node,mask) in seen:continue
            seen.add((node,mask))
            groups={}
            consumed=Counter(locations[i]['player'] for i in range(len(locations)) if mask>>i&1)
            for i in adjacent.get(node,[]):
                loc=locations[i]
                if loc['id']!=rid and not mask>>i&1:groups.setdefault(loc['player'],[]).append(i)
            choices=[]
            for owner,indices in sorted(groups.items()):
                count=min(len(indices),max(0,s['players'][owner]['inventory']['coffee']-consumed[owner]))
                choices.append(list(combinations(indices,count)))
            for selection in product(*choices):
                picked=tuple(i for group in selection for i in group)
                newmask=mask|sum(1<<i for i in picked);newpath=path+picked
                if node in ends:final.append((newmask,newpath))
                x,y,lane=node
                for q in geo.neighbors((x,y)):
                    direction='h' if q[0]!=x else 'v'
                    if not geo.road(b,q) or lane and lane!=direction:continue
                    nxt=(*q,direction if b['cells'][q[1]][q[0]]=='bridge' else '')
                    distance=costs[node]+int(geo.tile((x,y))!=geo.tile(q))+barriers[q]
                    if costs.get(nxt,999)==distance and distance<=best:
                        queue.append((nxt,newmask,newpath))
    if not final:return []
    maximum=max(mask.bit_count() for mask,path in final)
    finalists=[(mask,path) for mask,path in final if mask.bit_count()==maximum]
    common=finalists[0][0]
    for mask,path in finalists[1:]:common &= mask
    return [locations[i] for i in finalists[0][1] if common>>i&1]
