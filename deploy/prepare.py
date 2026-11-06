"""Build a private deployment archive with a consistent SQLite snapshot."""
import json
import os
from pathlib import Path
import sqlite3
import tarfile
import tempfile

root = Path(__file__).resolve().parent.parent
out = root / 'deploy' / 'artifacts'
out.mkdir(exist_ok=True, mode=0o700)
os.chmod(out, 0o700)
with tempfile.TemporaryDirectory() as tmp:
    snapshot = Path(tmp) / 'boardgame.sqlite3'
    with sqlite3.connect((root / 'boardgame.sqlite3').as_uri() + '?mode=ro', uri=True) as source:
        with sqlite3.connect(snapshot) as target:
            source.backup(target)
            assert target.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            counts = {table: target.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                      for table in ('identities', 'rooms', 'members', 'journal', 'requests')}
    def select(info):
        if any(part in {'.git', '.venv', 'node_modules', '__pycache__', 'artifacts'} for part in Path(info.name).parts):
            return None
        if Path(info.name).name.startswith('.env') or info.name.endswith('.pyc'):
            return None
        return info
    archive = out / 'boardgame-release.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        for item in ('boardgame', 'human-ui', 'pyproject.toml', 'uv.lock', '.python-version',
                     'README.md', 'Dockerfile', '.dockerignore', 'doc/FCM_RULES.md',
                     'doc/FCM_IMPLEMENTATION.md', 'doc/FCM_EXPANSIONS.md'):
            bundle.add(root / item, arcname=item, filter=select)
        bundle.add(snapshot, arcname='migration/boardgame.sqlite3')
        bundle.add(root / 'deploy/install-remote.sh', arcname='deploy/install-remote.sh')
        bundle.add(root / 'deploy/generate-tls.sh', arcname='deploy/generate-tls.sh')
    os.chmod(archive, 0o600)
    (out / 'snapshot-counts.json').write_text(json.dumps(counts, indent=2) + '\n')
    print(archive)
    print(json.dumps(counts))
