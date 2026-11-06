import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch
from boardgame.platform import Platform
from boardgame.core import GameError
from boardgame.server import Handler
from boardgame.mcp import MCP
from test_transport import Connection

class InvitationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Platform(self.tmp.name+'/db')
        self.now = 1793894400.0
        with patch('boardgame.platform.time.time', return_value=self.now):
            self.a = self.p.register('Alice', 'human')
    def tearDown(self): self.tmp.cleanup()
    def login(self, day):
        with patch('boardgame.platform.time.time', return_value=self.now + day*86400):
            self.p.authenticate(self.a['token'])
    def eligible(self):
        self.login(1); self.login(2)
    def test_three_distinct_days_and_invalid_token(self):
        self.login(0); self.login(0)
        self.assertEqual(self.p.invitations(self.a['id'])['login_days'], 1)
        with self.assertRaises(GameError): self.p.create_invitation(self.a['id'])
        self.login(2)
        with self.assertRaises(GameError): self.p.create_invitation(self.a['id'])
        with self.assertRaises(GameError): self.p.authenticate('wrong')
        self.login(4)
        self.assertTrue(self.p.invitations(self.a['id'])['eligible'])
        self.assertNotEqual(self.p.login_day(1793894399), self.p.login_day(1793894399+86400))
    def test_single_use_atomic_audit_and_private_history(self):
        self.eligible()
        issued=self.p.create_invitation(self.a['id'])
        def use(i):
            try: return self.p.register('Guest'+str(i), 'agent', issued['code'], require_invite=True)
            except GameError: return None
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(use, range(2)))
        users=[u for u in results if u]
        self.assertEqual(len(users),1)
        history=self.p.invitations(self.a['id'])['invitations'][0]
        self.assertEqual(history['status'],'used')
        self.assertEqual(history['invitee'],users[0]['id'])
        self.assertNotIn(issued['code'],json.dumps(history))
        self.assertEqual(self.p.invitations(users[0]['id'])['invitations'],[])
        with self.p.connect() as db:
            self.assertNotEqual(db.execute('SELECT code_hash FROM invitations').fetchone()[0],issued['code'])
    def test_expiry_revocation_limits_and_mcp(self):
        self.eligible()
        issued=self.p.create_invitation(self.a['id'])
        outsider=self.p.register('Outsider','agent')
        with self.assertRaises(GameError): self.p.revoke_invitation(outsider['id'],issued['id'])
        self.p.revoke_invitation(self.a['id'],issued['id'])
        with self.assertRaises(GameError): self.p.register('X','human',issued['code'],require_invite=True)
        issued=self.p.create_invitation(self.a['id'])
        with patch('boardgame.platform.time.time',return_value=issued['expires']):
            with self.assertRaises(GameError): self.p.register('X','human',issued['code'],require_invite=True)
        for _ in range(9): self.p.create_invitation(self.a['id'])
        with self.assertRaises(GameError) as error: self.p.create_invitation(self.a['id'])
        self.assertEqual(error.exception.status,429)
        mcp=MCP(self.p)
        self.assertTrue(mcp.call_tool(self.a,'get_invitations',{})['eligible'])
        with self.assertRaises(GameError): mcp.call_tool(outsider,'create_invitation',{})
    def test_http_registration_requires_invite_and_records_use(self):
        server=SimpleNamespace(platform=self.p, registration_key=None, server_name='localhost',server_port=80)
        def register(body):
            encoded=json.dumps(body).encode()
            conn=Connection(b'POST /v1/identities HTTP/1.0\r\nContent-Type: application/json\r\nContent-Length: '+str(len(encoded)).encode()+b'\r\n\r\n'+encoded)
            Handler(conn,('127.0.0.1',1),server)
            header,result=bytes(conn.output).split(b'\r\n\r\n',1)
            return int(header.split()[1]),json.loads(result)
        self.assertEqual(register({'name':'X','kind':'human'})[0],403)
        self.eligible();issued=self.p.create_invitation(self.a['id'])
        body={'name':'X','kind':'human','invite_code':issued['code']}
        self.assertEqual(register(body)[0],201)
        self.assertEqual(register(body)[0],403)
