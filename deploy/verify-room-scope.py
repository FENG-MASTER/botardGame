"""Verify room-scoped contracts on a disposable production snapshot, without tokens."""
import sys
from boardgame.platform import Platform
from boardgame.mcp import rules
from boardgame.games.fcm.scope import products
p=Platform(sys.argv[1])
with p.connect() as db:
    rooms=[dict(r) for r in db.execute('SELECT * FROM rooms')]
for row in rooms:
    room=p.get(row['owner'],row['id'])
    allowed=set(products(room['config'].get('modules',[])))
    assert set(room['catalog']['products'])==allowed
    if room['state']:
        for company in room['state']['players'].values():
            assert set(company['inventory'])==allowed
        assert p.replay(row['id'])['valid']
        with p.connect() as db: assert p.legacy_event_history(db,row) is not None
    book=rules(p,room['game'],room)
    assert set(book['game']['products'])==allowed
    assert set(book['module_rules'])==set(room['config'].get('modules',[]))
    assert book['rules_text']==book['room_rules_text']
    print('Room scope / replay verified:',row['id'],'version',row['version'],'products',sorted(allowed))
