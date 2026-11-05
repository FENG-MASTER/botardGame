from copy import deepcopy
import tempfile
import unittest
from boardgame.core import GameError
from boardgame.platform import Platform
from boardgame.games.fcm.engine import FCM
from boardgame.games.fcm import board as geo
from boardgame.games.fcm.catalog import stock, CARDS
from boardgame.games.fcm.modules import AVAILABLE_MODULES
from boardgame.games.fcm.tiles import generated, rotated, TILES


class ExpansionTests(unittest.TestCase):
    def game(self, *modules):
        self.g = FCM()
        self.s = self.g.create(['a', 'b'], {'modules': list(modules), 'scenario': {'board': geo.generated(2, 11)}}, 11)
        self.s.update(phase='work', queue=['a','b'], order=['a','b'], reserves={'a':100,'b':100})
        for pid,pos in [('a',[3,0]),('b',[8,0])]:
            self.g.place_restaurant(self.s,pid,{'position':pos},setup=True)
        self.a,self.b=(self.s['players'][p] for p in ['a','b'])
        return self.s

    def add(self, pid, kind, active=True):
        eid=self.g.employee(self.s,pid,kind)
        if active:self.s['players'][pid]['active'].append(eid)
        return eid

    def test_configuration_rejects_invalid_and_unimplemented_modules(self):
        for config in [{'modules':'sushi'}, {'modules':['sushi','sushi']}, {'modules':['unknown']},
                       {'modules':['new_milestones','hard_choices']},
                       {'modules':['kimchi'],'introductory':True}, {'modules':['six_players']}]:
            with self.subTest(config=config),self.assertRaises(GameError):FCM().create(['a','b'],config,0)
        self.game('sushi','noodles')
        self.assertIn('sushi_cook',self.s['stock'])
        self.assertNotIn('kimchi_master',self.s['stock'])
        with self.assertRaises(GameError):self.g.employee(self.s,'a','kimchi_master')

    def test_base_component_data_and_tile_rotation(self):
        self.assertEqual(sum(stock(5).values()),222)
        self.assertFalse(CARDS['trainer']['salary'])
        self.assertFalse(CARDS['pricing_manager']['salary'])
        self.assertTrue(CARDS['pricing_manager']['entry'])
        self.assertNotIn('pricing_manager',CARDS['management_trainee']['upgrades'])
        for tile in TILES:
            self.assertEqual(rotated(tile['id'],4),rotated(tile['id'],0))
        for players in range(2,7):
            modules=['new_districts','six_players'] if players==6 else []
            a=generated(players,21,modules);b=generated(players,21,modules)
            self.assertEqual(a,b)
            self.assertEqual(len(a['tiles']),{2:9,3:12,4:16,5:20,6:24}[players])
            self.assertEqual(len({t['id'] for t in a['tiles']}),len(a['tiles']))
            geo.validate(a)
        self.assertEqual({h['id'] for h in generated(5,0)['houses']},{2,4,5,7,8,10,12,13,15,16,18})

    def test_six_player_setup_and_order_position_five(self):
        g=FCM();s=g.create(list('abcdef'),{'modules':['six_players','new_districts']},4)
        self.assertEqual((s['board']['width'],s['board']['height']),(30,20))
        s.update(phase='order',queue=list('abcdef'),positions={})
        g.apply(s,'a',{'type':'choose_order','position':5})
        self.assertEqual(s['positions']['5'],'a')

    def test_kimchi_sushi_noodle_preference_and_consumption(self):
        self.game('kimchi','sushi','noodles')
        house=self.s['board']['houses'][0];house.update(garden=True,demand=['burger','beer'])
        self.a['inventory'].update(sushi=2)
        self.b['inventory'].update(kimchi=1,noodles=2)
        events=self.g.dinner(self.s)
        self.assertEqual(self.b['cash'],60) # Kimchi+noodles outranks plain sushi, garden doubles all 3.
        self.assertEqual(self.a['inventory']['sushi'],2)
        self.assertEqual(self.b['inventory']['kimchi'],0)
        self.assertEqual(house['demand'],[])

    def test_noodle_cannot_partially_replace_demand(self):
        self.game('noodles')
        house=self.s['board']['houses'][0];house['demand']=['burger','pizza']
        self.a['inventory'].update(noodles=1,burger=1)
        self.g.dinner(self.s)
        self.assertEqual(house['demand'],['burger','pizza'])

    def test_reserve_price_changes_for_following_houses_in_same_dinner(self):
        self.game('reserve_prices')
        self.s.update(bank=10, reserves={'a':20, 'b':20})
        for house in self.s['board']['houses'][:2]:
            house['demand']=['burger']
        self.a['inventory']['burger']=2
        self.g.dinner(self.s)
        self.assertEqual(self.a['cash'],30)
        served=[event for event in self.s['log'] if event['type']=='house_served']
        self.assertEqual([event['income'] for event in served],[10,20])

    def test_fry_chefs_bonus_is_per_house_and_receives_cfo_bonus(self):
        self.game('fry_chefs');self.add('a','fry_chef');self.add('a','fry_chef');self.add('a','cfo')
        self.s['board']['houses'][0]['demand']=['burger']*2
        self.a['inventory']['burger']=2
        self.g.dinner(self.s)
        self.assertEqual(self.a['cash'],60) # (20 food + 20 fries) * 1.5

    def test_kimchi_cleanup_production_and_separate_freezer(self):
        self.game('kimchi');self.add('a','kimchi_master')
        self.g.cleanup(self.s,'a',{'keep':{}})
        self.assertEqual(self.a['inventory']['kimchi'],1)
        self.a['milestones'].append('first_discard');self.a['inventory']['burger']=1
        with self.assertRaises(GameError):self.g.cleanup(deepcopy(self.s),'a',{'keep':{'burger':1,'kimchi':1}})
        self.g.cleanup(self.s,'a',{'keep':{'kimchi':1}})
        self.assertEqual(self.a['inventory']['kimchi'],2)

    def test_ketchup_is_awarded_after_all_houses_and_tracks_multiple_owners(self):
        self.game('ketchup');h=self.s['board']['houses'][0]
        h.update(demand=['burger'],demand_sources=['b']);self.a['inventory']['burger']=1
        self.g.dinner(self.s)
        self.assertIn('ketchup',self.b['milestones'])
        self.assertNotIn('ketchup',self.a['milestones'])
        self.assertEqual(h['demand_sources'],[])

    def test_mass_marketing_repeats_effect_not_duration(self):
        self.game('mass_marketeers');self.add('a','mass_marketeer');self.add('b','mass_marketeer')
        h=self.s['board']['houses'][0]
        self.s['campaigns']=[dict(id='1',kind='radio',player='a',employee=None,product='burger',cells=[[1,3]],remaining=2,eternal=False)]
        self.s.setdefault('log', [])
        self.g.marketing(self.s)
        self.assertEqual(h['demand'],['burger']*3)
        self.assertEqual(self.s['campaigns'][0]['remaining'],1)

    def test_apartments_double_marketing_without_cap(self):
        self.game('new_districts');h=self.s['board']['houses'][0];h['apartment']=True
        self.s['campaigns']=[dict(id='1',kind='radio',player='a',employee=None,product='burger',cells=[[1,3]],remaining=None,eternal=True)]
        for _ in range(3):self.g.marketing(self.s)
        self.assertEqual(len(h['demand']),6)

    def test_gourmet_guide_only_markets_gardens(self):
        self.game('gourmet_critics');e=self.add('a','gourmet_food_critic')
        self.s['board']['houses'][0]['garden']=True
        self.g.apply(self.s,'a',{'type':'work','market':[{'employee':e,'campaign_id':'17','product':'pizza','duration':3}]})
        self.s.setdefault('log', [])
        self.g.marketing(self.s)
        self.assertEqual(self.s['board']['houses'][0]['demand'],['pizza'])
        self.assertEqual(self.s['board']['houses'][1]['demand'],[])
        self.assertEqual(self.s['campaigns'][0]['remaining'],2)

    def test_night_shift_doubles_free_employee_but_not_ceo(self):
        self.game('night_shift');self.add('a','night_shift_manager');e=self.add('a','kitchen_trainee')
        self.g.apply(self.s,'a',{'type':'work','produce':[{'employee':e,'product':'burger'},{'employee':e,'product':'pizza'}]})
        self.assertEqual(self.a['inventory']['burger'],1);self.assertEqual(self.a['inventory']['pizza'],1)
        self.game('night_shift');self.add('a','night_shift_manager')
        with self.assertRaises(GameError):self.g.apply(self.s,'a',{'type':'work','hire':[{'recruiter':'a:ceo','kind':'waitress'}]*2})

    def test_night_shift_two_campaigns_remain_busy_until_both_end(self):
        self.game('night_shift');self.add('a','night_shift_manager');e=self.add('a','marketing_trainee')
        # Force duration rather than the base eternal-billboard milestone.
        self.s['closed_milestones'].append('first_billboard')
        self.s['campaign_tiles']['11'].update(width=1,height=1)
        self.s['campaign_tiles']['13'].update(width=1,height=1)
        self.g.apply(self.s,'a',{'type':'work','market':[
            {'employee':e,'campaign_id':'11','product':'burger','duration':1,'position':[4,3]},
            {'employee':e,'campaign_id':'13','product':'pizza','duration':2,'position':[1,4]}]})
        self.s.setdefault('log', [])
        self.g.marketing(self.s)
        self.assertEqual(next(v for v in self.a['employees'] if v['id']==e)['busy'],'13')
        self.s.setdefault('log', [])
        self.g.marketing(self.s)
        self.assertIsNone(next(v for v in self.a['employees'] if v['id']==e)['busy'])

    def test_movie_star_uniqueness_and_business_order(self):
        self.game('movie_stars');self.add('a','b_movie_star')
        with self.assertRaises(GameError):self.add('a','c_movie_star')
        self.s.update(phase='restructure',pending={})
        ea=self.a['employees'][-1]['id']
        self.g.apply(self.s,'a',{'type':'restructure','structure':{ea:'a:ceo'}})
        self.assertEqual(self.s['phase'],'order');self.assertEqual(self.s['queue'][0],'a')

    def test_reserve_price_tie_breaks_and_fixed_reserve(self):
        self.game('reserve_prices');self.s.update(bank=1,reserves={'a':5,'b':20})
        self.g.pay(self.s,'a',2)
        self.assertEqual(self.s['bank'],399)
        self.assertEqual(self.s['base_price'],20)
        self.assertEqual(self.s['next_ceo_slots'],3)
        self.game('reserve_prices');self.s.update(phase='reserve',pending={})
        self.g.apply(self.s,'a',{'type':'choose_reserve','amount':5})
        self.assertIsNone(self.g.observe(self.s,'b')['reserves']['a'])
        with self.assertRaises(GameError):self.g.apply(self.s,'b',{'type':'choose_reserve','amount':100})

    def test_hard_choices_expire_only_at_defined_round_end(self):
        self.game('hard_choices');self.s['round']=2
        self.g.new_round(self.s)
        self.assertIn('first_train',self.s['closed_milestones'])
        self.assertNotIn('first_hire_three',self.s['closed_milestones'])
        self.g.new_round(self.s)
        self.assertIn('first_hire_three',self.s['closed_milestones'])

    def test_room_configuration_persists_for_humans_and_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            platform=Platform(tmp+'/db')
            a=platform.register('human','human');b=platform.register('agent','agent')
            room=platform.create_room(a['id'],'fcm',2,{'modules':['sushi','kimchi']},11)
            platform.join(b['id'],room['id'],room['join_code'])
            self.assertEqual(platform.get(b['id'],room['id'])['config']['modules'],['sushi','kimchi'])
            state=platform.mutate(a['id'],room['id'],1,'start',{'type':'start'},start=True)['state']
            self.assertEqual(state['modules'],['kimchi','sushi'])
            self.assertTrue(Platform(tmp+'/db').replay(room['id'])['valid'])

    def test_new_milestones_maximum_compatible_six_player_game_replays(self):
        self.replay_combination('hard_choices')

    def test_hard_choices_maximum_compatible_six_player_game_replays(self):
        self.replay_combination('new_milestones')

    def replay_combination(self, excluded):
        from examples.play_agents import choose
        with tempfile.TemporaryDirectory() as tmp:
            platform=Platform(tmp+'/db')
            ids=[platform.register(str(i), 'human' if i==0 else 'agent')['id'] for i in range(6)]
            room=platform.create_room(ids[0],'fcm',6,{'modules':sorted(AVAILABLE_MODULES - {excluded})},4)
            for pid in ids[1:]:platform.join(pid,room['id'],room['join_code'])
            observation=platform.get(ids[0],room['id'])
            observation=platform.mutate(ids[0],room['id'],observation['version'],'start',{'type':'start'},start=True)
            for i in range(1500):
                if observation['status']=='finished':break
                pid=observation['state']['actors'][0]
                current=platform.get(pid,room['id'])
                action=choose(pid,current,platform.actions(pid,room['id']))
                observation=platform.mutate(pid,room['id'],current['version'],str(i),action)
            self.assertEqual(observation['status'],'finished')
            self.assertTrue(platform.replay(room['id'])['valid'])
