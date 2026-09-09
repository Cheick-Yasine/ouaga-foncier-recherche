const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('app/static/app.js','utf8');
function setup(){
 const data=new Map(), jobs=[], dom=new Map();
 const node=()=>({hidden:false,disabled:false,textContent:'',setAttribute(){},querySelector(){return null},remove(){}});
 const get=s=>{if(!dom.has(s))dom.set(s,node());return dom.get(s)};
 get('#waiting-template').content={firstElementChild:{cloneNode:node}};
 const c={pendingRequests:new Map(),thread:{id:'a',messages:[]},activePage:'chat',busy:false,checkingAlert:null,
  currentOwner:'visitor',period:{value:'30'},input:{value:''},submit:node(),messages:{after(){},setAttribute(){}},
  $:get,$$:()=>[],key:kind=>c.currentOwner+':'+kind,read:kind=>JSON.parse(data.get(c.currentOwner+':'+kind)||'[]'),
  write(){},api:(_,options)=>new Promise((resolve,reject)=>jobs.push({resolve,reject,body:JSON.parse(options.body)})),
  showPage(){},closeSidebar(){},appendMessage(){},persistThread(){},renderSidebar(){},renderConversation(){c.rendered=c.thread.id},
  historyContent:m=>m.content,cleanResult:r=>r,scrollEnd(){},toast(){},
  window:{HakimoWaiting:{start:()=>()=>{}}},localStorage:{getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v)},console,
 };
 vm.createContext(c);vm.runInContext(source.slice(source.indexOf('function syncWaitingPanels()'),source.indexOf("form.addEventListener('submit'")),c);
 return {c,data,jobs};
}
test('A response belongs to its original conversation after navigation',async()=>{
 const {c,data,jobs}=setup();const a=c.sendMessage('Question A');
 c.thread={id:'b',messages:[]};c.period.value='7';const b=c.sendMessage('Question B');
 jobs[0].resolve({answer:'Réponse A'});await a;
 assert.equal(c.thread.messages.length,1);assert.equal(c.rendered,undefined);
 assert.equal(JSON.parse(data.get('visitor:conversations'))[0].id,'a');
 assert.equal(c.pendingRequests.has('b'),true);assert.equal(c.submit.disabled,true);
 jobs[1].resolve({answer:'Réponse B'});await b;
 assert.equal(c.thread.messages[1].content,'Réponse B');assert.equal(c.rendered,'b');
 assert.equal(jobs[0].body.max_age_days,30);assert.equal(jobs[1].body.max_age_days,7);
 assert.equal(JSON.parse(data.get('visitor:conversations')).length,2);
});
test('Pending errors and storage remain associated with their original owner',async()=>{
 const {c,data,jobs}=setup();const promise=c.sendMessage('Question initiale');
 c.thread={id:'new',messages:[]};c.currentOwner='other';
 jobs[0].reject(new Error('Erreur test'));await promise;
 assert.equal(c.thread.messages.length,0);assert.equal(data.has('other:conversations'),false);
 assert.equal(JSON.parse(data.get('visitor:conversations'))[0].messages[1].error,true);
});
test('Double submit in one thread is ignored; navigation controls stay available',async()=>{
 const {c,jobs}=setup();const promise=c.sendMessage('Question initiale');await c.sendMessage('Doublon');
 assert.equal(jobs.length,1);assert.equal(c.$('#new-conversation').disabled,false);assert.equal(c.$('#account-button').disabled,false);
 jobs[0].resolve({answer:'OK'});await promise;assert.equal(c.submit.disabled,false);
});
test('History expanded returns through split view before collapsing',()=>{
 const c={sidebar:{hidden:false},sidebarCollapsed:false,mobileOpen:false,expanded:false,collapseNext:false,rememberSidebar(){},setSidebarState(){},historyToggle:{focus(){}}};
 vm.createContext(c);const start=source.indexOf("historyToggle.addEventListener('click', () => {")+"historyToggle.addEventListener('click', () => {".length;
 const body=source.slice(start,source.indexOf('\n});',start));
 vm.runInContext(body,c);assert.equal(c.expanded,true);
 vm.runInContext(body,c);assert.equal(c.expanded,false);assert.equal(c.sidebarCollapsed,false);
 vm.runInContext(body,c);assert.equal(c.sidebarCollapsed,true);
});
