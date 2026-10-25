'use strict';
// DOM unit tests with synthetic API replies. No browser, network or real accounts.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const {existsSync,readFileSync} = require('node:fs');
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
  let budget={settings:{monthly_eur:null,monthly_kwh:null,abschlag_eur:null},month:{observed_eur:3,observed_kwh:10,forecast_eur:null,forecast_kwh:null,forecast_reason:'Zu wenig Daten'},annual:{available:false,reason:'Mindestens 60 vollständig erfasste Tage erforderlich.'}};
  const vc=new VirtualConsole();vc.on('jsdomError',error=>errors.push(error));
  const dom=new JSDOM(readFileSync(join(root,'index.html'),'utf8'),{
    url:'http://kilowatch.test/#'+(options.page||'settings'),runScripts:'outside-only',virtualConsole:vc});
  const w=dom.window;
  w.setInterval=()=>0;
  // jsdom meldet en-US: Sprache festlegen, damit die deutschen Erwartungen gelten.
  w.localStorage.setItem('kilowatch-language',options.language||'de');
  w.URL.createObjectURL=()=> 'blob:http://kilowatch.test/synthetic';
  w.URL.revokeObjectURL=()=>{};
  w.fetch=async(path,config={})=>{
    if(path.startsWith('/i18n/')){
      const file=join(root,path);
      const catalog=existsSync(file)?JSON.parse(readFileSync(file,'utf8')):{};
      return {ok:true,status:200,json:async()=>structuredClone(catalog)};
    }
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
    else if(path.startsWith('/api/overview?'))data={summary:{import_kwh:null,coverage:0,cost_complete:false,base_month_factor:1,unpriced_kwh:0,start:0,end:3600},previous:null,gaps:[],targets:{daily_kwh:null,household:options.household??null},co2:options.co2??null,
      series:{group:'quarter',power_resolution_seconds:60,energy:[],power:Array.from({length:60},(_,i)=>({ts:i*60,power_w:i===30?4000:300+i,seconds:60}))}};
    else if(path==='/api/tariffs'&&config.method==='PUT'){tariffs=tariffs.filter(t=>t.start_date!==body.start_date);tariffs.push(body);}
    else if(path==='/api/tariffs')data={tariffs,prices:{count:0,start:null,end:null},market};
    else if(path==='/api/market/refresh'){market={rows:[{start:1800,end:5400,ct_kwh:-5}],fetched_at:2000000000,error:''};data=market;}
    else if(path==='/api/budget'&&config.method==='PUT'){budget.settings=body;}
    else if(path==='/api/budget')data={...budget,reference:options.household??null};
    else if(path==='/api/simulate')data={energy_cost_eur:10,base_cost_eur:2,feedin_eur:0,total_eur:12,actual_total_eur:13,priced_share:.5,average_eur_kwh:.3,comparable:false,paired_share:.5,difference_eur:-1.25,spot_weighted_ct:9,spot_time_average_ct:8};
    else if(path==='/api/updates')data={enabled:false,current:'1.0.0',repository:'example/kilowatch',checked_at:null,error:'',available:false};
    else if(path==='/api/credentials/bridge'){saved.password_configured=false;saved.enabled=false;saved.setup_required=true;}
    else if(path==='/api/bridge/test')data={protocol:'SML',endpoint:'/node_data.json',resolved_addresses:['192.168.1.10'],has_import:true};
    return {ok:status===200,status,json:async()=>structuredClone(data),blob:async()=>new w.Blob(['synthetic-image'],{type:'image/png'})};
  };
  for(const name of ['theme.js','i18n.js','overlays.js','configure.js','extras.js','insights.js','app.js'])new Script(readFileSync(join(root,name),'utf8'),{filename:name}).runInContext(dom.getInternalVMContext());
  await until(()=>needsSetup?!w.document.querySelector('#first-start-form').hidden:
    !!w.document.querySelector(({notifications:'#notification-form',costs:'#tariff-form',history:'#page-history .chart',dashboard:'#page-dashboard .cards'}[options.page])||'#settings-form'));
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

test('tariff simulation sends spot markup in ct and shows an honest result',async t=>{
  const h=await harness({page:'costs',settings:{setup_required:false}});t.after(()=>h.dom.window.close());const {w}=h;
  await until(()=>!!w.document.querySelector('#simulation-form'));
  const form=w.document.querySelector('#simulation-form');
  form.elements.mode.value='spot';form.elements.mode.dispatchEvent(new w.Event('change'));
  assert.equal(form.elements.ct_kwh.disabled,true);
  assert.equal(form.elements.markup_ct.disabled,false);
  for(const [name,value] of Object.entries({markup_ct:'18.5',vat_percent:'19',base_month:'10',feedin_ct:'8'}))input(w,'simulation-form',name,value);
  submit(w,'simulation-form');
  await until(()=>h.calls.some(c=>c.path==='/api/simulate'));
  const request=h.calls.find(c=>c.path==='/api/simulate').body;
  assert.equal(request.tariff.mode,'spot');assert.equal(request.tariff.markup_ct,18.5);
  assert.equal(request.tariff.feedin_eur_kwh,.08);assert.equal('eur_kwh' in request.tariff,false);
  await until(()=>w.document.querySelector('#simulation-result').textContent.includes('Günstiger als dein Tarif'));
  assert.match(w.document.querySelector('#simulation-result').textContent,/50,0 %/);
  assert.match(w.document.querySelector('#simulation-result').textContent,/verbrauchsgewichtet/);
  assert.deepEqual(h.errors,[]);
});

test('budget form saves empty fields as null',async t=>{
  const h=await harness({page:'costs',settings:{setup_required:false}});t.after(()=>h.dom.window.close());const {w}=h;
  await until(()=>!!w.document.querySelector('#budget-form'));
  input(w,'budget-form','monthly_eur','90');input(w,'budget-form','abschlag_eur','85.5');
  submit(w,'budget-form');
  await until(()=>h.calls.some(c=>c.path==='/api/budget'&&c.method==='PUT'));
  assert.deepEqual(h.calls.find(c=>c.path==='/api/budget'&&c.method==='PUT').body,{monthly_eur:90,monthly_kwh:null,abschlag_eur:85.5});
  assert.deepEqual(h.errors,[]);
});

test('theme toggle cycles auto, light and dark and remembers the choice',async t=>{
  const h=await harness({settings:{setup_required:false}});t.after(()=>h.dom.window.close());const {w}=h;
  const root=w.document.documentElement,button=w.document.querySelector('#theme-toggle');
  assert.equal(root.hasAttribute('data-theme'),false);
  button.click();assert.equal(root.getAttribute('data-theme'),'light');assert.equal(w.localStorage.getItem('kilowatch-theme'),'light');
  button.click();assert.equal(root.getAttribute('data-theme'),'dark');assert.equal(button.textContent,'Dunkel');
  button.click();assert.equal(root.hasAttribute('data-theme'),false);assert.equal(w.localStorage.getItem('kilowatch-theme'),null);
  assert.deepEqual(h.errors,[]);
});

test('English interface translates static and dynamic texts and tells the server the language',async t=>{
  const h=await harness({language:'en',page:'costs',settings:{setup_required:false,language:'en'}});t.after(()=>h.dom.window.close());const {w}=h;
  const en=JSON.parse(readFileSync(join(root,'i18n','en.json'),'utf8'));
  assert.equal(w.document.documentElement.lang,'en');
  const nav=w.document.querySelector('[data-page="costs"] bdi').textContent;
  assert.equal(nav,en['Kosten & Tarife']);assert.notEqual(nav,'Kosten & Tarife');
  await until(()=>!!w.document.querySelector('#tariff-form'));
  assert.match(w.document.querySelector('#page-costs').textContent,new RegExp(en['Tarifart'].replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
  assert.equal(w.document.title,en['Kilowatch · Energie zu Hause']);
  assert.ok(h.calls.filter(c=>c.path.startsWith('/api/')).every(c=>c.headers['X-Kilowatch-Language']==='en'));
  assert.deepEqual(h.errors,[]);
});

test('language and currency form saves both and hides euro spot prices for other currencies',async t=>{
  const h=await harness({settings:{setup_required:false,language:'de'}});t.after(()=>h.dom.window.close());const {w}=h;
  await until(()=>!!w.document.querySelector('#locale-form'));
  input(w,'locale-form','language','nl');input(w,'locale-form','currency','SEK');
  submit(w,'locale-form');
  await until(()=>h.calls.some(c=>c.path==='/api/settings'&&c.method==='PUT'&&c.body.currency==='SEK'));
  assert.deepEqual(h.calls.find(c=>c.body?.currency==='SEK').body,{language:'nl',currency:'SEK'});
  await until(()=>w.document.documentElement.lang==='nl');
  assert.equal(w.localStorage.getItem('kilowatch-language'),'nl');
  w.document.querySelector('[data-page="costs"]').click();
  await until(()=>!!w.document.querySelector('#simulation-form'));
  assert.equal(w.document.querySelector('#market-refresh'),null);
  assert.equal(w.document.querySelector('#simulation-form [name="mode"] option[value="spot"]'),null);
  assert.match(w.document.querySelector('#page-costs').textContent,/öre/);
  assert.doesNotMatch(w.document.querySelector('#page-costs').textContent,/\bct\b|€/);
  assert.deepEqual(h.errors,[]);
});

test('login screen offers all languages and switches immediately',async t=>{
  const h=await harness({settings:{setup_required:false}});t.after(()=>h.dom.window.close());const {w}=h;
  const select=w.document.querySelector('#login-language');
  assert.deepEqual([...select.options].map(o=>o.value),['de','en','nb','sv','nl']);
  select.value='sv';select.dispatchEvent(new w.Event('change'));
  await until(()=>w.document.documentElement.lang==='sv');
  const sv=JSON.parse(readFileSync(join(root,'i18n','sv.json'),'utf8'));
  assert.equal(w.document.querySelector('#login-form h2 bdi').textContent,sv['Anmelden']);
  assert.deepEqual(h.errors,[]);
});

test('hour views request the last hours and calendar dates switch back',async t=>{
  const h=await harness({page:'costs',settings:{setup_required:false}});t.after(()=>h.dom.window.close());const {w}=h;
  w.document.querySelector('[data-range="hours1"]').click();
  await until(()=>h.calls.some(c=>c.path==='/api/overview?hours=1'));
  assert.ok(w.document.querySelector('[data-range="hours1"]').classList.contains('selected'));
  w.document.querySelector('[data-range="hours6"]').click();
  await until(()=>h.calls.some(c=>c.path==='/api/overview?hours=6'));
  submit(w,'range-form');
  await until(()=>h.calls.filter(c=>c.path.startsWith('/api/overview?start=')).length>=2);
  assert.equal(w.document.querySelector('[data-range="hours6"]').classList.contains('selected'),false);
  assert.deepEqual(h.errors,[]);
});

test('rolling mean and min/max follow the window and restart after gaps',async t=>{
  const h=await harness({settings:{setup_required:false}});t.after(()=>h.dom.window.close());const {w}=h;
  const data=[{ts:0,v:1},{ts:60,v:3},{ts:120,v:5},{ts:1000,v:10},{ts:1060,v:null},{ts:1120,v:20}];
  const plain=value=>JSON.parse(JSON.stringify(value));
  const out=plain(w.rolling(data,'v','ts',150,false,300));
  assert.deepEqual(out.map(p=>p.mean),[1,2,3,10,null,15]);
  assert.deepEqual(out.map(p=>[p.low,p.high]),[[1,1],[1,3],[1,5],[10,10],[null,null],[10,20]]);
  assert.deepEqual(plain(w.rolling([{x:1,v:2},{x:2,v:4},{x:3,v:6}],'v','x',2,true)).map(p=>p.mean),[2,3,5]);
});

test('chart overlays can be switched on, are drawn and remembered',async t=>{
  const h=await harness({page:'history',settings:{setup_required:false,high_load_w:3000}});t.after(()=>h.dom.window.close());const {w}=h;
  const toggles=[...w.document.querySelectorAll('[data-overlay-chart="power"] input')].map(input=>input.value);
  assert.deepEqual(toggles,['mean','moving','range','highload']);
  assert.equal(w.document.querySelector('#page-history .overlay-line'),null);
  for(const key of ['moving','range','highload']){
    const input=w.document.querySelector(`[data-overlay-chart="power"] input[value="${key}"]`);
    input.checked=true;input.dispatchEvent(new w.Event('change',{bubbles:true}));
  }
  await until(()=>!!w.document.querySelector('#page-history .overlay-line'));
  assert.ok(w.document.querySelector('#page-history .overlay-band'));
  assert.ok(w.document.querySelector('#page-history .overlay-hline.overlay-reference'));
  assert.deepEqual(JSON.parse(w.localStorage.getItem('kilowatch-overlays-power')),['moving','range','highload']);
  assert.deepEqual(h.errors,[]);
});

test('dashboard shows the CO2 balance with source and the settings choose the grid country',async t=>{
  const co2={country:'de',kg:1.234,covered_kwh:3,uncovered_kwh:.5,g_kwh:411,renewable_share:48,current:{start:1800000000,g_kwh:300,renewable_share:120},source:'Energy-Charts.info (Fraunhofer ISE), CC BY 4.0',demo:false,error:'',deprecated:false};
  const h=await harness({page:'dashboard',co2,settings:{setup_required:false,grid_country:'de'}});t.after(()=>h.dom.window.close());const {w}=h;
  const text=w.document.querySelector('#page-dashboard').textContent;
  assert.match(text,/Strommix und CO₂/);assert.match(text,/1,23 kg/);assert.match(text,/411 g\/kWh/);
  assert.match(text,/Zuletzt veröffentlicht \([^)]+\)300 g\/kWh · 100 %/);
  assert.match(text,/0,50 kWh ohne veröffentlichten CO₂-Wert/);assert.match(text,/Quelle: Energy-Charts\.info \(Fraunhofer ISE\), CC BY 4\.0/);
  w.document.querySelector('[data-page="settings"]').click();
  await until(()=>!!w.document.querySelector('#grid-form'));
  assert.equal(w.document.querySelector('#grid-form [name="grid_country"]').value,'de');
  input(w,'grid-form','grid_country','');submit(w,'grid-form');
  await until(()=>h.calls.some(c=>c.method==='PUT'&&c.body?.grid_country===''));
  assert.deepEqual(h.errors,[]);
});

test('typical household reference appears in budget, comparison and settings',async t=>{
  const household={annual_kwh:2700,persons:2,type:'house',hot_water:false,source:'Stromspiegel für Deutschland (co2online), Stand 05/2025'};
  const h=await harness({page:'costs',household,settings:{setup_required:false,household_persons:2,household_type:'house'}});t.after(()=>h.dom.window.close());const {w}=h;
  await until(()=>!!w.document.querySelector('#budget-form'));
  const costs=w.document.querySelector('#page-costs').textContent;
  assert.match(costs,/Typischer Haushalt pro Jahr2\.700 kWh/);
  assert.match(costs,/Typischer Haushalt: etwa 225 kWh pro Monat/);
  assert.match(costs,/2 Personen im Haus laut Stromspiegel/);
  w.document.querySelector('[data-page="settings"]').click();
  await until(()=>!!w.document.querySelector('#household-form'));
  input(w,'household-form','household_persons','4');input(w,'household-form','household_hot_water','true');submit(w,'household-form');
  await until(()=>h.calls.some(c=>c.method==='PUT'&&c.body?.household_persons===4));
  assert.deepEqual(h.calls.find(c=>c.body?.household_persons===4).body,{household_persons:4,household_type:'house',household_hot_water:true});
  assert.deepEqual(h.errors,[]);
});

test('background refresh neither dims the page nor redraws unchanged data',async t=>{
  const h=await harness({page:'dashboard',settings:{setup_required:false}});t.after(()=>h.dom.window.close());const {w}=h;
  const target=w.document.querySelector('#page-dashboard');
  const before=target.querySelector('.cards');
  const observed=[];new w.MutationObserver(()=>observed.push(target.className)).observe(target,{attributes:true,attributeFilter:['class']});
  const calls=h.calls.length;
  await w.loadPage({background:true});
  assert.ok(h.calls.length>calls,'refresh requested data');
  assert.equal(target.querySelector('.cards'),before,'identical data keeps the rendered page');
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(observed.filter(c=>c.includes('loading')),[]);
  assert.deepEqual(h.errors,[]);
});
