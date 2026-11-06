import {el, money} from './dom.js';
import {employees, products, phases, milestones} from './labels.js';

export function eventEntries(room, batches) {
  return batches.flatMap(batch => batch.version > room.version ? [] : batch.events.map(event => ({...event, version:batch.version})));
}
export function currentRoundEntries(room, batches) {
  return eventEntries(room,batches).filter(event => event.round === room.state.round);
}
export function eventText(e, name) {
  const actions={start:'开始游戏',place_restaurant:'放置餐厅',pass:'暂缓放置餐厅',choose_reserve:'选择储备卡（金额按规则保密）',restructure:'提交公司结构（所有人提交后公开）',choose_order:'选择行动顺位',work:'提交经营计划',payday:'完成发薪决策',cleanup:'完成库存清理',choose_bonus:'选择里程碑奖励'};
  return {
    action_submitted:`${name(e.player)}：${actions[e.action_type] || e.action_type}`,
    round_started:`第 ${e.round} 轮开始。`,
    game_started:'所有人已入座，游戏开始。',
    player_joined:`${name(e.player)} 加入了游戏桌。`,
    structures_revealed:'所有公司结构已公开。',
    decision_automated:`${name(e.player)} 的${phases[e.phase] || e.phase}已自动完成：${{no_available_employees:'没有可安排的员工',only_position:'只剩一个顺位',no_firing_choice:'没有裁员选择',empty_inventory:'没有剩余库存',no_freezer:'没有可用冰柜',no_bonus_placement:'没有合法奖励位置'}[e.reason] || e.reason}。`,
    work_completed:`${name(e.player)} 完成经营：${workDetails(e.plan).join('；') || '本次没有安排经营操作'}。`,
    milestone:`${name(e.player)} 达成「${milestones[e.milestone] || e.milestone}」。`,
    house_served:`房屋 ${e.house} 在 ${name(e.player)} 用餐，收入 ${money(e.income)}。`,
    coffee_sold:`${name(e.player)} 售出咖啡，收入 ${money(e.income)}。`,
    salaries_paid:`${name(e.player)} 支付了 ${money(e.amount)} 工资。`,
    salaries_unpaid:`${name(e.player)} 有 ${money(e.amount)} 工资未能支付。`,
    marketing_resolved:'营销活动已结算，居民需求已更新。',
    bank_broken:`银行第 ${e.number} 次破产。`,
    game_finished:`本局结束，${name(e.winner)} 获胜。`,
    chain_bankrupt:`${name(e.player)} 的连锁破产退出。`,
    structure_overflow:`${name(e.player)} 的组织超出容量，只剩 CEO 工作。`,
    discount_bank_removed:`${name(e.player)} 的促销里程碑从银行移除 ${money(e.amount)}。`,
  }[e.type] || e.type;
}
function workDetails(plan) {
  if (!plan) return ['完成今日工作（旧记录未附明细）'];
  const pos = row => row.position ? ` (${row.position.join(', ')})` : '';
  return [
    ...(plan.hire || []).map(row=>`招聘${employees[row.kind] || row.kind}`),
    ...(plan.train || []).map(row=>`培训 ${row.employee || `新员工 #${row.hire_index}`} → ${(row.path || []).map(k=>employees[k] || k).join(' → ')}`),
    ...(plan.market || []).map(row=>`放置营销 #${row.campaign_id} · ${products[row.product] || row.product}${pos(row)}${row.rotate?'（旋转）':''}${row.side?` · ${row.side} / 起始行列 ${row.offset}`:''}`),
    ...(plan.produce || []).map(row=>`${row.employee} 生产／采购${row.product ? ` ${products[row.product] || row.product}`:''}${row.route?` · 路线 ${row.route.map(p=>`(${p.join(',')})`).join(' → ')}`:''}`),
    ...(plan.develop || []).map(row=>`开发房屋／花园${pos(row)}`),
    ...(plan.lobby || []).map(row=>`建设 ${row.piece}${pos(row)}`),
    ...(plan.restaurants || []).map(row=>`${row.restaurant_id?'搬迁':'开设'}餐厅${pos(row)}`),
  ];
}
export function roundLogPanel(room,batches) {
  const entries=currentRoundEntries(room,batches);
  const name=id=>room.members.find(m=>m.id===id)?.name || '系统';
  return el('section',{class:'round-log-panel card','aria-label':'本轮行动日志'},
    el('div',{class:'section-title'},el('h2',{},`本轮行动日志 · 第 ${room.state.round} 轮`),el('span',{class:'small muted'},`${entries.length} 条`)),
    el('p',{class:'small muted'},'全体玩家本轮已公开的行动；秘密储备与未公开公司结构不会显示。'),
    entries.length ? el('ol',{class:'round-action-list'},entries.map(e=>el('li',{},el('span',{},eventText(e,name)),el('small',{class:'muted'},`${phases[e.phase] || ''} · #${e.version}`)))) : el('p',{class:'muted'},'本轮还没有已公开的行动。')
  );
}
export function turnOrderPanel(room,viewer) {
  const s=room.state;
  const living=s.order.filter(id=>!s.players[id].eliminated);
  const choosing=s.phase==='order';
  const pending=['setup_restaurants','reserve','restructure'].includes(s.phase);
  const order=choosing?living.map((_,index)=>s.positions?.[String(index)] || null):living;
  return el('section',{class:'turn-order-panel card','aria-label':'本轮玩家顺序'},
    el('div',{class:'section-title'},el('h2',{},'本轮玩家顺序')),
    (pending || choosing) && el('p',{class:'small muted'},choosing?'正在选择本轮顺位，空位尚未确定。':'本轮尚未选序，以下显示现有顺序供参考。'),
    el('ol',{class:'turn-order-list'},order.map((id,index)=>el('li',{'data-player':id || '',class:s.actors?.includes(id)?'is-acting':''},
      el('strong',{},`${index+1}. ${id?(room.members.find(m=>m.id===id)?.name || id):'待选择'}${id===viewer?'（你）':''}`),
      id && el('small',{},s.finished?'已结束':s.actors?.includes(id)?'正在决策':'等待')
    )))
  );
}
