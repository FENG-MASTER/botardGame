import json
import unittest
from copy import deepcopy
from boardgame.core import GameError
from boardgame.games.fcm.engine import FCM
from boardgame.games.fcm import expansion_map as em, board as geo, coffee, milestones as ms
import test_fcm_modules as helpers


class RemainingExpansionTests(unittest.TestCase):
    game = helpers.ExpansionTests.game
    add = helpers.ExpansionTests.add

    def test_road_construction_barriers_and_cleanup(self):
        self.game('lobbyists');eid=self.add('a','lobbyist')
        before=geo.distance(self.s['board'],[[1,4]],[[3,4]])
        self.g.work(self.s,'a',dict(type='work',lobby=[dict(employee=eid,piece='road_short',position=[3,4])]))
        self.assertEqual(self.s['board']['cells'][4][3],'construction')
        self.assertEqual(self.s['roadworks'],[[2,4]])
        self.assertFalse(geo.road(self.s['board'],[3,4]))
        self.assertEqual(geo.distance(self.s['board'],[[1,4]],[[3,4]],self.s['roadworks']),before+1)
        self.g.new_round(self.s)
        self.assertTrue(geo.road(self.s['board'],[3,4]))
        self.assertEqual(self.s['lobby_supply']['road_short'],3)
        self.assertEqual(self.s['roadworks'],[])

    def test_park_garden_and_apartment_multipliers(self):
        self.game('lobbyists')
        h=self.s['board']['houses'][0];self.s['board']['cells'][0][2]='park'
        self.assertEqual(em.multiplier(self.s,h),2)
        h['garden']=True;self.assertEqual(em.multiplier(self.s,h),3)
        self.s['board']['cells'][1][2]='park';self.assertEqual(em.multiplier(self.s,h),3)
        h['garden']=False;h['apartment']=True;self.assertEqual(em.multiplier(self.s,h),2)

    def test_city_addition_shifts_all_coordinates_and_preserves_void(self):
        s=FCM().create(['a','b'],{'modules':['lobbyists','new_districts','coffee']},4)
        old=deepcopy(s['board']['houses'][0]['cells']);tile=s['board']['available_tiles'][0]
        s['players']['a']['coffee_shops']=[dict(id='a:c1',cells=[[1,1]])]
        s['offramps']=[dict(tile=[0,0],side='top',cells=em.edge_cells(0,0,'top'))]
        em.add_city(s,dict(tile_id=tile,tile=[-1,0],rotation=1))
        self.assertEqual(s['board']['width'],20)
        self.assertEqual(s['board']['houses'][0]['cells'],[[x+5,y] for x,y in old])
        self.assertEqual(s['players']['a']['coffee_shops'][0]['cells'],[[6,1]])
        self.assertEqual(s['offramps'][0]['tile'],[1,0])
        self.assertEqual(s['board']['cells'][8][0],'void')
        self.assertNotIn(tile,s['board']['available_tiles'])
        with self.assertRaises(GameError):em.add_city(s,dict(tile_id=s['board']['available_tiles'][0],tile=[1,-1]))

    def test_rural_campaign_demand_and_complete_meal_last(self):
        self.game('rural_marketeers','noodles','kimchi','fry_chefs')
        e=self.add('a','rural_marketeer');self.add('b','fry_chef')
        self.g.work(self.s,'a',dict(type='work',market=[dict(employee=e,campaign_id='21',product='pizza',duration=1,rural_side='top',offramp=dict(tile=[0,0],side='left'))]))
        self.g.marketing(self.s);self.g.marketing(self.s)
        self.assertEqual(self.s['rural']['demand'],['pizza']*4)
        self.assertTrue(self.s['campaigns'][0]['eternal'])
        self.b['inventory'].update(noodles=4,kimchi=1)
        self.g.dinner(self.s)
        self.assertEqual(self.b['cash'],60)
        self.assertEqual(self.s['rural']['demand'],[])
        self.assertEqual([e for e in self.s['log'] if e['type']=='house_served'][-1]['house'],'rural')

    def test_offramp_requires_road_and_blocks_airplane(self):
        self.game('rural_marketeers')
        self.s['campaigns']=[dict(kind='airplane',side='left',offset=1,span=3)]
        with self.assertRaises(GameError):em.add_offramp(self.s,dict(tile=[0,0],side='left'))
        self.s['campaigns']=[]
        em.add_offramp(self.s,dict(tile=[0,0],side='left'))
        with self.assertRaises(GameError):em.add_offramp(self.s,dict(tile=[0,0],side='left'))

    def test_training_coffee_shop_occupancy_and_range_sources(self):
        self.game('coffee');trainer=self.add('a','coach');target=self.add('a','barista_trainee',False)
        self.g.work(self.s,'a',dict(type='work',train=[dict(trainer=trainer,employee=target,path=['barista','lead_barista'],coffee_shops=[dict(position=[1,3]),dict(position=[6,3])])]))
        self.assertEqual(len(self.a['coffee_shops']),2)
        self.assertIn((6,3),geo.entrances(self.s,'a'))
        self.assertNotIn((6,3),geo.entrances(self.s,'a',coffee=False))
        with self.assertRaises(GameError):em.shop(self.s,'b',dict(position=[3,3]))
        with self.assertRaises(GameError):geo.empty(self.s,[[1,3]])
        self.a['inventory']['coffee']=10;self.a['milestones'].append('first_discard')
        with self.assertRaises(GameError):self.g.cleanup(self.s,'a',dict(keep={'coffee':1}))

    def straight_coffee(self):
        self.game('coffee')
        b=self.s['board'];b['cells']=[['empty']*15 for _ in range(15)]
        b['cells'][2]=['road']*15
        h=dict(id=1,order=1,cells=[[0,0],[1,0],[0,1],[1,1]],garden=False,demand=['burger'])
        b['houses']=[h]
        self.a['restaurants']=[dict(id='a:r1',cells=[[12,0],[13,0],[12,1],[13,1]],entrance=[12,1],open=True)]
        self.b['restaurants']=[dict(id='b:r1',cells=[[7,0],[8,0],[7,1],[8,1]],entrance=[7,1],open=True)]
        self.b['coffee_shops']=[dict(id='b:c1',cells=[[4,1]])]
        self.a['inventory'].update(burger=1,coffee=3);self.b['inventory']['coffee']=3
        return h

    def test_coffee_route_multiple_stops_excludes_destination_and_bonus(self):
        h=self.straight_coffee()
        self.assertEqual({v['id'] for v in coffee.stops(self.g,self.s,h,'a')},{'b:r1','b:c1'})
        self.g.dinner(self.s)
        self.assertEqual((self.a['cash'],self.b['cash']),(10,20))
        self.assertEqual(self.a['inventory']['coffee'],3)
        self.assertEqual(self.s['coffee_bonus'],['b'])
        self.g.cleanup_bonuses(self.s)
        self.assertEqual(self.s['phase'],'bonus')
        choice=self.g.bonus_options(self.s)[0]
        self.g.apply(self.s,'b',dict(type='choose_bonus',choice=choice))
        self.assertEqual(self.s['phase'],'order')
        self.assertEqual(len(self.b['coffee_shops']),2)

    def test_coffee_equal_shortest_branches_skip_ambiguous_stops(self):
        h=self.straight_coffee();b=self.s['board'];b['cells']=[['empty']*15 for _ in range(15)]
        for x in range(2,13):b['cells'][2][x]=b['cells'][12][x]='road'
        for y in range(2,13):b['cells'][y][2]=b['cells'][y][12]='road'
        h['cells']=[[7,1]]
        self.a['restaurants']=[dict(id='a:r1',cells=[[7,13]],entrance=[7,13],open=True)]
        self.b['restaurants']=[];self.b['coffee_shops']=[dict(id='b:left',cells=[[1,7]]),dict(id='b:right',cells=[[13,7]]),dict(id='b:common',cells=[[7,1]])]
        self.assertEqual([v['id'] for v in coffee.stops(self.g,self.s,h,'a')],['b:common'])
        self.b['coffee_shops'].pop(1)
        self.assertEqual({v['id'] for v in coffee.stops(self.g,self.s,h,'a')},{'b:left','b:common'})

    def test_replacement_milestones_free_cards_and_expiry(self):
        self.game('new_milestones');trainer=self.add('a','trainer');target=self.add('a','kitchen_trainee',False);recruiter=self.add('a','recruiting_girl')
        self.g.work(self.s,'a',dict(type='work',hire=[dict(recruiter=recruiter,kind='waitress')],train=[dict(trainer=trainer,employee=target,path=['burger_cook'])]))
        self.assertNotIn('first_train',self.a['milestones'])
        self.assertIn('new_first_trainer_used',self.a['milestones'])
        vp=next(e for e in self.a['employees'] if e['kind']=='executive_vice_president')
        self.assertFalse(self.g.salary_required(self.a,vp))
        self.assertEqual(sum(e['kind']=='trainer' for e in self.a['employees']),2)
        self.s['round']=2;self.g.new_round(self.s)
        self.assertIn('new_first_marketeer_used',self.s['closed_milestones'])

    def test_campaign_manager_two_campaigns_and_marketing_cash(self):
        self.game('new_milestones');e=self.add('a','campaign_manager')
        self.g.work(self.s,'a',dict(type='work',market=[dict(employee=e,campaign_id='9',product='burger',duration=2,position=[1,3],second_campaign=dict(campaign_id='10',position=[6,3]))]))
        self.assertEqual(len(self.s['campaigns']),2)
        self.assertIn('new_first_campaign_manager_used',self.a['milestones'])
        self.g.marketing(self.s)
        added=sum(h['demand'].count('burger') for h in self.s['board']['houses'])
        self.assertEqual(self.a['cash'],added*5)
        self.assertTrue(next(v for v in self.a['employees'] if v['id']==e)['busy'])

    def test_brand_manager_two_products_and_director_eternal(self):
        self.game('new_milestones');brand=self.add('a','brand_manager');director=self.add('b','brand_director')
        self.g.work(self.s,'a',dict(type='work',market=[dict(employee=brand,campaign_id='4',product='pizza',second_product='beer',duration=2,side='left',offset=0)]))
        self.g.work(self.s,'b',dict(type='work',market=[dict(employee=director,campaign_id='1',product='soda',duration=2,position=[1,3])]))
        self.g.marketing(self.s)
        self.assertEqual(self.s['board']['houses'][0]['demand'][:2],['soda','pizza'])
        self.assertEqual(self.s['board']['houses'][0]['demand'][2],'beer')
        self.assertTrue(next(c for c in self.s['campaigns'] if c['id']=='1')['eternal'])

    def test_pizza_radio_interrupt_survives_serialization_without_double_income(self):
        self.game('new_milestones');self.s['board']['houses'][0]['demand']=['pizza'];self.a['inventory']['pizza']=1
        self.g.dinner(self.s)
        self.assertEqual(self.s['phase'],'bonus');self.assertEqual(self.a['cash'],10)
        options=self.g.bonus_options(self.s)
        self.s=json.loads(json.dumps(self.s,sort_keys=True));self.a=self.s['players']['a']
        self.g.apply(self.s,'a',dict(type='choose_bonus',choice=options[0]))
        self.assertEqual(self.a['cash'],10)
        c=self.s['campaigns'][0];self.assertEqual(c['employee'],None)
        self.assertEqual(c['product'],'pizza');self.assertFalse(c['eternal'])
        self.assertNotIn('new_first_brand_director_used',self.a['milestones'])

    def test_food_wages_discount_and_trainer_waiver(self):
        self.game('new_milestones');self.add('a','coach');self.add('a','burger_cook')
        self.a['milestones']+=['new_first_beer_sold','new_first_waitress_used','new_first_trainer_used']
        self.a['inventory']['kimchi']=1;self.a['cash']=1
        with self.assertRaises(GameError):self.g.payday(deepcopy(self.s),'a',dict(fire=[]))
        self.g.payday(self.s,'a',dict(fire=[],food={'kimchi':1}))
        self.assertEqual(self.a['cash'],0);self.assertEqual(self.a['inventory']['kimchi'],0)
        self.assertEqual(len(self.a['employees']),3)
        self.assertEqual(next(e for e in self.s['log'] if e['type']=='salaries_unpaid')['amount'],2)

    def test_sold_milestones_ceo_freezer_and_active_training(self):
        self.game('new_milestones');h=self.s['board']['houses'][0];h['demand']=['burger','lemonade','soda']
        self.a['inventory'].update(burger=1,lemonade=1,soda=1);self.g.dinner(self.s)
        self.assertEqual(ms.ceo_slots(self.s,self.a),4);self.assertEqual(ms.freezer(self.a),10)
        trainer=self.add('a','trainer');cook=self.add('a','burger_cook')
        self.g.work(self.s,'a',dict(type='work',train=[dict(trainer=trainer,employee=cook,path=['burger_chef'])],produce=[dict(employee=cook)]))
        self.assertEqual(self.a['inventory']['burger'],8)

    def test_cart_double_sources_and_first_actual_use(self):
        self.game('new_milestones');e=self.add('a','cart_operator')
        self.g.produce(self.s,'a',next(v for v in self.a['employees'] if v['id']==e),__import__('boardgame.games.fcm.catalog',fromlist=['CARDS']).CARDS['cart_operator'],dict(route=[[2,0],[2,1],[2,2],[2,3]]))
        self.assertEqual(sum(self.a['inventory'].values()),4)
        self.assertIn('new_first_cart_operator_used',self.a['milestones'])

    def test_marketing_trainee_gifts_and_bonus_mailbox(self):
        self.game('new_milestones');e=self.add('a','marketing_trainee');manager=self.add('a','local_manager')
        self.s['board']['cells'][3][8]='empty'
        self.g.work(self.s,'a',dict(type='work',market=[dict(employee=e,campaign_id='14',product='burger',duration=1,position=[0,3])],restaurants=[dict(employee=manager,position=[8,3],entrance=0,mailbox=dict(campaign_id='9',product='beer',position=[6,3]))]))
        self.assertEqual({v['kind'] for v in self.a['employees']} & {'kitchen_trainee','errand_boy'},{'kitchen_trainee','errand_boy'})
        c=next(v for v in self.s['campaigns'] if v['id']=='9')
        self.assertTrue(c['eternal']);self.assertIsNone(c['employee'])
        self.assertFalse(self.a['restaurants'][-1]['open'])

    def test_discount_bank_removal_and_house_stacking(self):
        self.game('new_milestones');discount=self.add('a','discount_manager');developer=self.add('a','new_business_developer')
        self.s['board']['cells'][3][3]='empty'
        self.g.work(self.s,'a',dict(type='work',develop=[dict(employee=developer,position=[3,3],new_house_id=1)]))
        self.assertTrue(ms.stacking(self.a))
        self.assertIn('new_first_discount_manager_used',self.a['milestones'])
        self.s['bank']=500
        self.s['pending']={pid:dict(structure={discount:'a:ceo'} if pid=='a' else {},overflow=False) for pid in ['a','b']}
        self.g.reveal(self.s)
        self.assertEqual(self.s['bank'],400);self.assertEqual(self.a['cash'],0)

    def test_recruiter_box_copy_and_permanent_salary_exemption(self):
        self.game('new_milestones');self.s['stock']['executive_vice_president']=0;e=self.add('a','recruiting_girl')
        self.g.work(self.s,'a',dict(type='work',hire=[dict(recruiter=e,kind='waitress')]))
        vp=next(v for v in self.a['employees'] if v['kind']=='executive_vice_president')
        self.assertTrue(vp['box_copy']);self.assertFalse(self.g.salary_required(self.a,vp))
        self.g.payday(self.s,'a',dict(fire=[vp['id']]))
        self.assertEqual(self.s['stock']['executive_vice_president'],0)

    def test_airplane_stays_anchored_after_city_growth_and_blocks_lobbyist(self):
        g=FCM();s=g.create(['a','b'],{'modules':['lobbyists']},7)
        s['campaigns']=[dict(id='4',kind='airplane',side='top',offset=5,span=1,edge_line=0,cells=[])]
        tile=s['board']['available_tiles'][0]
        em.add_city(s,dict(tile_id=tile,tile=[0,-1]))
        plane=s['campaigns'][0];self.assertEqual(plane['edge_line'],5)
        self.assertFalse(em.edge_clear(s,1,1,'top'))
        with self.assertRaises(GameError):em.add_city(s,dict(tile_id=s['board']['available_tiles'][0],tile=[1,0]))

    def test_city_translation_replay_not_affected_by_shared_entrance_reference(self):
        self.game('lobbyists');self.s['board']['available_tiles']=['district-142d26']
        raw=deepcopy(self.s);serialized=json.loads(json.dumps(self.s))
        em.add_city(raw,dict(tile_id='district-142d26',tile=[-1,0]))
        em.add_city(serialized,dict(tile_id='district-142d26',tile=[-1,0]))
        self.assertEqual(raw,serialized)

    def test_lobbyist_bonus_is_required_atomic_plan_can_use_new_tile(self):
        self.game('lobbyists');eid=self.add('a','lobbyist');self.s['board']['available_tiles']=['district-142d26']
        plan=dict(type='work',lobby=[dict(employee=eid,piece='road_short',position=[3,4])])
        with self.assertRaises(GameError):self.g.work(deepcopy(self.s),'a',plan)
        plan['lobby'][0]['city']=dict(tile_id='district-142d26',tile=[3,0],rotation=0)
        self.g.work(self.s,'a',plan)
        self.assertEqual(self.s['board']['width'],20)
        self.assertIn('first_lobbyist_used',self.a['milestones'])
