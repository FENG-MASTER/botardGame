"""Expansion components transcribed from TTS 2202544434 and rules pp. 7, 15."""
from copy import deepcopy
from boardgame.core import require, integer
from . import board as geo
from . import tiles

PIECES = {
    'road_short': dict(cells=[[0,0],[1,0]], arrows=[[-1,0],[2,0]], count=4, kind='road'),
    'road_long': dict(cells=[[0,0],[1,0],[2,0],[3,0]], arrows=[[-1,0],[4,0]], count=2, kind='road'),
    'road_corner': dict(cells=[[0,0],[1,0],[1,1]], arrows=[[-1,0],[1,2]], count=2, kind='road'),
    'park_t': dict(cells=[[0,0],[1,0],[2,0],[1,1]], count=1, kind='park'),
    'park_left': dict(cells=[[0,0],[1,0],[2,0],[0,1]], count=1, kind='park'),
    'park_right': dict(cells=[[0,0],[1,0],[2,0],[2,1]], count=1, kind='park'),
    'park_long': dict(cells=[[0,0],[1,0],[2,0],[3,0]], count=1, kind='park'),
}
SIDES = {'left':(-1,0), 'right':(1,0), 'top':(0,-1), 'bottom':(0,1)}


def piece(kind, turns, position):
    data=deepcopy(PIECES[kind]); area=data['cells']; arrows=data.get('arrows',[])
    for _ in range(turns):
        height=max(y for x,y in area)+1
        area=[[height-1-y,x] for x,y in area]
        arrows=[[height-1-y,x] for x,y in arrows]
    x,y=position
    return [[x+a,y+b] for a,b in area], [[x+a,y+b] for a,b in arrows]


def tile_positions(b):
    return {(x,y) for y in range(b['height']//5) for x in range(b['width']//5)
            if any(b['cells'][v][u]!='void' for v in range(y*5,y*5+5) for u in range(x*5,x*5+5))}



def edge_cells(tx,ty,side):
    if side=='left': return [[tx*5-1,ty*5+i] for i in range(5)]
    if side=='right': return [[tx*5+5,ty*5+i] for i in range(5)]
    if side=='top': return [[tx*5+i,ty*5-1] for i in range(5)]
    return [[tx*5+i,ty*5+5] for i in range(5)]


def edge_clear(s, tx, ty, side):
    b=s['board'];dx,dy=SIDES[side]
    if (tx,ty) not in tile_positions(b) or (tx+dx,ty+dy) in tile_positions(b):return False
    for ramp in s.get('offramps',[]):
        if ramp['tile']==[tx,ty] and ramp['side']==side:return False
    axis=ty if side in ('left','right') else tx
    line={'left':tx*5,'right':tx*5+5,'top':ty*5,'bottom':ty*5+5}[side]
    return not any(c['kind']=='airplane' and c['side']==side and
                   c.get('edge_line',{'left':0,'right':b['width'],'top':0,'bottom':b['height']}[side])==line and
                   max(axis*5,c['offset'])<min(axis*5+5,c['offset']+c['span']) for c in s['campaigns'])



def add_offramp(s,a):
    require(len(s['offramps'])<3,'All three highway offramps have been used')
    tx,ty=a.get('tile',[None,None]);integer(tx,0,s['board']['width']//5-1,'tile.x');integer(ty,0,s['board']['height']//5-1,'tile.y')
    side=a.get('side');require(side in SIDES,'Invalid highway side')
    require(edge_clear(s,tx,ty,side),'Highway must occupy an exposed tile edge without airplane or highway')
    area=edge_cells(tx,ty,side);dx,dy=SIDES[side]
    require(any(geo.road(s['board'],(x-dx,y-dy)) for x,y in area),'Highway must connect to a road')
    s['offramps'].append(dict(tile=[tx,ty],side=side,cells=area))


def translate(s,dx,dy):
    def points(area):
        for p in area:p[0]+=dx;p[1]+=dy
    for h in s['board']['houses']:points(h['cells'])
    for t in s['board'].get('tiles',[]):t['x']+=dx//5;t['y']+=dy//5
    for p in s['players'].values():
        for r in p['restaurants']:
            entrance=[r['entrance'][0]+dx,r['entrance'][1]+dy]
            points(r['cells']);r['entrance']=entrance
        for shop in p['coffee_shops']:points(shop['cells'])
    for c in s['campaigns']:
        points(c['cells'])
        if c['kind']=='airplane':
            c['offset']+=dy if c['side'] in ('left','right') else dx
            if 'edge_line' in c:c['edge_line']+=dx if c['side'] in ('left','right') else dy
    for ramp in s.get('offramps',[]):
        points(ramp['cells']);ramp['tile'][0]+=dx//5;ramp['tile'][1]+=dy//5
    points(s.get('roadworks',[]))
    for feature in s.get('built_features',[]):points(feature['cells'])


def add_city(s,a):
    b=s['board'];tid=a.get('tile_id');require(tid in b.get('available_tiles',[]) and tid in tiles.BY_ID,'City tile is not available')
    pos=a.get('tile');require(isinstance(pos,list) and len(pos)==2,'tile must be [column,row]')
    tx=integer(pos[0],-1,b['width']//5,'tile.x');ty=integer(pos[1],-1,b['height']//5,'tile.y')
    occupied=tile_positions(b);require((tx,ty) not in occupied,'Tile position occupied')
    touching=[(side,tx-dx,ty-dy) for side,(dx,dy) in SIDES.items() if (tx-dx,ty-dy) in occupied]
    require(touching,'New tile must share a complete side with an existing tile')
    require(all(edge_clear(s,x,y,side) for side,x,y in touching),'New tile overlaps airplane or highway')
    turns=integer(a.get('rotation',0),0,3,'rotation');data=tiles.rotated(tid,turns)
    dx=5 if tx<0 else 0;dy=5 if ty<0 else 0
    width=max(b['width']+dx,(tx+1)*5+dx);height=max(b['height']+dy,(ty+1)*5+dy)
    grid=[['void']*width for _ in range(height)]
    for y,row in enumerate(b['cells']):grid[y+dy][dx:dx+b['width']]=row
    translate(s,dx,dy);tx+=dx//5;ty+=dy//5
    b.update(width=width,height=height,cells=grid)
    for y,row in enumerate(data['grid']):
        for x,symbol in enumerate(row):grid[ty*5+y][tx*5+x]=tiles.SYMBOLS[symbol]
    for h in data['houses']:
        h['cells']=[[tx*5+x,ty*5+y] for x,y in h['cells']]
        h.update(printed=True,demand=[],demand_sources=[],order={'π':3.141592653589793,'9¾':9.75}.get(h['id'],h['id']))
        b['houses'].append(h)
    b.setdefault('tiles',[]).append(dict(id=tid,x=tx,y=ty,rotation=turns));b['available_tiles'].remove(tid)


def lobby(engine,s,pid,a):
    kind=a.get('piece');require(kind in PIECES and s['lobby_supply'][kind]>0,'Construction component unavailable')
    position=geo.point(s['board'],a.get('position'));turns=integer(a.get('rotation',0),0,3,'rotation')
    area,arrows=piece(kind,turns,position);geo.empty(s,area)
    require(geo.distance(s['board'],geo.entrances(s,pid),area)<=2,'Lobbyist is out of range')
    road=PIECES[kind]['kind']=='road'
    if road:
        entries=geo.entrances(s,pid,coffee=False)
        require(any(geo.road(s['board'],q) or tuple(q) in entries for q in arrows),'An arrow must point to an existing road or own restaurant entrance')
        s['roadworks'] += [q for q in arrows if geo.road(s['board'],q)]
    for x,y in area:s['board']['cells'][y][x]='construction' if road else 'park'
    s['built_features'].append(dict(cells=deepcopy(area),kind='road' if road else 'park'))
    s['lobby_supply'][kind]-=1
    fresh=engine.grant(s,pid,'first_lobbyist_used')
    if fresh and s['board'].get('available_tiles'):
        require(a.get('city') is not None,'First lobbyist use requires choosing an additional city tile')
        add_city(s,a['city'])
    else:require(not a.get('city'),'No city tile bonus available')


def shop(s,pid,a,unlimited=False):
    p=s['players'][pid];pos=list(geo.point(s['board'],a.get('position')));moving=a.get('shop_id')
    old=next((v for v in p['coffee_shops'] if v['id']==moving),None)
    require(not moving or old is not None,'Unknown coffee shop')
    require(not moving or len(p['coffee_shops'])==3,'Move a coffee shop only after all three tokens are placed')
    require(old or len(p['coffee_shops'])<3,'Choose an existing shop to move')
    geo.empty(s,[pos],exclude=moving)
    require(any(geo.road(s['board'],q) for q in geo.neighbors(pos)),'Coffee shop must border a road')
    require(not any(geo.tile(v['cells'][0])==geo.tile(pos) for player in s['players'].values() for v in player['coffee_shops'] if v is not old),'Only one coffee shop per city tile')
    require(unlimited or geo.distance(s['board'],geo.entrances(s,pid),[pos])<=2,'Coffee shop is beyond range 2')
    if old:p['coffee_shops'].remove(old)
    p['coffee_shops'].append(dict(id=moving or pid+':c'+str(len(p['coffee_shops'])+1),cells=[pos]))


def multiplier(s,h):
    park=any(geo.inside(s['board'],q) and s['board']['cells'][q[1]][q[0]]=='park' for v in h['cells'] for q in geo.neighbors(v))
    return 1+int(h['garden'])+int(park)
