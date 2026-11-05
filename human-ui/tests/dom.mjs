import {JSDOM} from 'jsdom';
export function installDOM(url='http://ui.test/#preview'){
  const dom=new JSDOM('<!doctype html><html><body><div id="app"></div><div id="toast"></div></body></html>',{url,pretendToBeVisual:true});
  for(const key of ['window','document','Node','Element','HTMLElement','location','sessionStorage','localStorage','Event','MouseEvent'])globalThis[key]=key==='window'?dom.window:dom.window[key];
  dom.window.HTMLElement.prototype.scrollIntoView=function(){};
  dom.window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  dom.window.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new dom.window.Event('close'));};
  Object.defineProperty(globalThis,'navigator',{configurable:true,value:dom.window.navigator});
  return dom;
}
export const settle=()=>new Promise(resolve=>setImmediate(resolve));
export async function until(condition,label='condition',rounds=400){for(let i=0;i<rounds;i++){if(await condition())return;await new Promise(r=>setTimeout(r,5));}throw Error(`Timed out: ${label}`);}
export function clickText(text){const node=[...document.querySelectorAll('button')].find(n=>n.textContent.trim()===text);if(!node)throw Error('Button not found: '+text);if(node.disabled)throw Error('Button disabled: '+text);node.click();return node;}
export function inputLabel(label,value){const field=[...document.querySelectorAll('label')].find(n=>n.querySelector('.field-label')?.textContent===label);if(!field)throw Error('Field not found: '+label);const node=field.querySelector('input,select');node.value=String(value);node.dispatchEvent(new Event(node.tagName==='SELECT'?'change':'input',{bubbles:true}));return node;}
