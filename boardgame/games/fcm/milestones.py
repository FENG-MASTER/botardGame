"""2019 replacement milestone identifiers and availability."""
NEW = ['new_first_'+name for name in (
    'marketeer_used','marketing_trainee_used','campaign_manager_used','brand_manager_used',
    'brand_director_used','burger_sold','pizza_sold','lemonade_sold','beer_sold','soda_sold',
    'recruiting_girl_used','trainer_used','discount_manager_used','house_built',
    'restaurant','waitress_used','cart_operator_used')]
MODULE = {'ketchup':'ketchup','first_coffee_sold':'coffee',
          'first_lobbyist_used':'lobbyists','first_rural_marketeer_used':'rural_marketeers'}


def available(modules,base):
    return (list(NEW) if 'new_milestones' in modules else list(base))+[m for m,mod in MODULE.items() if mod in modules]


def freezer(p):
    return 10 if any(m in p['milestones'] for m in ('first_discard','new_first_soda_sold')) else 0


def stacking(p):
    return any(m in p['milestones'] for m in ('first_pay_twenty','new_first_house_built'))


def ceo_slots(s,p):
    return 4 if 'new_first_burger_sold' in p['milestones'] else s['ceo_slots']
