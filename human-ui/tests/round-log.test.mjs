import test from 'node:test';
import assert from 'node:assert/strict';
import {installDOM} from './dom.mjs';
import {preview} from '../src/preview.js';
import {currentRoundEntries,roundLogPanel,turnOrderPanel,eventText} from '../src/round-log.js';

test('current-round log excludes previous, unknown and newer-observation events',()=>{
  const dom=installDOM();
  try {
    const room=structuredClone(preview.room);
    const batches=[
      {version:1,events:[{type:'work_completed',round:2,player:'preview-agent'}]},
      {version:2,events:[{type:'action_submitted',round:3,player:'preview-human',action_type:'restructure'},{type:'work_completed',round:3,player:'preview-agent',plan:{hire:[{kind:'burger_cook'}]}}]},
      {version:3,events:[{type:'work_completed',player:'preview-agent'}]},
      {version:room.version+1,events:[{type:'work_completed',round:3,player:'preview-agent'}]},
    ];
    assert.equal(currentRoundEntries(room,batches).length,2);
    const panel=roundLogPanel(room,batches);
    assert.equal(panel.querySelectorAll('li').length,2);
    assert.match(panel.textContent,/Atlas.*招聘汉堡小厨/);
    assert.match(panel.textContent,/所有人提交后公开/);
    room.state.round=4;
    assert.equal(currentRoundEntries(room,batches).length,0);
    assert.match(roundLogPanel(room,batches).textContent,/本轮还没有/);
  } finally {dom.window.close();}
});
test('turn order follows selected positions and marks active player without inventing unchosen slots',()=>{
  const dom=installDOM();
  try {
    const room=structuredClone(preview.room);
    room.state.phase='order';room.state.positions={'1':'preview-human'};room.state.actors=['preview-agent'];
    let panel=turnOrderPanel(room,'preview-human');
    assert.match(panel.querySelectorAll('li')[0].textContent,/待选择/);
    assert.match(panel.querySelectorAll('li')[1].textContent,/你/);
    room.state.phase='work';room.state.order=['preview-agent','preview-human'];
    panel=turnOrderPanel(room,'preview-human');
    assert.equal(panel.querySelector('li').dataset.player,'preview-agent');
    assert.match(panel.querySelector('li').textContent,/正在决策/);
  } finally {dom.window.close();}
});
