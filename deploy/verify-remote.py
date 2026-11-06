"""Read-only deployment checks, run inside the API container."""
import json
import sqlite3
from urllib.request import urlopen
from boardgame.platform import Platform
from boardgame.mcp import MCP

with sqlite3.connect('/data/boardgame.sqlite3') as live, sqlite3.connect('/snapshot.sqlite3') as snapshot:
    assert live.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    counts = {}
    for table in ('identities', 'rooms', 'members', 'journal', 'requests'):
        expected = sorted(snapshot.execute(f'SELECT * FROM {table}').fetchall(), key=repr)
        actual = sorted(live.execute(f'SELECT * FROM {table}').fetchall(), key=repr)
        assert expected == actual, f'Data mismatch: {table}'
        counts[table] = len(actual)
    print('Migrated data matches snapshot:', json.dumps(counts))
    identity_id = live.execute('SELECT id FROM identities LIMIT 1').fetchone()[0]
p = Platform('/data/boardgame.sqlite3')
mcp = MCP(p)
# Read-only tools use the existing identity; no tokens are changed or extracted.
result = mcp.handle({'id': identity_id}, {'jsonrpc':'2.0','id':1,'method':'tools/call',
    'params': {'name':'get_game_rules','arguments':{'game_id':'fcm'}}})
assert not result['result']['isError'], result
book = json.loads(result['result']['content'][0]['text'])
assert book['game']['employees']['cart_operator']['name_zh'] == '采购专员'
assert '营销 API 坐标约定' in book['rules_text']
print('MCP rulebook and employee labels verified')
assert json.load(urlopen('http://127.0.0.1:8000/health'))['status'] == 'ok'
print('API health verified')
