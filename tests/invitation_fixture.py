"""Explicit eligible sponsor fixture; never used by production code."""
import time

def invite(platform):
    sponsor = platform.register('Fixture sponsor', 'human')
    with platform.connect(True) as db:
        for delta in (1, 2):
            now = time.time() - delta * 86400
            db.execute('INSERT INTO login_days VALUES(?,?,?)', (sponsor['id'], platform.login_day(now), now))
    return platform.create_invitation(sponsor['id'])['code']
