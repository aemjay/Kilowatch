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
  smtp_security:'starttls',smtp_user:'',smtp_from:'',smtp_from_name:'Kilowatch',subject_code:'',email_to:[],quiet_enabled:false,quiet_start:'22:00',
  quiet_end:'07:00',recovery:true,cooldown_minutes:60,offline_enabled:true,offline_seconds:120,
  load_enabled:false,load_w:3000,load_minutes:10,daily_kwh:0,battery_enabled:true,battery_v:2.7,
  disk_enabled:true,disk_free_mb:512},history:[],last_error:'',smtp_password_configured:false};

async function until(condition) {
  for(let i=0;i<50;i++){if(condition())return;await new Promise(resolve=>setImmediate(resolve));}
  assert.ok(condition(),'Expected DOM state was not reached');
}

async function harness(options={}) {
  const errors=[],calls=[];
  let saved=structuredClone({...settings,...options.settings});
  let notes=structuredClone(notification), needsSetup=!!options.needsSetup;
  let priceFeed={source:'',zone:'DE-LU',markup_ct:0,vat_percent:0,tibber_home:'',tibber_token_configured:false,zones:['DE-LU','AT','NL','BE','FR'],spot_source:'Energy-Charts',status:{fetched_at:null,error:'',homes:[]}};
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
    else if(path==='/api/live')data=options.live||{collector:{state:'setup'},reading:null,stale:true};
    else if(path.startsWith('/api/prices/outlook'))data=typeof options.outlook==='function'?options.outlook(path):options.outlook||{dynamic:false,intervals:[]};
    else if(path==='/api/notifications'&&config.method==='PUT'){
      const {smtp_password,...plain}=body;notes.settings=plain;
      if(smtp_password)notes.smtp_password_configured=true;
    }else if(path==='/api/notifications')data=notes;
    else if(path==='/api/discovery/network')data={suggestions:[{network:'192.168.1.0/24',reason:'Synthetic network'}]};
    else if(path==='/api/discovery/scan')data={network:body.network,checked:254,devices:[{ip:'192.168.1.10',host:'bridge.example.lan',fqdn:'bridge.example.lan'}]};
    else if(path==='/api/timeline')data=options.timeline||{start:null,end:0,bin_seconds:900,bins:[]};
    else if(path.startsWith('/api/overview?'))data={summary:{import_kwh:null,coverage:0,cost_complete:false,base_month_factor:1,unpriced_kwh:0,start:options.window?.start??0,end:options.window?.end??3600},previous:null,gaps:[],targets:{daily_kwh:null,household:options.household??null},co2:options.co2??null,
      series:options.series||{group:'quarter',power_resolution_seconds:60,energy:[],power:Array.from({length:60},(_,i)=>({ts:(options.window?.start??0)+i*60,power_w:i===30?4000:300+i,seconds:60}))}};
    else if(path==='/api/tariffs'&&config.method==='PUT'){tariffs=tariffs.filter(t=>t.start_date!==body.start_date);tariffs.push(body);}
    else if(path==='/api/prices/source'){priceFeed={...priceFeed,...body,tibber_token_configured:!!body.tibber_token||priceFeed.tibber_token_configured};delete priceFeed.tibber_token;data=priceFeed;}
    else if(path==='/api/tariffs')data={tariffs,prices:{count:0,start:null,end:null},market,price_feed:priceFeed};
    else if(path==='/api/market/refresh'){market={rows:[{start:1800,end:5400,ct_kwh:-5}],fetched_at:2000000000,error:''};data=market;}
    else if(path==='/api/budget'&&config.method==='PUT'){budget.settings=body;}
    else if(path==='/api/budget')data={...budget,reference:options.household??null};
    else if(path==='/api/simulate')data={energy_cost_eur:10,base_cost_eur:2,feedin_eur:0,total_eur:12,actual_total_eur:13,priced_share:.5,average_eur_kwh:.3,comparable:false,paired_share:.5,difference_eur:-1.25,spot_weighted_ct:9,spot_time_average_ct:8};
    else if(path==='/api/updates')data={enabled:false,current:'1.0.0',repository:'example/kilowatch',checked_at:null,error:'',available:false};
    else if(path==='/api/credentials/bridge'){saved.password_configured=false;saved.enabled=false;saved.setup_required=true;}
    else if(path==='/api/bridge/test')data={protocol:'SML',endpoint:'/node_data.json',resolved_addresses:['192.168.1.10'],has_import:true};
    return {ok:status===200,status,json:async()=>structuredClone(data),blob:async()=>new w.Blob(['synthetic-image'],{type:'image/png'})};
  };
  for(const name of ['theme.js','i18n.js','overlays.js','charts.js','timeline.js','configure.js','extras.js','insights.js','dashboard.js','app.js'])new Script(readFileSync(join(root,name),'utf8'),{filename:name}).runInContext(dom.getInternalVMContext());
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
  const h=await harness({settings:{setup_required:false,bridge_host:'old.example.lan',bridge_user:'synthetic-user',password_configured:true}});
  t.after(()=>h.dom.window.close());const {w}=h;
  input(w,'settings-form','bridge_host','bridge.example.lan');
  w.document.querySelector('#test-bridge').click();
  await until(()=>!w.document.querySelector('#bridge-result').hidden);
  assert.match(w.document.querySelector('#bridge-result').textContent,/192\.168\.1\.10/);
  const check=h.calls.find(c=>c.path==='/api/bridge/test');
  assert.equal(check.body.bridge_host,'bridge.example.lan');
  assert.equal('bridge_password' in check.body,false);
  submit(w,'settings-form');
  await until(()=>h.settings.bridge_host==='bridge.example.lan');
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
  const h=await harness({settings:{setup_required:false,bridge_host:'bridge.example.lan',bridge_user:'synthetic-user',password_configured:true}});
  t.after(()=>h.dom.window.close());h.w.document.querySelector('#forget-bridge').click();
  await until(()=>!h.settings.password_configured);
  assert.equal(h.settings.enabled,false);
  assert.equal(h.settings.bridge_host,'bridge.example.lan');
  assert.ok(h.calls.some(c=>c.path==='/api/credentials/bridge'&&c.method==='DELETE'));
});

test('sender name and subject code are saved; no Signal fields remain',async t=>{
  const h=await harness({page:'notifications',settings:{setup_required:false}});
  t.after(()=>h.dom.window.close());const {w}=h;
  assert.equal(w.document.querySelector('[name="smtp_from_name"]').value,'Kilowatch');
  assert.equal(w.document.querySelector('[name^="signal"]'),null);
  input(w,'notification-form','smtp_from_name','Stromzähler');
  input(w,'notification-form','subject_code','Kuckuck-17');
  w.document.querySelector('#notification-form button[type="submit"]').click();
  await until(()=>h.calls.some(c=>c.path==='/api/notifications'&&c.method==='PUT'));
  const update=h.calls.find(c=>c.path==='/api/notifications'&&c.method==='PUT');
  assert.equal(update.body.smtp_from_name,'Stromzähler');
  assert.equal(update.body.subject_code,'Kuckuck-17');
  assert.ok(!Object.keys(update.body).some(key=>key.includes('signal')));
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
  assert.equal(w.document.querySelector('[name="bridge_host"]').value,'bridge.example.lan');
  assert.equal(w.document.querySelector('[name="bridge_password"]').value,'');
  assert.deepEqual(h.errors,[]);
});

test('price source shows only the fields of the chosen source and never echoes the token',async t=>{
  const h=await harness({page:'costs',settings:{setup_required:false}});t.after(()=>h.dom.window.close());const {w}=h;
  await until(()=>!!w.document.querySelector('#price-source-form'));
  const form=w.document.querySelector('#price-source-form');
  assert.equal(form.elements.tibber_token.closest('label').hidden,true);
  form.elements.source.value='spot';form.elements.source.dispatchEvent(new w.Event('change'));
  assert.equal(form.elements.zone.disabled,false);assert.equal(form.elements.tibber_token.disabled,true);
  form.elements.source.value='tibber';form.elements.source.dispatchEvent(new w.Event('change'));
  input(w,'price-source-form','tibber_token','synthetic-token');
  submit(w,'price-source-form');
  await until(()=>h.calls.some(c=>c.path==='/api/prices/source'));
  const request=h.calls.find(c=>c.path==='/api/prices/source');
  assert.equal(request.body.source,'tibber');assert.equal(request.body.tibber_token,'synthetic-token');assert.equal(request.body.markup_ct,0);
  await until(()=>!!w.document.querySelector('#tibber-forget'));
  assert.equal(w.document.querySelector('#price-source-form').elements.tibber_token.value,'');
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

test('minute and hour views request their window and calendar dates switch back',async t=>{
  const h=await harness({page:'costs',settings:{setup_required:false}});t.after(()=>h.dom.window.close());const {w}=h;
  w.document.querySelector('[data-range="hours1"]').click();
  await until(()=>h.calls.some(c=>c.path==='/api/overview?hours=1'));
  assert.ok(w.document.querySelector('[data-range="hours1"]').classList.contains('selected'));
  w.document.querySelector('[data-range="hours6"]').click();
  await until(()=>h.calls.some(c=>c.path==='/api/overview?hours=6'));
  w.document.querySelector('[data-range="minutes15"]').click();
  await until(()=>h.calls.some(c=>c.path==='/api/overview?minutes=15'));
  w.document.querySelector('[data-range="minutes5"]').click();
  await until(()=>h.calls.some(c=>c.path==='/api/overview?minutes=5'));
  assert.ok(w.document.querySelector('[data-range="minutes5"]').classList.contains('selected'));
  submit(w,'range-form');
  await until(()=>h.calls.filter(c=>c.path.startsWith('/api/overview?start=')).length>=2);
  assert.equal(w.document.querySelector('[data-range="minutes5"]').classList.contains('selected'),false);
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

test('dashboard shows the live cost rate and a hint without tariff',async t=>{
  const reading={ts:1,power_w:2000,import_kwh:10,export_kwh:0};
  const h=await harness({page:'dashboard',settings:{setup_required:false},live:{collector:{state:'online'},reading,stale:false,age_seconds:1,
    cost:{tariff:true,mode:'fixed',rate_eur_kwh:.3,feedin_eur_kwh:null,direction:'import',eur_per_hour:.6}}});
  t.after(()=>h.dom.window.close());const {w}=h;
  assert.equal(w.document.querySelector('#live-cost').textContent,'0,60');
  assert.match(w.document.querySelector('#live-cost-note').textContent,/Arbeitspreis 30,00 ct\/kWh/);
  // Einspeisung ohne Vergütung: kein Betrag, Hinweis.
  w.eval("live={...live,cost:{tariff:true,mode:'fixed',rate_eur_kwh:.3,feedin_eur_kwh:null,direction:'export',eur_per_hour:null}};updateLiveCost()");
  assert.equal(w.document.querySelector('#live-cost-label').textContent,'Erlös gerade');
  assert.equal(w.document.querySelector('#live-cost').textContent,'—');
  w.eval("live={...live,cost:{tariff:false}};updateLiveCost()");
  assert.equal(w.document.querySelector('#live-cost-note').textContent,'Tarif unter Kosten & Tarife anlegen');
  assert.equal(w.document.querySelector('#price-outlook-slot').textContent,'');
  assert.deepEqual(h.errors,[]);
});

test('price traffic light colours quarters, marks now and switches the window length',async t=>{
  const start=1792969200,now=start+10*3600;
  const outlook=path=>{
    const hours=Number(new URLSearchParams(path.split('?')[1]).get('window_hours'));
    const intervals=Array.from({length:96},(_,i)=>({start:start+i*900,end:start+i*900+900,eur_kwh:i<40?.3:i<48?.1:.2}));
    return {dynamic:true,timezone:'Europe/Berlin',now,current_start:now,window_hours:hours,start,end:start+2*86400,tomorrow_start:start+86400,
      intervals,tomorrow_available:false,low_eur_kwh:.1,high_eur_kwh:.3,cheapest:{start:start+40*900,end:start+40*900+hours*3600,average_eur_kwh:hours===2?.1:.15}};
  };
  const h=await harness({page:'dashboard',settings:{setup_required:false},outlook});t.after(()=>h.dom.window.close());const {w}=h;
  await until(()=>!!w.document.querySelector('#price-window-text'));
  const slot=w.document.querySelector('#price-outlook-slot');
  assert.match(w.document.querySelector('#price-window-text').textContent,/Heute 10:00–12:00, Ø 10,0 ct\/kWh/);
  assert.equal(slot.querySelectorAll('rect.price-low').length,8);
  assert.equal(slot.querySelectorAll('rect.price-high').length,40);
  assert.equal(slot.querySelectorAll('rect.price-current').length,1);
  assert.match(slot.textContent,/Preise für morgen erscheinen am frühen Nachmittag/);
  slot.querySelector('[data-price-window="3"]').click();
  await until(()=>/Ø 15,0/.test(w.document.querySelector('#price-window-text')?.textContent||''));
  assert.ok(h.calls.some(c=>c.path==='/api/prices/outlook?window_hours=3'));
  assert.equal(w.document.querySelector('[data-price-window="3"]').getAttribute('aria-pressed'),'true');
  assert.deepEqual(h.errors,[]);
});

// --- Diagramme: Tooltip, Fadenkreuz, Zoom und Zeitbalken ---
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const windowCalls=h=>h.calls.filter(c=>c.path.startsWith('/api/overview?since=')).map(c=>Object.fromEntries(new URLSearchParams(c.path.split('?')[1])));

test('hovering a line chart shows crosshair, marker and a tooltip with the nearest value',async t=>{
  const h=await harness({page:'history',settings:{setup_required:false,high_load_w:3000}});t.after(()=>h.dom.window.close());const {w}=h;
  const chart=w.document.querySelector('#page-history .chart');
  await until(()=>!!chart.querySelector('.chart-tip'));
  assert.equal(chart.querySelectorAll('title').length,0,'keine trägen Browser-Tooltips mehr');
  const tip=chart.querySelector('.chart-tip');
  assert.equal(tip.hidden,true);
  // Messpunkt 30 (4000 W) liegt bei x = 47 + 1800/3600 * 701 = 397,5.
  chart.dispatchEvent(new w.MouseEvent('pointermove',{bubbles:true,clientX:399}));
  assert.equal(tip.hidden,false);
  assert.match(tip.textContent,/4\.000,0 W/);
  assert.equal(chart.querySelector('.chart-cursor').hasAttribute('hidden'),false);
  assert.equal(chart.querySelector('.chart-cursor line').getAttribute('x1'),'397.5');
  assert.equal(chart.querySelector('.chart-cursor circle').hasAttribute('hidden'),false);
  chart.dispatchEvent(new w.MouseEvent('pointerleave',{bubbles:true}));
  assert.equal(tip.hidden,true);
  assert.equal(chart.querySelector('.chart-cursor').hasAttribute('hidden'),true);
});

test('a line chart is reachable by keyboard and says when there are no data',async t=>{
  const h=await harness({page:'history',settings:{setup_required:false}});t.after(()=>h.dom.window.close());const {w}=h;
  const chart=w.document.querySelector('#page-history .chart');
  await until(()=>!!chart.querySelector('.chart-tip'));
  const tip=chart.querySelector('.chart-tip');
  chart.dispatchEvent(new w.FocusEvent('focus'));
  assert.equal(tip.hidden,false);
  const last=tip.textContent;
  chart.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true,cancelable:true}));
  assert.notEqual(tip.textContent,last);
  assert.equal(tip.getAttribute('role'),'status','Tastaturbedienung wird angesagt');
  chart.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));
  assert.equal(tip.hidden,true);
  // Hinter dem letzten Messpunkt (x1 = 3600, letzter Punkt 3540) liegt keine Messung mehr.
  chart.dispatchEvent(new w.MouseEvent('pointermove',{bubbles:true,clientX:4}));
  assert.match(tip.textContent,/keine Daten/);
  assert.equal(chart.querySelector('.chart-cursor circle').hasAttribute('hidden'),true);
});

test('bars lift on hover and name day, energy and recorded hours',async t=>{
  const day=86400*20000;
  const series={group:'day',power_resolution_seconds:900,power:[],energy:[0,1,2].map(i=>({ts:day+i*86400,import_kwh:2.5+i,import_s:86400,export_kwh:0,export_s:86400}))};
  const h=await harness({page:'history',series,settings:{setup_required:false}});t.after(()=>h.dom.window.close());const {w}=h;
  const chart=w.document.querySelector('#page-history .chart');
  await until(()=>!!chart.querySelector('.chart-tip'));
  chart.dispatchEvent(new w.MouseEvent('pointermove',{bubbles:true,clientX:100}));
  const tip=chart.querySelector('.chart-tip');
  assert.match(tip.textContent,/2,500 kWh/);
  assert.match(tip.textContent,/24,0 h erfasst/);
  assert.ok(chart.querySelector('rect.bar[data-i="0"]').classList.contains('hover'));
  chart.dispatchEvent(new w.MouseEvent('pointermove',{bubbles:true,clientX:700}));
  assert.equal(chart.querySelector('rect.bar.hover').dataset.i,'2');
  assert.match(tip.textContent,/4,500 kWh/);
});

function timelineSetup(){
  const now=Math.floor(Date.now()/1000), first=now-10*86400;
  return {now,first,options:{page:'history',settings:{setup_required:false},window:{start:now-86400,end:now-3600},
    timeline:{start:first,end:now,bin_seconds:3600,bins:Array.from({length:40},(_,i)=>({ts:first+i*21600,kwh:1+i%5,covered:1}))}}};
}

test('the timeline shows the whole record with the current window and moves it by dragging',async t=>{
  const {options,first,now}=timelineSetup();
  const h=await harness(options);t.after(()=>h.dom.window.close());const {w}=h;
  await until(()=>!w.document.getElementById('timeline').hidden);
  const svg=w.document.getElementById('timeline-svg');
  assert.equal(svg.querySelectorAll('.tl-bar').length,40);
  assert.ok(svg.querySelector('.tl-window')&&svg.querySelectorAll('.tl-handle').length===2);
  assert.match(w.document.getElementById('timeline-label').textContent,/–/);
  const scale=744/(now-first), xOf=ts=>8+(ts-first)*scale;
  const win=svg.querySelector('.tl-window'), left=Number(win.getAttribute('x')), right=left+Number(win.getAttribute('width'));
  // Fenster mit gedrückter Maustaste nach links (in die Vergangenheit) schieben.
  const middle=(left+right)/2;
  svg.dispatchEvent(new w.MouseEvent('pointerdown',{bubbles:true,clientX:middle,button:0}));
  svg.dispatchEvent(new w.MouseEvent('pointermove',{bubbles:true,clientX:middle-60}));
  svg.dispatchEvent(new w.MouseEvent('pointerup',{bubbles:true,clientX:middle-60}));
  await pause(320);
  const [call]=windowCalls(h).slice(-1);
  assert.ok(call,'Daten für das neue Fenster werden geladen');
  const shift=60/scale;
  assert.ok(Math.abs((Number(call.until)-Number(call.since))-(options.window.end-options.window.start))<90,'Länge bleibt');
  assert.ok(Math.abs(Number(call.since)-(options.window.start-shift))<900,'Fenster wurde verschoben');
  assert.equal(h.w.document.querySelector('#range-start').value.length,10);
});

test('dragging a window edge and the mouse wheel zoom the time axis',async t=>{
  const {options,now,first}=timelineSetup();
  const h=await harness(options);t.after(()=>h.dom.window.close());const {w}=h;
  await until(()=>!w.document.getElementById('timeline').hidden);
  const svg=w.document.getElementById('timeline-svg');
  const win=svg.querySelector('.tl-window'), left=Number(win.getAttribute('x'));
  svg.dispatchEvent(new w.MouseEvent('pointerdown',{bubbles:true,clientX:left,button:0}));
  svg.dispatchEvent(new w.MouseEvent('pointermove',{bubbles:true,clientX:left+40}));
  svg.dispatchEvent(new w.MouseEvent('pointerup',{bubbles:true,clientX:left+40}));
  await pause(320);
  let call=windowCalls(h).slice(-1)[0];
  assert.ok(Number(call.until)-Number(call.since)<options.window.end-options.window.start,'linker Rand nach innen: kleineres Fenster');
  assert.equal(Number(call.until),options.window.end);
  const span=Number(call.until)-Number(call.since);
  const before=windowCalls(h).length;
  const wheel=new w.WheelEvent('wheel',{bubbles:true,cancelable:true,deltaY:-200,clientX:left+60});
  svg.dispatchEvent(wheel);
  assert.equal(wheel.defaultPrevented,true,'Mausrad zoomt statt die Seite zu scrollen');
  await pause(320);
  assert.ok(windowCalls(h).length>before);
  call=windowCalls(h).slice(-1)[0];
  assert.ok(Number(call.until)-Number(call.since)<span,'Hineinzoomen verkleinert das Fenster');
  // Nie unter 5 Minuten, nie über den erfassten Zeitraum.
  for(let i=0;i<40;i++)svg.dispatchEvent(new w.WheelEvent('wheel',{bubbles:true,cancelable:true,deltaY:-400,clientX:left}));
  await pause(320);
  call=windowCalls(h).slice(-1)[0];
  assert.ok(Number(call.until)-Number(call.since)>=300);
  for(let i=0;i<60;i++)svg.dispatchEvent(new w.WheelEvent('wheel',{bubbles:true,cancelable:true,deltaY:400,clientX:left}));
  await pause(320);
  call=windowCalls(h).slice(-1)[0];
  assert.ok(Number(call.since)>=first-1&&Number(call.until??now)-Number(call.since)<=now-first+2);
  assert.equal(call.until,undefined,'Fenster bis zur Gegenwart folgt der Zeit');
});

test('clicking beside the window recentres it, buttons and keys zoom, "Alles" shows the whole record',async t=>{
  const {options,first,now}=timelineSetup();
  const h=await harness(options);t.after(()=>h.dom.window.close());const {w}=h;
  await until(()=>!w.document.getElementById('timeline').hidden);
  const svg=w.document.getElementById('timeline-svg');
  const scale=744/(now-first);
  svg.dispatchEvent(new w.MouseEvent('pointerdown',{bubbles:true,clientX:60,button:0}));
  svg.dispatchEvent(new w.MouseEvent('pointerup',{bubbles:true,clientX:60}));
  await pause(320);
  let call=windowCalls(h).slice(-1)[0];
  const centre=(Number(call.since)+Number(call.until))/2;
  assert.ok(Math.abs(centre-(first+(60-8)/scale))<1800,'Fenster sitzt dort, wo geklickt wurde');
  assert.ok(Math.abs((Number(call.until)-Number(call.since))-(options.window.end-options.window.start))<90,'Länge bleibt');
  const span=Number(call.until)-Number(call.since);
  w.document.getElementById('timeline-in').click();
  await pause(320);
  call=windowCalls(h).slice(-1)[0];
  assert.ok(Math.abs((Number(call.until)-Number(call.since))-span/2)<900);
  svg.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true,cancelable:true}));
  await pause(320);
  const moved=windowCalls(h).slice(-1)[0];
  assert.ok(Number(moved.since)>Number(call.since));
  w.document.getElementById('timeline-all').click();
  await pause(320);
  call=windowCalls(h).slice(-1)[0];
  assert.ok(Math.abs(Number(call.since)-first)<=1);
  assert.equal(call.until,undefined);
});

test('ctrl+wheel and dragging inside the chart zoom and pan the same window',async t=>{
  const {options}=timelineSetup();
  const h=await harness(options);t.after(()=>h.dom.window.close());const {w}=h;
  const chart=w.document.querySelector('#page-history .chart');
  await until(()=>!!chart.querySelector('.chart-tip')&&!w.document.getElementById('timeline').hidden);
  const plain=new w.WheelEvent('wheel',{bubbles:true,cancelable:true,deltaY:-100,clientX:300});
  chart.dispatchEvent(plain);
  assert.equal(plain.defaultPrevented,false,'normales Mausrad scrollt weiter die Seite');
  const zoom=new w.WheelEvent('wheel',{bubbles:true,cancelable:true,deltaY:-200,ctrlKey:true,clientX:300});
  chart.dispatchEvent(zoom);
  assert.equal(zoom.defaultPrevented,true);
  await pause(320);
  let call=windowCalls(h).slice(-1)[0];
  const span=Number(call.until)-Number(call.since);
  assert.ok(span<options.window.end-options.window.start);
  chart.dispatchEvent(new w.MouseEvent('pointerdown',{bubbles:true,clientX:300,button:0}));
  w.dispatchEvent(new w.MouseEvent('pointermove',{bubbles:true,clientX:340}));
  w.dispatchEvent(new w.MouseEvent('pointerup',{bubbles:true,clientX:340}));
  await pause(320);
  const dragged=windowCalls(h).slice(-1)[0];
  assert.ok(Number(dragged.since)<Number(call.since),'Ziehen nach rechts zeigt früher Liegendes');
  assert.ok(Math.abs((Number(dragged.until)-Number(dragged.since))-span)<90,'Länge bleibt');
});
