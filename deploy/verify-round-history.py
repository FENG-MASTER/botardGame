"""Read-only history validation against a disposable SQLite snapshot."""
import sys
from boardgame.platform import Platform
p=Platform(sys.argv[1])
with p.connect() as db:
    rooms=[dict(r) for r in db.execute('SELECT * FROM rooms')]
    for room in rooms:
        if room['state'] is None: continue
        history=p.legacy_event_history(db,room)
        assert history is not None, 'Legacy replay mismatch: '+room['id']
        state=__import__('json').loads(room['state'])
        events=[e for batch in history.values() for e in batch]
        current=[e for e in events if e.get('round')==state['round']]
        assert current, 'Missing current-round history'
        assert all('round' in e for e in events)
        print('Verified',room['id'],'version',room['version'],'round',state['round'],'current events',len(current))
