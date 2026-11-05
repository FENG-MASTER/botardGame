import test from 'node:test';
import assert from 'node:assert/strict';
import {installDOM} from './dom.mjs';
import {modulePicker,moduleProblem} from '../src/modules.js';
import {API} from '../src/api.js';
import {freshDraft,buildAction} from '../src/model.js';
const modules=[
  {id:'sushi',name:'寿司',available:true},
  {id:'kimchi',name:'泡菜',available:true},
  {id:'coffee',name:'咖啡',available:false},
  {id:'new_districts',name:'新城区',available:true},
  {id:'six_players',name:'六人游戏',available:true,requires:['new_districts']},
];
test('room picker supports zero, one and multiple modules, with unavailable choices disabled',()=>{
 const dom=installDOM();try {
  let selected=[];
  const render=()=>document.querySelector('#app').replaceChildren(modulePicker(modules,selected,{capacity:2,introductory:false,onChange:value=>{selected=value;render();}}));
  render();assert.match(document.body.textContent,/已选 0 个/);
  document.querySelectorAll('input')[0].click();assert.deepEqual(selected,['sushi']);
  document.querySelectorAll('input')[1].click();assert.deepEqual(selected,['sushi','kimchi']);assert.match(document.body.textContent,/已选 2 个/);
  assert.equal(document.querySelectorAll('input')[2].disabled,true);
  document.querySelector('button').click();assert.deepEqual(selected,[]);
 } finally {dom.window.close();}
});
test('room combination rules match server constraints',()=>{
 assert.equal(moduleProblem(modules,[],2,false),null);
 assert.equal(moduleProblem(modules,['sushi','kimchi'],2,false),null);
 assert.ok(moduleProblem(modules,['sushi'],2,true));
 assert.ok(moduleProblem(modules,['coffee'],2,false));
 assert.ok(moduleProblem(modules,[],6,false));
 assert.ok(moduleProblem(modules,['six_players'],6,false));
 assert.ok(moduleProblem(modules,['six_players','new_districts'],2,false));
 assert.equal(moduleProblem(modules,['six_players','new_districts'],6,false),null);
});
test('create request preserves selected modules and reserve-price draft uses a legal card',async()=>{
 let sent;
 const api=new API('test',async(url,options)=>{sent=JSON.parse(options.body);return Response.json({id:'r'});});
 await api.create({game:'fcm',capacity:2,config:{modules:['sushi','kimchi']}});
 assert.deepEqual(sent.config.modules,['sushi','kimchi']);
 const draft=freshDraft({modules:['reserve_prices'],round:1,phase:'reserve'});
 assert.deepEqual(buildAction('reserve',draft),{type:'choose_reserve',amount:10});
});
