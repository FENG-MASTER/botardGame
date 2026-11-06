"""Base-game employee abilities. Physical component counts are scenario data."""

PRODUCTS = ["burger", "pizza", "beer", "lemonade", "soda"]
CARDS = {}


def card(
    name,
    *,
    salary=True,
    entry=False,
    slots=0,
    train=0,
    hire=0,
    discount=False,
    price=0,
    product=None,
    quantity=0,
    marketing=0,
    distance=None,
    unique=False,
    upgrades=(),
):
    CARDS[name] = dict(
        salary=salary,
        entry=entry,
        slots=slots,
        train=train,
        hire=hire,
        discount=discount,
        price=price,
        product=product,
        quantity=quantity,
        marketing=marketing,
        distance=distance,
        unique=unique,
        upgrades=list(upgrades),
    )


card("ceo", salary=False, slots=3, hire=1)
card("waitress", salary=False, entry=True)
card(
    "management_trainee",
    salary=False,
    entry=True,
    slots=2,
    upgrades=["junior_vice_president", "new_business_developer", "pricing_manager"],
)
card(
    "junior_vice_president",
    slots=3,
    upgrades=["vice_president", "local_manager", "luxuries_manager"],
)
card("vice_president", slots=4, upgrades=["senior_vice_president", "discount_manager"])
card(
    "senior_vice_president",
    slots=5,
    upgrades=["executive_vice_president", "regional_manager"],
)
card("executive_vice_president", slots=10, unique=True, upgrades=["cfo"])
card("new_business_developer")
card("local_manager", distance=3)
card("regional_manager", unique=True)
card("pricing_manager", price=-1)
card("luxuries_manager", price=10, unique=True)
card("discount_manager", price=-3)
card("cfo", unique=True)
card(
    "recruiting_girl", salary=False, entry=True, hire=1, upgrades=["recruiting_manager"]
)
card("recruiting_manager", hire=2, discount=True, upgrades=["hr_director"])
card("hr_director", hire=4, discount=True, unique=True)
card("trainer", entry=True, train=1, upgrades=["coach"])
card("coach", train=2, upgrades=["guru"])
card("guru", train=3, unique=True)
card("errand_boy", entry=True, salary=False, quantity=1, upgrades=["cart_operator"])
card("cart_operator", quantity=2, distance=2, upgrades=["truck_driver"])
card("truck_driver", quantity=3, distance=3, upgrades=["zeppelin_pilot"])
card("zeppelin_pilot", quantity=2, distance=4, unique=True)
card(
    "marketing_trainee",
    entry=True,
    salary=False,
    marketing=1,
    distance=2,
    upgrades=["campaign_manager"],
)
card("campaign_manager", marketing=2, distance=3, upgrades=["brand_manager"])
card("brand_manager", marketing=3, upgrades=["brand_director"])
card("brand_director", marketing=4, unique=True)
card(
    "kitchen_trainee",
    entry=True,
    salary=False,
    quantity=1,
    upgrades=["burger_cook", "pizza_cook"],
)
card("burger_cook", product="burger", quantity=3, upgrades=["burger_chef"])
card("pizza_cook", product="pizza", quantity=3, upgrades=["pizza_chef"])
card("burger_chef", product="burger", quantity=8)
card("pizza_chef", product="pizza", quantity=8)

MILESTONES = [
    "first_billboard",
    "first_train",
    "first_hire_three",
    "first_burger_marketed",
    "first_pizza_marketed",
    "first_drink_marketed",
    "first_errand_boy",
    "first_twenty",
    "first_burger_produced",
    "first_pizza_produced",
    "first_waitress",
    "first_discard",
    "first_lower_price",
    "first_cart_operator",
    "first_airplane",
    "first_radio",
    "first_hundred",
    "first_pay_twenty",
]


# Transcribed base card faces (TTS sheet 1) and 2019 replacement cards.
CARDS['management_trainee']['upgrades'] = ['junior_vice_president', 'luxuries_manager', 'new_business_developer']
CARDS['junior_vice_president']['upgrades'] = ['coach', 'vice_president', 'recruiting_manager', 'discount_manager', 'local_manager']
CARDS['vice_president']['upgrades'] = ['senior_vice_president', 'guru', 'regional_manager']
CARDS['senior_vice_president']['upgrades'] = ['executive_vice_president', 'cfo', 'hr_director']
CARDS['executive_vice_president']['upgrades'] = []
CARDS['pricing_manager'].update(entry=True, salary=False)
CARDS['trainer']['salary'] = False
for _kind in ('burger_chef', 'pizza_chef'):
    CARDS[_kind]['unique'] = True
BASE_KINDS = set(CARDS)
BASE_PRODUCTS = list(PRODUCTS)

card('sushi_cook', product='sushi', quantity=2, upgrades=['sushi_chef'])
card('sushi_chef', product='sushi', quantity=5, unique=True)
card('noodle_cook', product='noodles', quantity=6, upgrades=['noodle_chef'])
card('noodle_chef', product='noodles', quantity=16, unique=True)
card('kimchi_master', entry=True, unique=True)
card('fry_chef')
card('barista_trainee', entry=True, salary=False, product='coffee', quantity=1, upgrades=['barista'])
card('barista', product='coffee', quantity=2, upgrades=['lead_barista'])
card('lead_barista', product='coffee', quantity=5, unique=True)
card('lobbyist', entry=True, distance=2)
card('night_shift_manager', entry=True, unique=True)
card('mass_marketeer')
card('rural_marketeer', marketing=1)
card('gourmet_food_critic', marketing=2)
for _rank in ('b', 'c', 'd'):
    card(f'{_rank}_movie_star', unique=True)
MODULE_KINDS = {
    'sushi':['sushi_cook','sushi_chef'], 'noodles':['noodle_cook','noodle_chef'],
    'kimchi':['kimchi_master'], 'fry_chefs':['fry_chef'],
    'coffee':['barista_trainee','barista','lead_barista'], 'lobbyists':['lobbyist'],
    'night_shift':['night_shift_manager'], 'mass_marketeers':['mass_marketeer'],
    'rural_marketeers':['rural_marketeer'], 'gourmet_critics':['gourmet_food_critic'],
    'movie_stars':['b_movie_star','c_movie_star','d_movie_star'],
}
for _module, _kinds in MODULE_KINDS.items():
    for _kind in _kinds: CARDS[_kind]['module'] = _module
CARDS['kitchen_trainee']['upgrades'] += ['sushi_cook','noodle_cook']
for _kind in ('burger_cook','pizza_cook','sushi_cook','noodle_cook'):
    CARDS[_kind]['upgrades'].append('fry_chef')
CARDS['marketing_trainee']['upgrades'] += ['mass_marketeer','rural_marketeer','gourmet_food_critic']
CARDS['waitress']['upgrades'] = ['b_movie_star','c_movie_star','d_movie_star']
PRODUCTS += ['sushi','noodles','kimchi','coffee']
for _kind, _c in CARDS.items():
    _c['color'] = ('black' if _c['slots'] or _kind in ('ceo','night_shift_manager') else
                  'green' if _c['quantity'] or _kind in ('kimchi_master','fry_chef') else
                  'blue' if _c['marketing'] or _kind=='mass_marketeer' else
                  'gray' if _c['hire'] or _c['train'] else
                  'red' if _kind in ('local_manager','regional_manager') else
                  'orange' if _c['price'] else 'purple')
    _c['manager'] = bool(_c['slots']) or _kind == 'night_shift_manager'


def enabled_cards(modules=()):
    return {k:v for k,v in CARDS.items() if v.get('module') is None or v['module'] in modules}


def stock(players, modules=()):
    limited = 1 if players <= 3 else players - 2
    twelve = {'waitress','junior_vice_president','pricing_manager','recruiting_girl',
              'trainer','errand_boy','marketing_trainee','kitchen_trainee','barista_trainee'}
    result = {k: (1 if k.endswith('_movie_star') else limited if c['unique'] else
                  18 if k=='management_trainee' else 12 if k in twelve else
                  9 if k=='barista' else 6)
              for k,c in enabled_cards(modules).items() if k!='ceo'}
    if set(modules) & {'coffee','kimchi','sushi','noodles'}:
        result['luxuries_manager'] += 1
    return result

_BASE_CAMPAIGNS = {str(i): dict(kind=('radio' if i<=3 else 'airplane' if i<=6 else 'mailbox' if i<=10 else 'billboard'), width=w, height=h)
    for i,(w,h) in enumerate([(1,1),(1,1),(1,1),(1,2),(3,2),(5,2),(2,2),(2,2),(1,1),(1,1),(3,2),(2,2),(3,1),(2,1),(1,1),(1,1)],1)}


def campaigns(players, modules=()):
    removed = {2:{12,15,16},3:{15,16},4:{16}}.get(players,set())
    result = {k:dict(v) for k,v in _BASE_CAMPAIGNS.items() if int(k) not in removed}
    if 'gourmet_critics' in modules:
        result.update({str(i):dict(kind='guide',width=1,height=1) for i in range(17,21)})
    if 'rural_marketeers' in modules:
        result.update({str(i):dict(kind='giant_billboard',width=1,height=1) for i in range(21,25)})
    return result


# Display metadata only; stable action IDs remain English.
from .employee_names import EMPLOYEE_NAMES_ZH

for _kind, _card in CARDS.items():
    _card["name_zh"] = EMPLOYEE_NAMES_ZH[_kind]
