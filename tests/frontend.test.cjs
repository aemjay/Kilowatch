'use strict';
// DOM unit tests with synthetic API replies. No browser, network or real accounts.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {Script} = require('node:vm');
const {JSDOM, VirtualConsole} = require('jsdom');

const root=join(__dirname,'..','app','static');
const settings={name:'Synthetic home',bridge_host:'',bridge_user:'admin',password_configured:false,
  setup_required:true,demo:false,version:'1.0.0',node_id:1,enabled:true,poll_seconds:5,
  high_load_w:3000,raw_retention_days:90,minute_retention_days:1095,max_gap_seconds:90,max_power_w:100000};
const notification={settings:{enabled:false,email_enabled:false,smtp_host:'',smtp_port:587,
  smtp_security:'starttls',smtp_user:'',smtp_from:'',email_to:[],signal_enabled:false,
  signal_url:'',signal_number:'',signal_to:[],quiet_enabled:false,quiet_start:'22:00',
  quiet_end:'07:00',recovery:true,cooldown_minutes:60,offline_enabled:true,offline_seconds:120,
  load_enabled:false,load_w:3000,load_minutes:10,daily_kwh:0,battery_enabled:true,battery_v:2.7,
  disk_enabled:true,disk_free_mb:512},history:[],last_error:'',smtp_password_configured:false,
  signal_token_configured:false};

async function until(condition) {
  for(let i=0;i<50;i++){if(condition())return;await new Promise(resolve=>setImmediate(resolve));}
  assert.ok(condition(),'Expected DOM state was not reached');
}

async function harness(options={}) {
  const errors=[],calls=[];
  let saved=structuredClone({...settings,...options.settings});
  let notes=structuredClone(notification), needsSetup=!!options.needsSetup;
  let tariffs=structuredClone(options.tariffs||[]),market={rows:[],fetched_at:null,error:''};
  const vc=new VirtualConsole();vc.on('jsdomError',error=>errors.push(error));
  const dom=new JSDOM(readFileSync(join(root,'index.html'),'utf8'),{
    url:'http://kilowatch.test/#'+(options.page||'settings'),runScripts:'outside-only',virtualConsole:vc});
  const w=dom.window;
  w.setInterval=()=>0;
  w.URL.createObjectURL=()=> 'blob:http://kilowatch.test/synthetic';
  w.URL.revokeObjectURL=()=>{};
  w.fetch=async(path,config={})=>{
    const body=config.body?JSON.parse(config.body):null;
    calls.push({path,method:config.method||'GET',body,headers:config.headers});
    let data={ok:true},status=200;
    if(path==='/api/setup/status')data={needs_setup:needsSetup};
    else if(path==='/api/setup'){needsSetup=false;}
    else if(path==='/api/settings'&&config.method==='PUT'){
      const {bridge_password,...plain}=body;
      saved={...saved,...plain,password_configured:!!bridge_password||saved.password_configured};
      saved.setup_required=!(saved.bridge_host&&saved.bridge_user&&saved.password_configured);
    }else if(path==='/api/settings')data=saved;
    else if(path==='/api/live')data={collector:{state:'setup'},reading:null,stale:true};
    else if(path==='/api/notifications'&&config.method==='PUT'){
      const {smtp_password,signal_token,...plain}=body;notes.settings=plain;
      if(smtp_password)notes.smtp_password_configured=true;
      if(signal_token)notes.signal_token_configured=true;
    }else if(path==='/api/notifications')data=notes;
    else if(path==='/api/discovery/network')data={suggestions:[{network:'192.168.1.0/24',reason:'Synthetic network'}]};
    else if(path==='/api/discovery/scan')data={network:body.network,checked:254,devices:[{ip:'192.168.1.10',host:'bridge.fritz.box',fqdn:'bridge.fritz.box'}]};
    else if(path.startsWith('/api/overview?'))data={summary:{import_kwh:null,coverage:0,cost_complete:false,base_month_factor:1,unpriced_kwh:0}};
    else if(path==='/api/tariffs'&&config.method==='PUT'){tariffs=tariffs.filter(t=>t.start_date!==body.start_date);tariffs.push(body);}
    else if(path==='/api/tariffs')data={tariffs,prices:{count:0,start:null,end:null},market};
    else if(path==='/api/market/refresh'){market={rows:[{start:1800,end:5400,ct_kwh:-5}],fetched_at:2000000000,error:''};data=market;}
    else if(path==='/api/credentials/bridge'){saved.password_configured=false;saved.enabled=false;saved.setup_required=true;}
    else if(path==='/api/bridge/test')data={protocol:'SML',endpoint:'/node_data.json',resolved_addresses:['192.168.1.10'],has_import:true};
    return {ok:status===200,status,json:async()=>structuredClone(data),blob:async()=>new w.Blob(['synthetic-image'],{type:'image/png'})};
  };
  for(const name of ['configure.js','extras.js','app.js'])new Script(readFileSync(join(root,name),'utf8'),{filename:name}).runInContext(dom.getInternalVMContext());
  await until(()=>needsSetup?!w.document.querySelector('#first-start-form').hidden:
    !!w.document.querySelector(({notifications:'#notification-form',costs:'#tariff-form'}[options.page])||'#settings-form'));
  return {w,dom,calls,errors,get settings(){return saved;}};
}

function input(w,form,name,value){w.document.querySelector(`#${form} [name="${name}"]`).value=value;}
function submit(w,id){w.document.getElementById(id).dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));}

test('first-start wizard sets own password then asks for empty bridge details',async t=>{
  const h=await harness({needsSetup:true});t.after(()=>h.dom.window.close());
  const {w}=h;
  assert.equal(w.document.querySelector('#login-form').hidden,true);
  input(w,'first-start-form','setup_code','synthetic-code');
  input(w,'first-start-form','password','synthetic-password');
  input(w,'first-start-form','confirmation','synthetic-password');
  submit(w,'first-start-form');
  await until(()=>!!w.document.querySelector('#settings-form'));
  const setup=h.calls.find(c=>c.path==='/api/setup');
  assert.deepEqual(setup.body,{setup_code:'synthetic-code',password:'synthetic-password'});
  assert.equal(setup.headers['X-Kilowatch-Request'],'1');
  for(const name of ['bridge_host','bridge_password'])
    assert.equal(w.document.querySelector(`[name="${name}"]`).value,'');
  assert.equal(w.document.querySelector('[name="bridge_user"]').value,'admin');
  assert.deepEqual(h.errors,[]);
});

test('password mismatch stays in wizard and sends no setup request',async t=>{
  const h=await harness({needsSetup:true});t.after(()=>h.dom.window.close());
  input(h.w,'first-start-form','password','synthetic-password');
  input(h.w,'first-start-form','confirmation','another-password');
  submit(h.w,'first-start-form');
  await until(()=>!!h.w.document.querySelector('#setup-error').textContent);
  assert.equal(h.calls.some(c=>c.path==='/api/setup'),false);
});

test('bridge test accepts FQDN and saved secret is never rendered back',async t=>{
  const h=await harness({settings:{setup_required:false,bridge_host:'old.fritz.box',bridge_user:'synthetic-user',password_configured:true}});
  t.after(()=>h.dom.window.close());const {w}=h;
  input(w,'settings-form','bridge_host','bridge.fritz.box');
  w.document.querySelector('#test-bridge').click();
  await until(()=>!w.document.querySelector('#bridge-result').hidden);
  assert.match(w.document.querySelector('#bridge-result').textContent,/192\.168\.1\.10/);
  const check=h.calls.find(c=>c.path==='/api/bridge/test');
  assert.equal(check.body.bridge_host,'bridge.fritz.box');
  assert.equal('bridge_password' in check.body,false);
  submit(w,'settings-form');
  await until(()=>h.settings.bridge_host==='bridge.fritz.box');
  assert.equal(w.document.querySelector('[name="bridge_password"]').value,'');
  assert.deepEqual(h.errors,[]);
});

test('notification form normalizes recipients and saves before explicit test',async t=>{
  const h=await harness({page:'notifications',settings:{setup_required:false}});
  t.after(()=>h.dom.window.close());const {w}=h;
  input(w,'notification-form','smtp_host','smtp.example.test');
  input(w,'notification-form','smtp_from','from@example.test');
  input(w,'notification-form','email_to','one@example.test; two@example.test\nthree@example.test');
  input(w,'notification-form','smtp_password','synthetic-smtp-password');
  w.document.querySelector('#test-email').click();
  await until(()=>h.calls.some(c=>c.path==='/api/notifications/test/email'));
  const update=h.calls.find(c=>c.path==='/api/notifications'&&c.method==='PUT');
  assert.deepEqual(update.body.email_to,['one@example.test','two@example.test','three@example.test']);
  assert.equal(update.body.enabled,false);
  assert.equal(update.body.smtp_port,587);
  assert.equal(update.body.smtp_password,'synthetic-smtp-password');
  assert.ok(h.calls.indexOf(update)<h.calls.findIndex(c=>c.path==='/api/notifications/test/email'));
  await until(()=>w.document.querySelector('[name="smtp_password"]').value==='');
  assert.deepEqual(h.errors,[]);
});

test('forget bridge password pauses acquisition without erasing address',async t=>{
  const h=await harness({settings:{setup_required:false,bridge_host:'bridge.fritz.box',bridge_user:'synthetic-user',password_configured:true}});
  t.after(()=>h.dom.window.close());h.w.document.querySelector('#forget-bridge').click();
  await until(()=>!h.settings.password_configured);
  assert.equal(h.settings.enabled,false);
  assert.equal(h.settings.bridge_host,'bridge.fritz.box');
  assert.ok(h.calls.some(c=>c.path==='/api/credentials/bridge'&&c.method==='DELETE'));
});

test('Signal pairing saves gateway and requests a protected local QR image',async t=>{
  const h=await harness({page:'notifications',settings:{setup_required:false}});
  t.after(()=>h.dom.window.close());const {w}=h;
  input(w,'notification-form','signal_url','http://signal-api:8080');
  w.document.querySelector('#signal-qr-button').click();
  await until(()=>!!w.document.querySelector('#signal-qr img'));
  const request=h.calls.find(c=>c.path==='/api/notifications/signal/qr');
  assert.equal(request.method,'POST');
  assert.equal(request.headers['X-Kilowatch-Request'],'1');
  assert.equal(w.document.querySelector('#signal-qr').hidden,false);
  assert.match(w.document.querySelector('#signal-qr img').alt,/QR-Code/);
  assert.deepEqual(h.errors,[]);
});

test('subnet discovery works before credentials and adopts discovered FQDN',async t=>{
  const h=await harness();t.after(()=>h.dom.window.close());const {w}=h;
  await until(()=>w.document.querySelector('#discovery-network').value==='192.168.1.0/24');
  w.document.querySelector('#discover-bridge').click();
  await until(()=>!!w.document.querySelector('[data-use-device]'));
  const request=h.calls.find(c=>c.path==='/api/discovery/scan');
  assert.deepEqual(request.body,{network:'192.168.1.0/24'});
  w.document.querySelector('[data-use-device]').click();
  assert.equal(w.document.querySelector('[name="bridge_host"]').value,'bridge.fritz.box');
  assert.equal(w.document.querySelector('[name="bridge_password"]').value,'');
  assert.deepEqual(h.errors,[]);
});

test('HT/NT switch submits two prices and local schedule in correct units',async t=>{
  const h=await harness({page:'costs',settings:{setup_required:false}});t.after(()=>h.dom.window.close());const {w}=h;
  const form=w.document.querySelector('#tariff-form');
  form.elements.mode.value='dual';form.elements.mode.dispatchEvent(new w.Event('change'));
  assert.equal(form.elements.low_ct.disabled,false);
  for(const [name,value] of Object.entries({name:'Synthetic HT/NT',ct_kwh:'35',low_ct:'25',low_start:'21:45',low_end:'07:15',weekend_low:'true'}))input(w,'tariff-form',name,value);
  submit(w,'tariff-form');
  await until(()=>h.calls.some(c=>c.path==='/api/tariffs'&&c.method==='PUT'));
  const request=h.calls.find(c=>c.path==='/api/tariffs'&&c.method==='PUT');
  assert.equal(request.body.eur_kwh,.35);assert.equal(request.body.low_eur_kwh,.25);
  assert.equal(request.body.low_start,'21:45');assert.equal(request.body.low_end,'07:15');
  assert.equal(request.body.weekend_low,true);
  await until(()=>!!w.document.querySelector('[data-edit-tariff]'));
  w.document.querySelector('[data-edit-tariff]').click();
  assert.equal(w.document.querySelector('#tariff-form').elements.low_ct.value,'25');
  assert.deepEqual(h.errors,[]);
});

test('market prices are fetched only by explicit click and clearly separate from contract',async t=>{
  const h=await harness({page:'costs',settings:{setup_required:false}});t.after(()=>h.dom.window.close());const {w}=h;
  assert.equal(h.calls.some(c=>c.path==='/api/market/refresh'),false);
  assert.match(w.document.querySelector('#page-costs').textContent,/Netto-Börsenpreise/);
  w.document.querySelector('#market-refresh').click();
  await until(()=>h.calls.some(c=>c.path==='/api/market/refresh'));
  assert.equal(h.calls.find(c=>c.path==='/api/market/refresh').method,'POST');
  assert.deepEqual(h.errors,[]);
});
