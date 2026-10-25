'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number = (value, decimals = 1) => value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toLocaleString('de-DE', {minimumFractionDigits:decimals,maximumFractionDigits:decimals});
const unit = (value, suffix, decimals = 1) => `${number(value, decimals)} ${suffix}`;
const dayString = date => new Intl.DateTimeFormat('sv-SE', {timeZone:'Europe/Berlin'}).format(date);
const today = () => dayString(new Date());
const shiftDay = (day, amount) => { const date = new Date(day + 'T12:00:00Z'); date.setUTCDate(date.getUTCDate() + amount); return date.toISOString().slice(0,10); };
const localTime = (ts, options = {}) => new Date(ts * 1000).toLocaleString('de-DE', {timeZone:'Europe/Berlin', ...options});
const localDate = ts => localTime(ts,{day:'2-digit',month:'2-digit',year:'numeric'});
const dateLabel = day => new Date(day + 'T12:00:00Z').toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit',year:'numeric',timeZone:'Europe/Berlin'});
let page = 'dashboard', settings = {}, live = {}, overview = null, requestVersion = 0, toastTimer;

async function api(path, method = 'GET', body) {
  const options = {method, headers:{'X-Kilowatch-Request':'1'}, credentials:'same-origin'};
  if (body !== undefined) { options.headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(body); }
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail;
    try { detail = (await response.json()).detail; } catch { detail = 'Anfrage fehlgeschlagen.'; }
    if (response.status === 401 && path !== '/api/login') showLogin();
    if (Array.isArray(detail)) detail = detail.map(item => `${item.loc?.slice(-1)[0] || 'Eingabe'}: ${item.msg}`).join('; ');
    throw new Error(String(detail || `HTTP ${response.status}`));
  }
  return response.json();
}

function toast(message, error = false) {
  const box = $('#toast'); box.textContent = message; box.classList.toggle('error',error); box.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => box.hidden = true, error ? 9000 : 4500);
}
function safely(callback) { return async event => { try { await callback(event); } catch (error) { toast(error.message,true); } }; }
function showLogin() { $('#application').hidden = true; $('#login').hidden = false; $('#login-form').hidden=false; $('#first-start-form').hidden=true; }
function empty(title = 'Noch keine Messwerte.', text = '') { return `<div class="empty"><span class="empty-icon">⌁</span><strong>${esc(title)}</strong>${text?`<span>${esc(text)}</span>`:''}</div>`; }
function panel(title, subtitle, content, extra = '') { return `<div class="panel"><div class="panel-header"><div><h2>${esc(title)}</h2>${subtitle?`<p>${esc(subtitle)}</p>`:''}</div>${extra}</div>${content}</div>`; }
function stat(label, value) { return `<div class="stat-line"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`; }
function metric(label, value, suffix, note, icon, highlight = false) { return `<div class="card metric-card${highlight ? ' highlight' : ''}"><div class="metric-label">${esc(label)}<span class="metric-icon">${icon}</span></div><div class="metric-value">${value}<small>${esc(suffix)}</small></div><div class="metric-note">${esc(note)}</div></div>`; }
function coverage(summary) { const percent = Math.min(100,Math.max(0,(summary?.coverage || 0)*100)); return `<div class="quality-row"><span>Datenabdeckung</span><div class="quality-track"><span style="width:${percent}%"></span></div><strong>${number(percent,1)} %</strong></div>`; }
function periodText() { return `${dateLabel($('#range-start').value)} – ${dateLabel($('#range-end').value)}`; }
function query() { return new URLSearchParams({start:$('#range-start').value,end:$('#range-end').value}).toString(); }
function totalNote(summary) { return summary.gap_count ? `${summary.gap_count} Lücke(n) · ${unit(summary.recovered_import_kwh,'kWh')} nur als Gesamtmenge bekannt` : `${number(summary.coverage*100,1)} % zeitlich erfasst`; }

function lineChart(data, field = 'power_w', label = 'W', xField = 'ts', options = {}) {
  data = data.filter(item => item[field] != null && Number.isFinite(item[field]));
  if (data.length < 2) return empty('Noch zu wenige Messpunkte.','Für diesen Zeitraum sind mindestens zwei Werte erforderlich.');
  const w = 760, h = 245, left = 47, right = 12, top = 15, bottom = 34;
  const x0 = options.start ?? data[0][xField], x1 = options.end ?? data[data.length-1][xField];
  const low = Math.min(0,...data.map(item => item[field])), high = Math.max(1,...data.map(item => item[field])) * 1.12;
  const X = val => left + (val-x0)/Math.max(1,x1-x0)*(w-left-right);
  const Y = val => top+(high-val)/Math.max(1,high-low)*(h-top-bottom);
  const times = data.slice(1).map((item,index)=>item[xField]-data[index][xField]).sort((a,b)=>a-b);
  const gapLimit = xField === 'ts' ? Math.max(120, (times[Math.floor(times.length/2)]||60)*2.5) : Infinity;
  const paths = []; let segment = [];
  data.forEach((item,index) => { if(index && item[xField]-data[index-1][xField]>gapLimit) { if(segment.length)paths.push(segment); segment=[]; } segment.push(item); });
  if(segment.length) paths.push(segment);
  let grid = '';
  for(let i=0;i<=4;i++) { const val = low+(high-low)*i/4, y = Y(val); grid += `<line class="grid-line" x1="${left}" x2="${w-right}" y1="${y}" y2="${y}"/><text x="${left-9}" y="${y+3}" text-anchor="end">${number(val,0)}</text>`; }
  let xLabels = '';
  for(let i=0;i<=5;i++) { const val=x0+(x1-x0)*i/5; const text=xField==='ts'?localTime(val,{hour:'2-digit',minute:'2-digit',...(x1-x0>86400?{day:'2-digit',month:'2-digit'}:{})}):`${number(val,0)} h`; xLabels+=`<text x="${X(val)}" y="${h-8}" text-anchor="${i===0?'start':i===5?'end':'middle'}">${esc(text)}</text>`; }
  const pathsSvg = paths.map(items=>{ const line=items.map((item,i)=>`${i?'L':'M'}${X(item[xField]).toFixed(1)},${Y(item[field]).toFixed(1)}`).join(' '); return `<path d="${line} L${X(items.at(-1)[xField]).toFixed(1)},${Y(0)} L${X(items[0][xField]).toFixed(1)},${Y(0)} Z" fill="url(#energy-fill)"/><path d="${line}" fill="none" stroke="#a8c445" stroke-width="2.3" stroke-linejoin="round"/>`; }).join('');
  const dots = data.filter((_,i)=>i%Math.max(1,Math.floor(data.length/350))===0).map(item=>`<circle cx="${X(item[xField]).toFixed(1)}" cy="${Y(item[field]).toFixed(1)}" r="4" fill="transparent"><title>${esc(xField==='ts'?localTime(item[xField]):unit(item[xField],'h'))} · ${esc(unit(item[field],label))}</title></circle>`).join('');
  return `<div class="chart"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)} im ausgewählten Zeitraum"><defs><linearGradient id="energy-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#d3eb65" stop-opacity=".34"/><stop offset="100%" stop-color="#d3eb65" stop-opacity=".01"/></linearGradient></defs>${grid}${pathsSvg}${dots}${xLabels}<text x="${left}" y="7">${esc(label)}</text></svg></div>`;
}

function barChart(data, field = 'import_kwh', label = 'kWh') {
  if(!data.length) return empty();
  const w=760,h=245,left=42,top=18,bottom=36,right=9;
  const max=Math.max(.1,...data.map(item=>item[field]||0))*1.15;
  // Kleine Abstände zeigen fehlende Zeitfenster; keine nullgefüllten Balken.
  const width=(w-left-right)/Math.max(1,data.length), skip=Math.max(1,Math.ceil(data.length/9));
  let grid='';
  for(let i=0;i<=4;i++){const y=h-bottom-(h-top-bottom)*i/4;grid+=`<line class="grid-line" x1="${left}" x2="${w-right}" y1="${y}" y2="${y}"/><text x="${left-8}" y="${y+3}" text-anchor="end">${number(max*i/4,1)}</text>`;}
  const bars=data.map((item,index)=>{const value=item[field],x=left+index*width,y=h-bottom-(value||0)/max*(h-top-bottom);return `${value==null?'':`<rect x="${x+width*.18}" y="${y}" width="${Math.max(1,width*.64)}" height="${h-bottom-y}" rx="${Math.min(4,width*.2)}" fill="#bfd559"><title>${esc(localDate(item.ts))} · ${esc(unit(value,label,3))} · ${number((item.import_s||0)/3600,1)} h erfasst</title></rect>`}${index%skip===0?`<text x="${x+width/2}" y="${h-9}" text-anchor="middle">${esc(localTime(item.ts,{day:'2-digit',month:'2-digit',...(data.length<20?{}:{})}))}</text>`:''}`;}).join('');
  return `<div class="chart"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Verbrauch in ${label}">${grid}${bars}<text x="${left}" y="8">${label}</text></svg></div>`;
}

function powerPanel(data) {
  const isShort = data.series.group === 'quarter';
  const chart = isShort ? lineChart(data.series.power,'power_w','W','ts',{start:data.summary.start,end:data.summary.end}) : barChart(data.series.energy);
  return panel(isShort?'So fließt dein Strom.':'Dein Verbrauch im Verlauf.',isShort?'Mittlere Netzleistung je Zeitabschnitt · positive Werte = Bezug':'Verbrauch aus den Zählerständen · zeitlich zugeordnete Energie',chart+`<div class="chart-note"><span>${isShort?'Leere Stellen zeigen fehlende Messdaten.':'Nicht zeitlich zuordenbare Lückenenergie ist separat ausgewiesen.'}</span><span>${isShort?'ZEIT':'DATUM'}</span></div>`,`<div class="legend"><span><i></i>${isShort?'Netzleistung':'Netzbezug'}</span></div>`);
}

function updateLiveParts() {
  const state=live.collector?.state, valid=live.reading&&!live.stale;
  const names={online:'Bridge verbunden',demo:'Demo aktiv',stale:'Daten veraltet',error:'Verbindung prüfen',setup:'Einrichtung offen',paused:'Erfassung pausiert',starting:'Erfassung startet'};
  $('#status-label').textContent=names[state]||'Verbinde …';
  $('#status-dot').className='status-dot'+(['error'].includes(state)?' error':!['online','demo'].includes(state)?' warning':'');
  $('#demo-badge').hidden=!settings.demo;
  const alert=$('#connection-alert');
  const warning=!valid && state!=='demo';
  alert.hidden=!warning;
  if(warning) alert.textContent=live.collector?.message||'Noch keine gültigen Messdaten. Bridge unter Einstellungen verbinden.';
  const powerNode=$('#live-power'); if(powerNode)powerNode.textContent=number(valid?live.reading.power_w:null,0);
  const ageNode=$('#live-age'); if(ageNode)ageNode.textContent=live.reading?`Letzte Messung vor ${number(live.age_seconds,0)} s`:'Noch keine Messung';
}

function renderDashboard(data) {
  const s=data.summary,p=data.previous;
  let comparison='Noch keine Vergleichsdaten';
  if(s.import_kwh!=null&&p?.import_kwh>0&&s.coverage>.98&&p.coverage>.98)comparison=`${number((s.import_kwh/p.import_kwh-1)*100,1)} % zur Vorperiode`;
  else if(p)comparison='Vergleich erst bei guter Datenabdeckung';
  const valid=live.reading&&!live.stale;
  const cards=`<div class="cards">${metric('Aktuell zu Hause',`<span id="live-power">${number(valid?live.reading.power_w:null,0)}</span>`,'W','Lokale Netzleistung','↯',true)}${metric('Netzbezug',number(s.import_kwh,2),'kWh',comparison,'↗')}${metric('Erfasste Kosten',number(s.known_cost_eur,2),'€',s.cost_complete?'Inklusive anteiligem Grundpreis':s.tariff_missing?'Tarif fehlt oder Preisimport unvollständig':'Teilbetrag · Datenabdeckung beachten','€')}${metric('Leistungsspitze',number(s.peak_w==null?null:s.peak_w/1000,2),'kW','Höchste erfasste Momentanleistung','⌁')}</div>`;
  const reading=live.reading;
  const flow=`<div class="flow"><div class="flow-end"><div class="flow-icon">♧</div><small>STROMNETZ</small></div><div class="flow-line"></div><div class="flow-end"><div class="flow-icon">⌂</div><small>ZU HAUSE</small></div></div><div class="stats-list">${stat('Bezug im Zeitraum',unit(s.import_kwh,'kWh',2))}${stat('Einspeisung',unit(s.export_kwh,'kWh',2))}${stat('Bezugszähler',unit(reading?.import_kwh,'kWh',3))}${stat('Einspeisezähler',unit(reading?.export_kwh,'kWh',3))}</div><div class="divider"></div>${coverage(s)}<p id="live-age" class="copy-footnote">${reading?`Letzte Messung vor ${number(live.age_seconds,0)} s`:'Noch keine Messung'}</p>`;
  const quality=panel('Datenqualität','',`<div class="insight"><span class="insight-icon">◉</span><div><h3>${s.coverage>.98?'Dein Zeitraum ist gut erfasst.':'Deine Historie entsteht ab jetzt.'}</h3><p>${esc(totalNote(s))}. ${s.crossing_gaps?'Eine Lücke reicht über die Zeitraumgrenze. Ihre Energiemenge bleibt außerhalb dieser Summe.':''}</p></div></div>`);
  const compare=panel('Vorperiode','',p?`<div class="stats-list">${stat('Ausgewählter Zeitraum',unit(s.import_kwh,'kWh',2))}${stat('Vorperiode',unit(p.import_kwh,'kWh',2))}${stat('Abdeckung der Vorperiode',unit(p.coverage*100,'%',1))}${stat('Vergleich bis',localTime(p.end,{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}))}</div>`:empty('Vergleich noch nicht verfügbar.'));
  $('#page-dashboard').innerHTML=cards+`<div class="grid-main"><div>${powerPanel(data)}${quality}</div><div>${panel('Bezug und Einspeisung','',flow)}${compare}</div></div>`;
}

function renderHistory(data) {
  const rows=data.series.energy;
  const table=rows.length?`<div class="table-wrap"><table><thead><tr><th>Zeitpunkt / Zeitraum</th><th>Bezug kWh</th><th>Einspeisung kWh</th><th>Erfasster Bezug</th><th>Spitze W</th></tr></thead><tbody>${rows.map(row=>`<tr><td>${esc(data.series.group==='quarter'?localTime(row.ts,{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',timeZoneName:'short'}):localDate(row.ts))}</td><td>${number(row.import_kwh,3)}</td><td>${number(row.export_kwh,3)}</td><td>${unit(row.import_s/3600,'h',2)}</td><td>${number(row.peak_w,0)}</td></tr>`).join('')}</tbody></table></div>`:empty();
  const gaps=data.gaps.length?`<div class="table-wrap"><table><thead><tr><th>Beginn</th><th>Ende</th><th>Bezug gesamt</th><th>Grund</th></tr></thead><tbody>${data.gaps.slice(0,100).map(g=>`<tr><td>${esc(localTime(g.start))}</td><td>${esc(localTime(g.end))}</td><td>${unit(g.import_kwh,'kWh',3)}</td><td>${esc(g.reason)}</td></tr>`).join('')}</tbody></table></div><p class="copy-footnote">Max. 100 angezeigt; vollständig unter Export → Lücken.</p>`:'<p class="muted">Keine Messlücken in diesem Zeitraum.</p>';
  $('#page-history').innerHTML=powerPanel(data)+panel('Verbrauch im Detail.',periodText(),table)+panel('Messlücken','',gaps);
}

function heatmap(cells) {
  if(!cells.length)return empty('Dein Tagesmuster wird hier sichtbar.');
  const days=[...new Set(cells.map(c=>c.day))].slice(-62), lookup=new Map(cells.map(c=>[`${c.day}:${c.hour}`,c]));
  const maximum=Math.max(.01,...cells.map(c=>c.seconds?c.kwh*3600/c.seconds:0));
  let html='<div class="heat-scroll"><div class="heat-grid"><span></span>'+Array.from({length:24},(_,i)=>`<span class="heat-label">${String(i).padStart(2,'0')}</span>`).join('');
  for(const day of days){html+=`<span class="heat-label">${esc(dateLabel(day).slice(0,5))}</span>`;for(let h=0;h<24;h++){const cell=lookup.get(`${day}:${h}`), strength=cell?.seconds?Math.min(1,cell.kwh*3600/cell.seconds/maximum):null; const color=strength==null?'#eff2eb':`hsl(${83-strength*6} ${35+strength*20}% ${92-strength*54}%)`;html+=`<div class="heat-cell" style="background:${color}" title="${esc(dateLabel(day))} ${String(h).padStart(2,'0')}:00 · ${cell?unit(cell.kwh,'kWh',3)+' / '+unit(cell.seconds/3600,'h',2)+' erfasst':'keine Daten'}"></div>`;}}
  return html+'</div></div><div class="heat-key">Wenig '+['#eff4dd','#dce9ab','#b9d164','#86aa31'].map(c=>`<i style="background:${c}"></i>`).join('')+' Viel · Farbe: Verbrauch je erfasster Stunde · letzte 62 Tage</div>';
}

function profileChart(rows) {
  const weekday=Array.from({length:24},(_,hour)=>({hours:hour,power_w:rows.find(r=>r.type==='weekday'&&r.hour===hour)?.average_kw*1000})).filter(r=>Number.isFinite(r.power_w));
  const weekend=Array.from({length:24},(_,hour)=>({hours:hour,power_w:rows.find(r=>r.type==='weekend'&&r.hour===hour)?.average_kw*1000})).filter(r=>Number.isFinite(r.power_w));
  const table=`<div class="table-wrap"><table><thead><tr><th>Stunde</th><th>Mo–Fr Ø W</th><th>Sa–So Ø W</th></tr></thead><tbody>${Array.from({length:24},(_,h)=>`<tr><td>${String(h).padStart(2,'0')}:00</td><td>${number(weekday.find(r=>r.hours===h)?.power_w,0)}</td><td>${number(weekend.find(r=>r.hours===h)?.power_w,0)}</td></tr>`).join('')}</tbody></table></div>`;
  return table;
}

function renderAnalysis(data, base) {
  const forecast=data.forecast;
  const cards=`<div class="cards">${metric('Nachtgrundlast (P10)',number(data.baseline_w,0),'W',`${data.night_quarters} ausreichend erfasste Nachtintervalle`,'☾',true)}${metric('Hohe Last',number(base.summary.high_load_hours,2),'h',`Intervallmittel ≥ ${unit(settings.high_load_w,'W',0)}`,'↗')}${metric('Zeitlich zugeordnet',number(base.summary.allocated_import_kwh,2),'kWh','Aus Zählerstandsdifferenzen oder Schätzung','▥')}${metric('Monatsprognose',number(forecast.available?forecast.expected_kwh:null,0),'kWh',forecast.available?`${number(forecast.low_kwh,0)} – ${number(forecast.high_kwh,0)} kWh Band`:'Noch keine belastbare Datenbasis','⌁')}</div>`;
  const forecastText=forecast.available?forecast.method:forecast.reason;
  const anomaly=data.anomalies.map(a=>`<div class="insight"><span class="insight-icon">◉</span><div><h3>${esc(a.title)}</h3><p>${esc(a.text)}</p></div></div>`).join('');
  $('#page-analysis').innerHTML=cards+panel('Stundenmuster','',heatmap(data.heatmap))+`<div class="grid-two"><div>${panel('Lastdauerlinie','',lineChart(data.duration_curve,'power_w','W','hours'))}${panel('Auffälligkeiten','',anomaly)}</div><div>${panel('Tagesverlauf','',profileChart(data.profile))}</div></div>`+panel('Prognose','',`<p class="muted">${esc(forecastText)}</p>`);
  mountAnalysisInsights().catch(error=>toast(error.message,true));
}

function renderCosts(data, base) {
  const s=base.summary;
  const tariffRows=data.tariffs.map(t=>`<tr><td>${esc(dateLabel(t.start_date))}</td><td>${esc(t.name)}</td><td>${t.mode==='fixed'?'1 Tarifstufe':t.mode==='dual'?'2 Tarifstufen (HT/NT)':'Variabel / CSV'}</td><td>${tariffRateLabel(t)}</td><td>${unit(t.base_month,'€',2)}</td><td><button class="secondary" data-edit-tariff="${esc(t.start_date)}">Bearbeiten</button> <button class="danger-button" data-delete-tariff="${esc(t.start_date)}">Entfernen</button></td></tr>`).join('');
  const costDetails=`<div class="stats-list">${stat('Bepreiste Bezugsenergie',unit(s.energy_cost_eur,'€',2))}${stat('Anteilig bekannter Grundpreis',unit(s.base_cost_eur,'€',2))}${stat('Einspeiseerlös',unit(s.feedin_eur,'€',2))}${stat('Bekannter Gesamtbetrag',unit(s.known_cost_eur,'€',2))}${stat('Energiemenge ohne Preiszuordnung',unit(s.unpriced_kwh,'kWh',3))}</div><div class="divider"></div>${coverage(s)}${s.cost_complete?'':'<p class="copy-footnote">Betrag unvollständig: nicht gemessene oder nicht bepreiste Energie fehlt.</p>'}`;
  const form=`<form id="tariff-form"><div class="form-grid"><label>Gültig ab<input name="start_date" type="date" value="${today().slice(0,7)}-01" required></label><label>Tarifname<input name="name" maxlength="80" placeholder="Mein Stromtarif" required></label><label>Preisart<select name="mode"><option value="fixed">Festpreis</option><option value="dynamic">Dynamisch per CSV-Import</option></select></label><label>Arbeitspreis brutto (ct/kWh)<input name="ct_kwh" type="number" step=".001" min="-500" max="1000" required value="32"></label><label>Grundpreis brutto (€/Monat)<input name="base_month" type="number" step=".01" min="0" max="1000" required value="0"></label><label>Einspeisevergütung (ct/kWh)<input name="feedin_ct" type="number" step=".001" min="-500" max="1000" required value="0"></label></div><div class="form-actions"><button type="submit" class="primary">Tarif speichern</button></div></form>`;
  const csv=`<p class="muted"><code>start,end,eur_kwh</code> · Bruttopreise · Zeit mit UTC-Offset · Viertelstundenraster</p><div class="form-actions"><label class="secondary">CSV auswählen<input id="price-file" type="file" accept=".csv,text/csv" class="sr-only"></label><button class="danger-button" id="delete-prices">Alle Importpreise löschen</button></div><p class="copy-footnote">${data.prices.count} Intervalle gespeichert${data.prices.start!=null?' · '+esc(localDate(data.prices.start))+' – '+esc(localDate(data.prices.end)):''}.</p><pre class="system-pre">start,end,eur_kwh\n2026-10-01T00:00:00+02:00,2026-10-01T01:00:00+02:00,0.295</pre>`;
  $('#page-costs').innerHTML=`<div class="grid-two"><div>${panel('Was dein Strom kostet.',periodText(),costDetails)}<div id="budget-slot"></div></div><div>${panel('Tarif hinterlegen','',form)}</div></div>`+panel('Tarifhistorie','',tariffRows?`<div class="table-wrap"><table><thead><tr><th>Ab</th><th>Tarif</th><th>Art</th><th>Preis/kWh</th><th>Grundpreis/Monat</th><th></th></tr></thead><tbody>${tariffRows}</tbody></table></div>`:empty('Noch kein Tarif hinterlegt.','Trage deinen Arbeitspreis und Grundpreis ein.'))+'<div id="simulation-slot"></div>'+panel('Dynamische Preise','',csv);
  $('#tariff-form').addEventListener('submit',safely(async event=>{event.preventDefault();const values=Object.fromEntries(new FormData(event.target));await api('/api/tariffs','PUT',{start_date:values.start_date,name:values.name,mode:values.mode,eur_kwh:values.mode==='dynamic'?0:Number(values.ct_kwh)/100,base_month:Number(values.base_month),feedin_eur_kwh:Number(values.feedin_ct)/100,...tariffExtraValues(values)});toast('Tarif gespeichert.');await loadPage();}));
  $$('[data-delete-tariff]').forEach(button=>button.addEventListener('click',safely(async()=>{await api('/api/tariffs/'+button.dataset.deleteTariff,'DELETE');toast('Tarif entfernt.');await loadPage();})));
  $('#price-file').addEventListener('change',safely(async event=>{const file=event.target.files[0];if(!file)return;if(file.size>1500000)throw new Error('CSV darf höchstens 1,5 MB groß sein.');const result=await api('/api/prices/import','POST',{csv:await file.text()});toast(`${result.count} Preise importiert.`);await loadPage();}));
  $('#delete-prices').addEventListener('click',safely(async()=>{await api('/api/prices','DELETE');toast('Importpreise entfernt.');await loadPage();}));
  mountTariffOptions(data);
  mountCostInsights(data, base);
}

function renderEvents(events) {
  const items=events.map(e=>`<article class="event-item"><h3>${esc(e.title)}</h3><small>${esc(localDate(e.start))} – ${esc(localDate(e.end-1))}</small><p>${esc(e.note)}</p><div class="button-row"><button class="secondary" data-compare-event="${e.id}">Verbrauch vergleichen</button><button class="danger-button" data-delete-event="${e.id}">Entfernen</button></div><div id="event-result-${e.id}" hidden class="inline-result"></div></article>`).join('');
  const form=`<form id="event-form"><div class="form-grid"><label class="full">Ereignis<input name="title" maxlength="120" placeholder="Zum Beispiel: neuer Kühlschrank" required></label><label>Von<input name="start_date" type="date" value="${today()}" required></label><label>Bis einschließlich<input name="end_date" type="date" value="${today()}" required></label><label class="full">Notiz<textarea name="note" rows="4" maxlength="2000" placeholder="Was hat sich verändert?"></textarea></label></div><div class="form-actions"><button class="primary" type="submit">Ereignis markieren</button></div></form>`;
  $('#page-events').innerHTML=`<div class="grid-two"><div>${panel('Ereignisse','',items||empty('Noch keine Ereignisse.','Deine eigenen Markierungen erscheinen hier.'))}</div><div>${panel('Ereignis hinzufügen','',form)}</div></div>`;
  $('#event-form').addEventListener('submit',safely(async e=>{e.preventDefault();await api('/api/events','POST',Object.fromEntries(new FormData(e.target)));toast('Ereignis gespeichert.');await loadPage();}));
  $$('[data-delete-event]').forEach(b=>b.addEventListener('click',safely(async()=>{await api('/api/events/'+b.dataset.deleteEvent,'DELETE');await loadPage();})));
  $$('[data-compare-event]').forEach(b=>b.addEventListener('click',safely(async()=>{const result=await api(`/api/events/${b.dataset.compareEvent}/comparison`);const node=$('#event-result-'+b.dataset.compareEvent);node.hidden=false;node.textContent=`Im Ereignis: ${unit(result.during.import_kwh,'kWh',2)} (${unit(result.during.coverage*100,'%',1)} erfasst)\nDavor: ${unit(result.before.import_kwh,'kWh',2)} (${unit(result.before.coverage*100,'%',1)} erfasst)\nEin laufendes Ereignis ist kürzer als seine volle Vorperiode. Der Vergleich zeigt Zusammenhänge, keine nachgewiesene Ursache.`;})));
}

function renderReports(data) {
  const s=data.summary;
  const rows=data.series.energy.map(r=>`<tr><td>${esc(localTime(r.ts,{day:'2-digit',month:'2-digit',year:'numeric',...(data.series.group==='quarter'?{hour:'2-digit',minute:'2-digit',timeZoneName:'short'}:{})}))}</td><td>${number(r.import_kwh,3)}</td><td>${number(r.export_kwh,3)}</td><td>${unit(r.import_s/3600,'h',2)}</td></tr>`).join('');
  const content=`<div class="report-heading"><h1>Kilowatch · Energiebericht</h1><p>${esc(settings.name)} · ${esc(periodText())}</p></div><div class="report-actions button-row"><button class="primary" id="print-report">Drucken / als PDF speichern</button><button class="secondary" id="month-report">Aktueller Monat</button><button class="secondary" id="year-report">Aktuelles Jahr</button></div><div class="report-summary"><p><strong>${esc(periodText())}</strong> · Erstellt ${esc(localTime(Date.now()/1000))}</p><p>Netzbezug: <strong>${unit(s.import_kwh,'kWh',3)}</strong> · Einspeisung: <strong>${unit(s.export_kwh,'kWh',3)}</strong></p><p>Bekannte Kosten: <strong>${unit(s.known_cost_eur,'€',2)}</strong> · ${s.cost_complete?'Nahezu vollständiger Zeitraum':'Unvollständiger Betrag'} · Datenabdeckung: ${unit(s.coverage*100,'%',2)}</p><p>Lückenenergie im Bezug: ${unit(s.recovered_import_kwh,'kWh',3)} · ${s.gap_count} Messlücke(n) · ${s.crossing_gaps} über die Zeitraumgrenzen</p></div>${rows?`<div class="table-wrap"><table><thead><tr><th>Zeitraum</th><th>Bezug kWh</th><th>Einspeisung kWh</th><th>Erfasster Bezug</th></tr></thead><tbody>${rows}</tbody></table></div>`:empty()}<p class="copy-footnote">Geschätzter Bezug aus Leistungsintegration: ${unit(s.estimated_import_kwh,'kWh',3)}</p>`;
  const exports=`<div class="form-grid"><label>Datentyp<select id="export-kind"><option value="quarters">Viertelstunden · dauerhaft</option><option value="minutes">Minutenwerte · innerhalb Aufbewahrung</option><option value="samples">Einzelmessungen · innerhalb Aufbewahrung</option><option value="gaps">Messlücken · separat</option></select></label><label>Format<select id="export-format"><option value="csv">CSV (Semikolon / UTF-8)</option><option value="json">JSON</option></select></label></div><div class="form-actions"><button class="primary" id="export-data">Datei herunterladen</button><a href="/api/backup" class="secondary" download>Datenbank sichern</a></div><p class="copy-footnote">Max. 100.000 Zeilen pro Datei.</p>`;
  $('#page-reports').innerHTML=panel('Dein Energiebericht.',periodText(),content)+`<div class="report-actions">${panel('Export','',exports)}</div>`;
  $('#print-report').addEventListener('click',()=>window.print());
  $('#month-report').addEventListener('click',()=>applyRange('month'));$('#year-report').addEventListener('click',()=>applyRange('year'));
  $('#export-data').addEventListener('click',()=>{window.location.href=`/api/export?${query()}&kind=${$('#export-kind').value}&format=${$('#export-format').value}`;});
}

function renderSettings() { renderSettingsV11(); }

function renderSystem(data) {
  const d=data.bridge;
  const info=`<div class="stats-list">${stat('Status',data.collector.message||'—')}${stat('Funkpegel Zähler → Bridge',unit(d.rssi_dbm,'dBm',1))}${stat('Spannung am Lesekopf',unit(d.battery_v,'V',2))}${stat('Temperatur',unit(d.temperature_c,'°C',1))}${stat('Paketempfang',unit(d.delivery_percent,'%',1))}${stat('Ungültige Telegramme laut Bridge',number(d.invalid_readings,0))}${stat('Firmware',d.firmware?Object.entries(d.firmware).map(([key,val])=>`${key}: ${val}`).join(' / '):'—')}${stat('Datenbank inklusive WAL',unit(data.database_bytes/1024/1024,'MB',1))}${stat('Einzelmessungen',number(data.counts.samples,0))}${stat('Viertelstunden',number(data.counts.quarters,0))}</div>`;
  const issues=data.issues.length?`<div class="table-wrap"><table><thead><tr><th>Zeit</th><th>Art</th><th>Hinweis</th></tr></thead><tbody>${data.issues.map(i=>`<tr><td>${esc(localTime(i.ts))}</td><td>${esc(i.code)}</td><td>${esc(i.message)}</td></tr>`).join('')}</tbody></table></div>`:'<p class="muted">Keine gespeicherten Erfassungsfehler.</p>';
  const obis=Object.entries(live.obis||{}).map(([key,val])=>`<tr><td>${esc(key)}</td><td>${esc(val.value)}</td><td>${esc(val.unit)}</td></tr>`).join('');
  $('#page-system').innerHTML=`<div class="grid-two"><div>${panel('Verbindung & Empfang','',info)}</div><div>${panel('Sicherungen','',`<p class="muted">${data.backups.length?data.backups.map(esc).join('<br>'):'Noch keine automatische Sicherung.'}</p><div class="form-actions"><a class="primary" href="/api/backup" download>Jetzt konsistent sichern</a></div>`)}${panel('Register','',obis?`<div class="table-wrap"><table><thead><tr><th>OBIS</th><th>Wert</th><th>Einheit</th></tr></thead><tbody>${obis}</tbody></table></div>`:empty())}</div></div>`+panel('Erfassungsprotokoll','',issues);
  mountUpdates().catch(error=>toast(error.message,true));
}

const pageText={
  dashboard:['ÜBERSICHT','Übersicht'],
  history:['VERLAUF','Verlauf'],
  analysis:['ANALYSEN','Analysen'],
  costs:['KOSTEN & TARIFE','Kosten & Tarife'],
  notifications:['BENACHRICHTIGUNGEN','Benachrichtigungen'],
  events:['EREIGNISSE','Ereignisse'],
  reports:['BERICHTE & EXPORT','Berichte & Export'],
  settings:['EINSTELLUNGEN','Einstellungen'],
  system:['SYSTEM & DATENQUALITÄT','System & Datenqualität']
};

async function loadPage() {
  const version=++requestVersion, selected=page;
  const target=$('#page-'+selected);target.classList.add('loading');
  try {
    const q=query();
    if(['dashboard','history','analysis','costs','reports'].includes(selected)) {
      const requests=[api('/api/overview?'+q)];
      if(selected==='analysis')requests.push(api('/api/analysis?'+q));
      if(selected==='costs')requests.push(api('/api/tariffs'));
      const result=await Promise.all(requests);if(version!==requestVersion)return;overview=result[0];
      if(selected==='dashboard')renderDashboard(overview);
      if(selected==='history')renderHistory(overview);
      if(selected==='analysis')renderAnalysis(result[1],overview);
      if(selected==='costs')renderCosts(result[1],overview);
      if(selected==='reports')renderReports(overview);
    } else if(selected==='events'){const result=await api('/api/events');if(version!==requestVersion)return;renderEvents(result);}
    else if(selected==='notifications'){const result=await api('/api/notifications');if(version!==requestVersion)return;renderNotifications(result);}
    else if(selected==='settings'){settings=await api('/api/settings');if(version!==requestVersion)return;renderSettings();}
    else if(selected==='system'){const result=await api('/api/diagnostics');if(version!==requestVersion)return;renderSystem(result);}
    updateLiveParts();
  } catch(error) { if(version===requestVersion)toast(error.message,true); }
  finally {target.classList.remove('loading');}
}

async function navigate(value, updateHash=true) {
  if(!pageText[value])value='dashboard';page=value;
  $$('.page').forEach(section=>section.hidden=section.id!=='page-'+page);
  $$('[data-page]').forEach(button=>button.classList.toggle('active',button.dataset.page===page));
  const text=pageText[page];$('#breadcrumb').textContent=text[0];$('#page-title').textContent=text[1];
  $('#range-bar').hidden=['settings','system','events','notifications'].includes(page);
  $('.sidebar').classList.remove('open');
  if(updateHash)history.replaceState(null,'','#'+page);
  await loadPage();
}

async function applyRange(value) {
  const now=today();let start=now,end=now;
  if(value==='yesterday')start=end=shiftDay(now,-1);
  if(value==='week')start=shiftDay(now,-6);
  if(value==='month')start=now.slice(0,7)+'-01';
  if(value==='year')start=now.slice(0,4)+'-01-01';
  $('#range-start').value=start;$('#range-end').value=end;
  $$('[data-range]').forEach(button=>button.classList.toggle('selected',button.dataset.range===value));
  await loadPage();
}

async function start() {
  const setupState=await api('/api/setup/status');
  if(setupState.needs_setup){renderInitialSetup();return;}
  settings=await api('/api/settings');live=await api('/api/live');
  $('#login').hidden=true;$('#application').hidden=false;$('#home-name').textContent=settings.name;$('#version').textContent=settings.version;
  $('#today-label').textContent=new Date().toLocaleDateString('de-DE',{weekday:'short',day:'numeric',month:'long',year:'numeric',timeZone:'Europe/Berlin'});
  if(!$('#range-start').value){$('#range-start').value=today();$('#range-end').value=today();}
  $('#range-end').max=today();$('#range-start').max=today();
  let initial=location.hash.slice(1)||'dashboard';if(settings.setup_required&&!settings.demo)initial='settings';
  await navigate(initial);updateLiveParts();
}

$('#first-start-form').addEventListener('submit',async event=>{event.preventDefault();$('#setup-error').textContent='';try{const data=Object.fromEntries(new FormData(event.target));if(data.password!==data.confirmation)throw new Error('Passwörter stimmen nicht überein.');delete data.confirmation;await api('/api/setup','POST',data);await api('/api/login','POST',{password:data.password});event.target.reset();$('#first-start-form').hidden=true;$('#login-form').hidden=false;await start();}catch(error){$('#setup-error').textContent=error.message;}});
$('#login-form').addEventListener('submit',async event=>{event.preventDefault();$('#login-error').textContent='';try{await api('/api/login','POST',{password:$('#login-password').value});$('#login-password').value='';await start();}catch(error){$('#login-error').textContent=error.message;}});
$('#logout').addEventListener('click',safely(async()=>{await api('/api/logout','POST');showLogin();}));
$$('[data-page]').forEach(button=>button.addEventListener('click',()=>navigate(button.dataset.page)));
$$('[data-range]').forEach(button=>button.addEventListener('click',()=>applyRange(button.dataset.range)));
$('#range-form').addEventListener('submit',event=>{event.preventDefault();if($('#range-end').value<$('#range-start').value){toast('Das Ende liegt vor dem Beginn.',true);return;}$$('[data-range]').forEach(button=>button.classList.remove('selected'));loadPage();});
$('#mobile-menu').addEventListener('click',()=>$('.sidebar').classList.toggle('open'));
window.addEventListener('hashchange',()=>navigate(location.hash.slice(1),false));
setInterval(async()=>{if($('#application').hidden||document.hidden)return;try{live=await api('/api/live');updateLiveParts();}catch(error){if(!$('#application').hidden)toast(error.message,true);}},5000);
setInterval(()=>{if(!$('#application').hidden&&!document.hidden&&['dashboard','history'].includes(page))loadPage();},60000);
start().catch(error=>{showLogin();if(error.message!=='Bitte anmelden.')$('#login-error').textContent=error.message;});
