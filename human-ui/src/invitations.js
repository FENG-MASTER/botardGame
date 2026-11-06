import { el, button } from './dom.js';

export function invitationPanel(api, copy) {
  const panel = el('section', { class: 'invitation-panel' });
  let pending = false;
  let issued;
  let failure = '';
  async function load() {
    try {
      const data = await api.invitations();
      panel.replaceChildren(
        el('h3', {}, '邀请新玩家'),
        el('p', {}, `已登录 ${data.login_days} / ${data.required_days} 天（北京时间的不同自然日）`),
        el('p', {class:'small muted'}, '邀请码只能注册一个账号，7 天有效。注册邀请码与房间邀请码不同。'),
        button('生成邀请码', async () => {
          if (pending) return;
          pending = true;
          generate.disabled = true;
          try { issued = await api.createInvitation(); failure = ''; }
          catch (e) { failure = e.message; }
          finally { pending = false; await load(); }
        }, 'secondary'),
        failure && el('p', {role:'alert'}, failure),
        issued && el('div', {}, el('p', {}, '请立即复制保存，完整邀请码仅在生成时显示。'),
          el('input', {readOnly:true, value:issued.code, 'aria-label':'新邀请码'}),
          button('复制邀请码', () => copy(issued.code), 'primary')),
        el('h3', {}, '邀请记录'),
        ...(data.invitations.length ? data.invitations.map(invite => el('div', {class:'invitation-history'},
          el('p', {}, `${{available:'未使用',used:'已使用',revoked:'已撤销',expired:'已过期'}[invite.status]} · 创建于 ${new Date(invite.created*1000).toLocaleString('zh-CN')}`),
          el('small', {}, invite.invitee_name ? `受邀玩家：${invite.invitee_name} · 注册于 ${new Date(invite.used_at*1000).toLocaleString('zh-CN')}` : `到期：${new Date(invite.expires*1000).toLocaleString('zh-CN')}`),
          invite.status === 'available' && button('撤销', async () => {
            if (pending) return;
            pending = true;
            try { await api.revokeInvitation(invite.id); if (issued?.id === invite.id) issued = null; failure = ''; }
            catch(e) { failure = e.message; }
            finally { pending = false; await load(); }
          }, 'text small')
        )) : [el('p', {class:'muted'}, '还没有邀请记录')])
      );
      const generate = panel.querySelector('button');
      generate.disabled = !data.eligible || pending;
    } catch (e) { panel.replaceChildren(el('p', {role:'alert'}, e.message), button('重试', load)); }
  }
  load();
  return panel;
}
