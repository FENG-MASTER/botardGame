import json
import tempfile
import unittest
from boardgame.platform import Platform, encode
from examples.play_agents import choose

class RoundEventTests(unittest.TestCase):
    def test_reconstruct_legacy_rounds_without_leaking_secret_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Platform(tmp+'/db')
            users=[p.register('a','human'),p.register('b','agent')]
            ids=[u['id'] for u in users]
            room=p.create_room(ids[0],'fcm',2,seed=7)
            rid=room['id'];p.join(ids[1],rid,room['join_code'])
            room=p.mutate(ids[0],rid,1,'start',{'type':'start'},start=True)
            for step in range(150):
                if room['state']['round']>=3:break
                for pid in ids:
                    options=p.actions(pid,rid)
                    if options['can_act']:
                        room=p.mutate(pid,rid,options['version'],str(step)+'-'+pid,choose(pid,p.get(pid,rid),options))
                        break
            self.assertEqual(room['state']['round'],3)
            observation_before=p.get(ids[0],rid)
            before=p.events(ids[0],rid)['events']
            flat=[e for b in before for e in b['events']]
            self.assertTrue(any(e['type']=='round_started' and e['round']==3 for e in flat))
            self.assertTrue(any(e['type']=='work_completed' and e['round']==2 for e in flat))
            self.assertTrue(all('amount' not in e and 'structure' not in e for e in flat if e['type']=='action_submitted'))
            with p.connect(True) as db:
                for row in db.execute('SELECT version,events FROM journal WHERE room=?',(rid,)).fetchall():
                    events=json.loads(row['events'])
                    old=[{k:v for k,v in e.items() if k not in ('round','phase','plan')} for e in events if e['type']!='round_started']
                    db.execute('UPDATE journal SET events=? WHERE room=? AND version=?',(encode(old),rid,row['version']))
            p._event_history_cache.clear()
            recovered=p.events(ids[1],rid)['events']
            recovered_flat=[e for b in recovered for e in b['events']]
            self.assertTrue(all('round' in e for e in recovered_flat))
            self.assertTrue(any(e['type']=='work_completed' and e['plan'] for e in recovered_flat))
            self.assertTrue(any(e['type']=='round_started' and e['round']==3 for e in recovered_flat))
            self.assertEqual(p.get(ids[0],rid),observation_before)
            # Failed reconstruction must not guess a round or return raw actions.
            p._event_history_cache.clear()
            with p.connect(True) as db:
                state=json.loads(db.execute('SELECT state FROM rooms WHERE id=?',(rid,)).fetchone()[0])
                state['bank']+=1
                db.execute('UPDATE rooms SET state=? WHERE id=?',(encode(state),rid))
            self.assertFalse(any(e['type']=='round_started' for b in p.events(ids[0],rid)['events'] for e in b['events']))
