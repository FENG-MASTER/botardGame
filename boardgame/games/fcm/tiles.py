"""Transcribed TTS board data. The engine uses cells, never image recognition."""
import json
import random
from copy import deepcopy
from pathlib import Path

TILES = json.loads((Path(__file__).parent / 'data' / 'tiles.json').read_text())
BY_ID = {t['id']: t for t in TILES}
SYMBOLS = {'.':'empty', 'R':'road', 'X':'bridge', 'B':'beer', 'S':'soda', 'L':'lemonade', 'H':'house', 'P':'park'}
NEW_HOUSES = [1, 3, 6, 9, 11, 14, 17, 19]


def rotated(tile_id, turns=0):
    data = deepcopy(BY_ID[tile_id])
    for _ in range(turns % 4):
        data['grid'] = [list(row) for row in zip(*data['grid'][::-1])]
        for house in data['houses']:
            house['cells'] = [[4-y, x] for x,y in house['cells']]
    return data


def generated(players, seed, modules=()):
    cols, rows = {2:(3,3), 3:(3,4), 4:(4,4), 5:(5,4), 6:(6,4)}[players]
    pool = [t['id'] for t in TILES if t['module']=='base'
            or (t['module']=='new_districts' and 'new_districts' in modules)
            or (t['module']=='parks' and 'new_districts' in modules and 'lobbyists' in modules)]
    rng = random.Random(seed)
    rng.shuffle(pool)
    board = dict(width=cols*5, height=rows*5,
                 cells=[['empty']*(cols*5) for _ in range(rows*5)], houses=[], tiles=[], available_tiles=pool[cols*rows:])
    for i, tile_id in enumerate(pool[:cols*rows]):
        tx,ty=i%cols,i//cols
        turns=rng.randrange(4)
        t=rotated(tile_id,turns)
        board['tiles'].append(dict(id=tile_id,x=tx,y=ty,rotation=turns))
        for y,row in enumerate(t['grid']):
            for x,c in enumerate(row):board['cells'][ty*5+y][tx*5+x]=SYMBOLS[c]
        for h in t['houses']:
            h['cells']=[[tx*5+x,ty*5+y] for x,y in h['cells']]
            h.update(printed=True,demand=[],demand_sources=[])
            board['houses'].append(h)
    return board
