"""Read-only comparison against the pre-release backup; run with sudo on server."""
import sqlite3
import json
backup='/home/ubuntu/botardgame/backups/before-scope-20261106.sqlite3'
with sqlite3.connect('file:/home/ubuntu/botardgame/data/boardgame.sqlite3?mode=ro',uri=True) as live, sqlite3.connect('file:'+backup+'?mode=ro',uri=True) as old:
    assert live.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    counts={}
    for table in ('identities','rooms','members','journal','requests'):
        a=sorted(old.execute(f'SELECT * FROM {table}').fetchall(),key=repr)
        b=sorted(live.execute(f'SELECT * FROM {table}').fetchall(),key=repr)
        assert a==b,table+' changed: inspect legitimate activity before assuming migration failure'
        counts[table]=len(b)
    print('Original gameplay and credentials unchanged:',json.dumps(counts))
    print('Invitation audit rows:',live.execute('SELECT count(*) FROM invitations').fetchone()[0])
    print('Users currently eligible:',live.execute('SELECT count(*) FROM (SELECT player FROM login_days GROUP BY player HAVING count(*)>=3)').fetchone()[0])
    print('Recorded login days per existing user:',[r[0] for r in live.execute('SELECT count(*) FROM login_days GROUP BY player')])
