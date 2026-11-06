"""Room contracts must not advertise or accept disabled expansion content."""
from copy import deepcopy
import json
import tempfile
import unittest
from boardgame.core import GameError
from boardgame.games.fcm.engine import FCM
from boardgame.games.fcm.catalog import BASE_PRODUCTS, MODULE_KINDS, PRODUCTS
from boardgame.games.fcm.modules import MODULES
from boardgame.games.fcm.scope import action_schema
from boardgame.platform import Platform, encode
from boardgame.mcp import MCP, rules
from boardgame.server import Handler
from types import SimpleNamespace
from test_transport import Connection


class RoomScopeTests(unittest.TestCase):
    def test_every_module_and_combinations_expose_only_enabled_content(self):
        g = FCM()
        configs = [[], *([m] for m in MODULES if m != 'six_players'),
                   ['sushi','kimchi'], ['coffee','new_milestones','lobbyists'],
                   ['six_players','new_districts'],
                   [m for m in MODULES if m not in ('six_players','hard_choices')]]
        for modules in configs:
            with self.subTest(modules=modules):
                config={'modules':modules}
                s=g.create(list('abcdef') if 'six_players' in modules else ['a','b'],config,7)
                original=deepcopy(s)
                view=g.observe(s,'a'); cat=g.room_descriptor(config)
                allowed=set(BASE_PRODUCTS) | (set(modules)&{'coffee','sushi','kimchi','noodles'})
                self.assertEqual(set(cat['products']),allowed)
                for company in view['players'].values():
                    self.assertEqual(set(company['inventory']),allowed)
                    self.assertEqual('coffee_shops' in company,'coffee' in modules)
                for module,kinds in MODULE_KINDS.items():
                    for kind in kinds:self.assertEqual(kind in cat['employees'],module in modules)
                for card in cat['employees'].values():
                    self.assertTrue(set(card['upgrades'])<=cat['employees'].keys())
                for field,module in [('lobby_supply','lobbyists'),('roadworks','lobbyists'),('built_features','lobbyists'),('offramps','rural_marketeers'),('rural','rural_marketeers'),('coffee_bonus','coffee')]:
                    self.assertEqual(field in view,module in modules)
                self.assertEqual('available_tiles' in view['board'],'lobbyists' in modules)
                s.update(phase='work',queue=['a'])
                options=g.actions(s,'a'); work=options['actions'][0]['schema']['properties']
                self.assertEqual('lobby' in work,'lobbyists' in modules)
                self.assertEqual('lobby_components' in options,'lobbyists' in modules)
                self.assertEqual('lobby' in options['plan_order'],'lobbyists' in modules)
                self.assertEqual('coffee_shops' in work['train']['items']['properties'],'coffee' in modules)
                market=work['market']['items']['properties']
                self.assertEqual(set(market['product']['enum']),set(BASE_PRODUCTS))
                self.assertEqual('offramp' in market,'rural_marketeers' in modules)
                self.assertEqual('second_campaign' in market,'new_milestones' in modules)
                self.assertEqual(set(work['train']['items']['properties']['path']['items']['enum']),set(cat['employees']))
                self.assertEqual(set(work['produce']['items']['properties']['product']['enum']),allowed-{'kimchi'})
                keep=action_schema('cleanup',s)['properties']['keep']['properties']
                self.assertEqual(set(keep),allowed-{'coffee'})
                self.assertEqual('food' in action_schema('payday',s)['properties'],'new_milestones' in modules)
                self.assertEqual(action_schema('choose_reserve',s)['properties']['amount']['enum'],[5,10,20] if 'reserve_prices' in modules else [100,200,300])
                self.assertEqual(original['players'],s['players']) # projection does not rewrite replay state
        self.assertEqual(len(g.descriptor()['products']),9) # explicit platform catalog
        self.assertEqual(g.descriptor()['scope'],'platform_catalog')
        self.assertEqual(g.room_descriptor({'introductory':True})['milestones'],[])

    def test_custom_scenarios_cannot_bypass_module_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Platform(tmp+'/db'); a=p.register('a','human')
            tiles={'17':dict(kind='guide',width=1,height=1)}
            with self.assertRaises(GameError):
                p.create_room(a['id'],'fcm',2,{'scenario':{'campaign_tiles':tiles}},1)
            room=p.create_room(a['id'],'fcm',2,{'modules':['gourmet_critics'],'scenario':{'campaign_tiles':tiles}},1)
            self.assertIn('gourmet_food_critic',room['catalog']['employees'])

    def test_http_mcp_input_validation_cached_responses_and_public_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Platform(tmp+'/db');a=p.register('a','human');b=p.register('b','agent')
            room=p.create_room(a['id'],'fcm',2,{},7);rid=room['id']
            p.join(b['id'],rid,room['join_code'])
            p.mutate(a['id'],rid,1,'start',{'type':'start'},start=True)
            # Simulate a pre-release cached response that includes all products.
            with p.connect(True) as db:
                row=db.execute('SELECT response FROM requests WHERE key="start"').fetchone()
                cached=json.loads(row[0]);cached.pop('catalog')
                for company in cached['state']['players'].values():company['inventory']={k:0 for k in PRODUCTS}
                db.execute('UPDATE requests SET response=? WHERE key="start"',(encode(cached),))
                state=json.loads(db.execute('SELECT state FROM rooms WHERE id=?',(rid,)).fetchone()[0])
                state.update(phase='work',queue=[a['id']])
                db.execute('UPDATE rooms SET state=? WHERE id=?',(encode(state),rid))
            retry=p.mutate(a['id'],rid,1,'start',{'type':'start'},start=True)
            self.assertEqual(set(retry['state']['players'][a['id']]['inventory']),set(BASE_PRODUCTS))
            self.assertEqual(retry['catalog']['scope'],'room')
            before=p.get(a['id'],rid)
            for action in [dict(type='work',lobby=[]),dict(type='work',train=[dict(trainer='x',employee='y',path=['sushi_cook'])]),dict(type='work',produce=[dict(employee='x',product='sushi')]),dict(type='cleanup',keep={'sushi':0}),dict(type='payday',food={}),dict(type='work',train=[dict(trainer='x',path=['burger_cook'],coffee_shops=[])])]:
                for dry_run in (True,False):
                    with self.subTest(action=action,dry_run=dry_run),self.assertRaises(GameError) as err:
                        p.mutate(a['id'],rid,before['version'],'bad',action,dry_run=dry_run)
                    self.assertEqual(err.exception.code,'invalid_parameters')
            self.assertEqual(p.get(a['id'],rid),before)
            api=SimpleNamespace(platform=p,registration_key=None,server_name='localhost',server_port=8000)
            conn=Connection(f'GET /v1/rooms/{rid} HTTP/1.0\r\nAuthorization: Bearer {a["token"]}\r\n\r\n'.encode())
            Handler(conn,('127.0.0.1',1),api)
            header,body=bytes(conn.output).split(b'\r\n\r\n',1)
            self.assertIn(b'200',header.splitlines()[0]);http=json.loads(body)
            mcp=MCP(p)
            observed=mcp.call_tool(a,'observe_game',{'room_id':rid})
            self.assertEqual(http,observed)
            self.assertEqual(mcp.call_tool(a,'get_available_actions',{'room_id':rid})['actions'],p.actions(a['id'],rid)['actions'])
            self.assertEqual(set(http['catalog']['products']),set(BASE_PRODUCTS))
            book=rules(p,'fcm',http)
            self.assertEqual(book['module_rules'],{})
            self.assertNotIn('implementation_notes',book)
            self.assertEqual(book['rules_text'],book['room_rules_text'])
            self.assertNotIn('sushi_cook',json.dumps(book))
            self.assertEqual(book['game']['products'],BASE_PRODUCTS)
            with p.connect(True) as db:
                events=[dict(type='salaries_paid',player=a['id'],round=1,phase='payday',food={})]
                db.execute('UPDATE journal SET events=? WHERE room=? AND version=2',(encode(events),rid))
            public=p.events(a['id'],rid)['events'][-1]['events'][0]
            self.assertNotIn('food',public)
