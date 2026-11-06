"""Run with sudo on the production host while boardgame containers are stopped."""
import json
import os
from pathlib import Path
import sqlite3
import sys

source = Path('/home/ubuntu/botardgame/data/boardgame.sqlite3')
target = Path(sys.argv[1])
if target.exists():
    raise SystemExit('Refusing to overwrite existing backup')
target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
os.chmod(target.parent, 0o700)
os.umask(0o077)
with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as src, sqlite3.connect(target) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    counts={t:dst.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('identities','rooms','members','journal','requests')}
print('Backup verified:', target, json.dumps(counts))
