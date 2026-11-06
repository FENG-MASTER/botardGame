import test from 'node:test';
import assert from 'node:assert/strict';
import {installDOM, until} from './dom.mjs';
import {invitationPanel} from '../src/invitations.js';

test('invitation UI shows eligibility, one-time code and safe audit records', async () => {
  const dom=installDOM();
  try {
    let eligible=false, generated=0, revoked=0;
    const data={login_days:2,required_days:3,eligible:false,invitations:[]};
    const api={
      invitations:async()=>({...data,eligible,login_days:eligible?3:2}),
      createInvitation:async()=>{
        generated++; data.invitations=[{id:'one',status:'available',created:1,expires:600}];
        return {id:'one',code:'PRIVATE-INVITE'};
      },
      revokeInvitation:async()=>{revoked++;data.invitations[0].status='revoked';},
    };
    let copied;
    const first=invitationPanel(api,v=>{copied=v;}); document.body.append(first);
    await until(()=>first.querySelector('button'));
    assert.equal(first.querySelector('button').disabled,true);
    eligible=true;
    const panel=invitationPanel(api,v=>{copied=v;});document.body.append(panel);
    await until(()=>panel.querySelector('button'));
    panel.querySelector('button').click();
    await until(()=>panel.querySelector('input'));
    assert.equal(generated,1);
    assert.equal(panel.querySelector('input').value,'PRIVATE-INVITE');
    [...panel.querySelectorAll('button')].find(b=>b.textContent==='复制邀请码').click();
    assert.equal(copied,'PRIVATE-INVITE');
    [...panel.querySelectorAll('button')].find(b=>b.textContent==='撤销').click();
    await until(()=>!panel.querySelector('input'));
    assert.equal(revoked,1);assert.match(panel.textContent,/已撤销/);
    data.invitations=[{id:'used',status:'used',created:1,used_at:2,invitee_name:'<img src=x onerror=alert(1)>',expires:600}];
    const audit=invitationPanel(api,()=>{});document.body.append(audit);
    await until(()=>audit.textContent.includes('受邀玩家'));
    assert.equal(audit.querySelector('img'),null);
  } finally { dom.window.close(); }
});
