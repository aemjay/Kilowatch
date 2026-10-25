'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number = (value, decimals = 1) => value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toLocaleString(LOCALE, {minimumFractionDigits:decimals,maximumFractionDigits:decimals});
const unit = (value, suffix, decimals = 1) => `${number(value, decimals)} ${localCurrency(suffix)}`;
const dayString = date => new Intl.DateTimeFormat('sv-SE', {timeZone:'Europe/Berlin'}).format(date);
const today = () => dayString(new Date());
const shiftDay = (day, amount) => { const date = new Date(day + 'T12:00:00Z'); date.setUTCDate(date.getUTCDate() + amount); return date.toISOString().slice(0,10); };
const localTime = (ts, options = {}) => new Date(ts * 1000).toLocaleString(LOCALE, {timeZone:'Europe/Berlin', ...options});
const localDate = ts => localTime(ts,{day:'2-digit',month:'2-digit',year:'numeric'});
const dateLabel = day => new Date(day + 'T12:00:00Z').toLocaleDateString(LOCALE,{day:'2-digit',month:'2-digit',year:'numeric',timeZone:'Europe/Berlin'});
let page = 'dashboard', settings = {}, live = {}, overview = null, requestVersion = 0, toastTimer;

async function api(path, method = 'GET', body) {
  const options = {method, headers:{'X-Kilowatch-Request':'1','X-Kilowatch-Language':LANGUAGE}, credentials:'same-origin'};
  if (body !== undefined) { options.headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(body); }
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail;
    try { detail = (await response.json()).detail; } catch { detail = t('Anfrage fehlgeschlagen.'); }
    if (response.status === 401 && path !== '/api/login') showLogin();
    if (Array.isArray(detail)) detail = detail.map(item => `${item.loc?.slice(-1)[0] || t('Eingabe')}: ${t(String(item.msg).replace(/^Value error, /,''))}`).join('; ');
    const error = new Error(String(detail || `HTTP ${response.status}`)); error.status = response.status;
    throw error;
  }
  return response.json();
}

function toast(message, error = false) {
  const box = $('#toast'); box.textContent = message; box.classList.toggle('error',error); box.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => box.hidden = true, error ? 9000 : 4500);
}
function safely(callback) { return async event => { try { await callback(event); } catch (error) { toast(error.message,true); } }; }
function showLogin() { $('#application').hidden = true; $('#login').hidden = false; $('#login-form').hidden=false; $('#first-start-form').hidden=true; }
function empty(title = t('Noch keine Messwerte.'), text = '') { return `<div class="empty"><span class="empty-icon">⌁</span><strong>${esc(title)}</strong>${text?`<span>${esc(text)}</span>`:''}</div>`; }
function panel(title, subtitle, content, extra = '') { return `<div class="panel"><div class="panel-header"><div><h2>${esc(title)}</h2>${subtitle?`<p>${esc(subtitle)}</p>`:''}</div>${extra}</div>${content}</div>`; }
function stat(label, value) { return `<div class="stat-line"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`; }
function metric(label, value, suffix, note, icon, highlight = false) { return `<div class="card metric-card${highlight ? ' highlight' : ''}"><div class="metric-label">${esc(label)}<span class="metric-icon">${icon}</span></div><div class="metric-value">${value}<small>${esc(suffix)}</small></div><div class="metric-note">${esc(note)}</div></div>`; }
function coverage(summary) { const percent = Math.min(100,Math.max(0,(summary?.coverage || 0)*100)); return `<div class="quality-row"><span>${t('Datenabdeckung')}</span><div class="quality-track"><span style="width:${percent}%"></span></div><strong>${number(percent,1)} %</strong></div>`; }
// Stundenansicht (letzte 1 oder 6 Stunden) oder Kalendertage aus den Datumsfeldern.
let rangeHours=null, lastPageRefresh=0;
function datesText() { return `${dateLabel($('#range-start').value)} – ${dateLabel($('#range-end').value)}`; }
function periodText() { return rangeHours ? t('Letzte {count} Std.',{count:rangeHours}) : datesText(); }
function query() { return new URLSearchParams(rangeHours?{hours:rangeHours}:{start:$('#range-start').value,end:$('#range-end').value}).toString(); }
function totalNote(summary) { return summary.gap_count ? `${t('{count} Lücke(n)',{count:summary.gap_count})} · ${t('{value} nur als Gesamtmenge bekannt',{value:unit(summary.recovered_import_kwh,'kWh')})}` : t('{percent} % zeitlich erfasst',{percent:number(summary.coverage*100,1)}); }

function lineChart(data, field = 'power_w', label = 'W', xField = 'ts', options = {}) {
  data = data.filter(item => item[field] != null && Number.isFinite(item[field]));
  if (data.length < 2) return empty(t('Noch zu wenige Messpunkte.'),t('Für diesen Zeitraum sind mindestens zwei Werte erforderlich.'));
  const w = 760, h = 245, left = 47, right = 12, top = 15, bottom = 34;
  const x0 = options.start ?? data[0][xField], x1 = options.end ?? data[data.length-1][xField];
  const overlays = options.overlays || [];
  const extra = overlays.flatMap(o => o.type === 'hline' ? [o.y] : o.type === 'band' ? o.points.flatMap(p => [p.low, p.high]) : o.points.map(p => p.y));
  const low = Math.min(0,...data.map(item => item[field]),...extra), high = Math.max(1,...data.map(item => item[field]),...extra) * 1.12;
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
  return `<div class="chart"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(t('{label} im ausgewählten Zeitraum',{label}))}"><defs><linearGradient id="energy-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#d3eb65" stop-opacity=".34"/><stop offset="100%" stop-color="#d3eb65" stop-opacity=".01"/></linearGradient></defs>${grid}${overlaySvg(overlays.filter(o=>o.type==='band'),X,Y,left,w-right)}${pathsSvg}${overlaySvg(overlays.filter(o=>o.type!=='band'),X,Y,left,w-right)}${dots}${xLabels}<text x="${left}" y="7">${esc(label)}</text></svg></div>`;
}

// Overlays zeichnen: Band (Min/Max), Linie (gleitender Ø) und waagerechte Referenzlinie mit Beschriftung.
function overlaySvg(overlays, X, Y, x0, x1) {
  return overlays.map(o => {
    if (o.type === 'hline') { const y=Y(o.y).toFixed(1); return `<line class="overlay-hline ${o.cls}" x1="${x0}" x2="${x1}" y1="${y}" y2="${y}"/><text class="overlay-label ${o.cls}" x="${x1-2}" y="${Number(y)-4}" text-anchor="end">${esc(o.label)}</text>`; }
    if (o.points.length < 2) return '';
    if (o.type === 'band') { const top=o.points.map((p,i)=>`${i?'L':'M'}${X(p.x).toFixed(1)},${Y(p.high).toFixed(1)}`).join(' '), bottom=o.points.slice().reverse().map(p=>`L${X(p.x).toFixed(1)},${Y(p.low).toFixed(1)}`).join(' '); return `<path class="overlay-band" d="${top} ${bottom} Z"/>`; }
    return `<path class="overlay-line ${o.cls}" d="${o.points.map((p,i)=>`${i?'L':'M'}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join(' ')}"/>`;
  }).join('');
}

function barChart(data, field = 'import_kwh', label = 'kWh', overlays = []) {
  if(!data.length) return empty();
  const w=760,h=245,left=42,top=18,bottom=36,right=9;
  const extra=overlays.flatMap(o=>o.type==='hline'?[o.y]:o.type==='band'?o.points.map(p=>p.high):o.points.map(p=>p.y));
  const max=Math.max(.1,...data.map(item=>item[field]||0),...extra)*1.15;
  // Kleine Abstände zeigen fehlende Zeitfenster; keine nullgefüllten Balken.
  const width=(w-left-right)/Math.max(1,data.length), skip=Math.max(1,Math.ceil(data.length/9));
  let grid='';
  for(let i=0;i<=4;i++){const y=h-bottom-(h-top-bottom)*i/4;grid+=`<line class="grid-line" x1="${left}" x2="${w-right}" y1="${y}" y2="${y}"/><text x="${left-8}" y="${y+3}" text-anchor="end">${number(max*i/4,1)}</text>`;}
  const bars=data.map((item,index)=>{const value=item[field],x=left+index*width,y=h-bottom-(value||0)/max*(h-top-bottom);return `${value==null?'':`<rect x="${x+width*.18}" y="${y}" width="${Math.max(1,width*.64)}" height="${h-bottom-y}" rx="${Math.min(4,width*.2)}" fill="#bfd559"><title>${esc(localDate(item.ts))} · ${esc(unit(value,label,3))} · ${esc(t('{hours} h erfasst',{hours:number((item.import_s||0)/3600,1)}))}</title></rect>`}${index%skip===0?`<text x="${x+width/2}" y="${h-9}" text-anchor="middle">${esc(localTime(item.ts,{day:'2-digit',month:'2-digit',...(data.length<20?{}:{})}))}</text>`:''}`;}).join('');
  // Overlay-Punkte tragen den Zeitstempel ihres Balkens; gezeichnet wird in der Balkenmitte.
  const index=new Map(data.map((item,i)=>[item.ts,i])), X=ts=>left+(index.get(ts)??0)*width+width/2, Y=value=>h-bottom-(value||0)/max*(h-top-bottom);
  return `<div class="chart"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(t('Verbrauch in {unit}',{unit:label}))}">${grid}${overlaySvg(overlays.filter(o=>o.type==='band'),X,Y,left,w-right)}${bars}${overlaySvg(overlays.filter(o=>o.type!=='band'),X,Y,left,w-right)}<text x="${left}" y="8">${label}</text></svg></div>`;
}

function powerPanel(data) {
  const isShort = data.series.group === 'quarter', resolution = data.series.power_resolution_seconds, raw = resolution === 0;
  const highLoad = {key:'highload', label:t('Grenze hohe Last {watts}',{watts:unit(settings.high_load_w,'W',0)}), value:settings.high_load_w};
  const spec = isShort
    ? {chart:'power', data:data.series.power, field:'power_w', xField:'ts', gapLimit:raw?120:resolution*2.5, ...powerWindow(resolution), references:[highLoad]}
    // Der laufende Tag oder Monat ist unvollständig und würde Ø und Trend nach unten ziehen.
    : {chart:'energy-'+data.series.group, data:Date.now()/1000-data.summary.end<300?data.series.energy.slice(0,-1):data.series.energy, field:'import_kwh', xField:'ts', byCount:true,
       window:data.series.group==='day'?7:3, windowLabel:data.series.group==='day'?t('7 Tage'):t('3 Monate'),
       references:data.series.group==='day'?[{key:'target', label:t('Tagesziel {value}',{value:unit(data.targets?.daily_kwh,'kWh',1)}), value:data.targets?.daily_kwh??null}]:[]};
  const overlays = buildOverlays(spec);
  const chart = overlayToggles(spec) + (isShort ? lineChart(data.series.power,'power_w','W','ts',{start:data.summary.start,end:data.summary.end,overlays}) : barChart(data.series.energy,'import_kwh','kWh',overlays));
  return panel(isShort?t('So fließt dein Strom.'):t('Dein Verbrauch im Verlauf.'),raw?t('Einzelne Messwerte im Abfrageintervall · positive Werte = Bezug'):isShort?t('Mittlere Netzleistung je Zeitabschnitt · positive Werte = Bezug'):t('Verbrauch aus den Zählerständen · zeitlich zugeordnete Energie'),chart+`<div class="chart-note"><span>${isShort?t('Leere Stellen zeigen fehlende Messdaten.'):t('Nicht zeitlich zuordenbare Lückenenergie ist separat ausgewiesen.')}</span><span>${isShort?t('ZEIT'):t('DATUM')}</span></div>`,`<div class="legend"><span><i></i>${isShort?t('Netzleistung'):t('Netzbezug')}</span></div>`);
}

function updateLiveParts() {
  const state=live.collector?.state, valid=live.reading&&!live.stale;
  const names={online:t('Bridge verbunden'),demo:t('Demo aktiv'),stale:t('Daten veraltet'),error:t('Verbindung prüfen'),setup:t('Einrichtung offen'),paused:t('Erfassung pausiert'),starting:t('Erfassung startet')};
  $('#status-label').textContent=names[state]||t('Verbinde …');
  $('#status-dot').className='status-dot'+(['error'].includes(state)?' error':!['online','demo'].includes(state)?' warning':'');
  $('#demo-badge').hidden=!settings.demo;
  const alert=$('#connection-alert');
  const warning=!valid && state!=='demo';
  alert.hidden=!warning;
  if(warning) alert.textContent=live.collector?.message?t(live.collector.message,live.collector.params||{}):t('Noch keine gültigen Messdaten. Bridge unter Einstellungen verbinden.');
  const powerNode=$('#live-power'); if(powerNode)powerNode.textContent=number(valid?live.reading.power_w:null,0);
  const ageNode=$('#live-age'); if(ageNode)ageNode.textContent=live.reading?t('Letzte Messung vor {seconds} s',{seconds:number(live.age_seconds,0)}):t('Noch keine Messung');
}

function renderDashboard(data) {
  const s=data.summary,p=data.previous;
  let comparison=t('Noch keine Vergleichsdaten');
  if(s.import_kwh!=null&&p?.import_kwh>0&&s.coverage>.98&&p.coverage>.98)comparison=t('{percent} % zur Vorperiode',{percent:number((s.import_kwh/p.import_kwh-1)*100,1)});
  else if(p)comparison=t('Vergleich erst bei guter Datenabdeckung');
  const valid=live.reading&&!live.stale;
  const cards=`<div class="cards">${metric(t('Aktuell zu Hause'),`<span id="live-power">${number(valid?live.reading.power_w:null,0)}</span>`,'W',t('Lokale Netzleistung'),'↯',true)}${metric(t('Netzbezug'),number(s.import_kwh,2),'kWh',comparison,'↗')}${metric(t('Erfasste Kosten'),number(s.known_cost_eur,2),'€',s.cost_complete?t('Inklusive anteiligem Grundpreis'):s.tariff_missing?t('Tarif fehlt oder Preisimport unvollständig'):t('Teilbetrag · Datenabdeckung beachten'),'€')}${metric(t('Leistungsspitze'),number(s.peak_w==null?null:s.peak_w/1000,2),'kW',t('Höchste erfasste Momentanleistung'),'⌁')}</div>`;
  const reading=live.reading;
  const flow=`<div class="flow"><div class="flow-end"><div class="flow-icon">♧</div><small>${t('STROMNETZ')}</small></div><div class="flow-line"></div><div class="flow-end"><div class="flow-icon">⌂</div><small>${t('ZU HAUSE')}</small></div></div><div class="stats-list">${stat(t('Bezug im Zeitraum'),unit(s.import_kwh,'kWh',2))}${stat(t('Einspeisung'),unit(s.export_kwh,'kWh',2))}${stat(t('Bezugszähler'),unit(reading?.import_kwh,'kWh',3))}${stat(t('Einspeisezähler'),unit(reading?.export_kwh,'kWh',3))}</div><div class="divider"></div>${coverage(s)}<p id="live-age" class="copy-footnote">${reading?t('Letzte Messung vor {seconds} s',{seconds:number(live.age_seconds,0)}):t('Noch keine Messung')}</p>`;
  const quality=panel(t('Datenqualität'),'',`<div class="insight"><span class="insight-icon">◉</span><div><h3>${s.coverage>.98?t('Dein Zeitraum ist gut erfasst.'):t('Deine Historie entsteht ab jetzt.')}</h3><p>${esc(totalNote(s))}. ${s.crossing_gaps?t('Eine Lücke reicht über die Zeitraumgrenze. Ihre Energiemenge bleibt außerhalb dieser Summe.'):''}</p></div></div>`);
  const compare=panel(t('Vorperiode'),'',p?`<div class="stats-list">${stat(t('Ausgewählter Zeitraum'),unit(s.import_kwh,'kWh',2))}${stat(t('Vorperiode'),unit(p.import_kwh,'kWh',2))}${stat(t('Abdeckung der Vorperiode'),unit(p.coverage*100,'%',1))}${stat(t('Vergleich bis'),localTime(p.end,{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}))}</div>`:empty(t('Vergleich noch nicht verfügbar.')));
  $('#page-dashboard').innerHTML=cards+`<div class="grid-main"><div>${powerPanel(data)}${quality}</div><div>${panel(t('Bezug und Einspeisung'),'',flow)}${compare}</div></div>`;
  mountOverlayToggles($('#page-dashboard'),()=>renderDashboard(overview));
}

function renderHistory(data) {
  const rows=data.series.energy;
  const table=rows.length?`<div class="table-wrap"><table><thead><tr><th>${t('Zeitpunkt / Zeitraum')}</th><th>${t('Bezug kWh')}</th><th>${t('Einspeisung kWh')}</th><th>${t('Erfasster Bezug')}</th><th>${t('Spitze W')}</th></tr></thead><tbody>${rows.map(row=>`<tr><td>${esc(data.series.group==='quarter'?localTime(row.ts,{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',timeZoneName:'short'}):localDate(row.ts))}</td><td>${number(row.import_kwh,3)}</td><td>${number(row.export_kwh,3)}</td><td>${unit(row.import_s/3600,'h',2)}</td><td>${number(row.peak_w,0)}</td></tr>`).join('')}</tbody></table></div>`:empty();
  const gaps=data.gaps.length?`<div class="table-wrap"><table><thead><tr><th>${t('Beginn')}</th><th>${t('Ende')}</th><th>${t('Bezug gesamt')}</th><th>${t('Grund')}</th></tr></thead><tbody>${data.gaps.slice(0,100).map(g=>`<tr><td>${esc(localTime(g.start))}</td><td>${esc(localTime(g.end))}</td><td>${unit(g.import_kwh,'kWh',3)}</td><td>${esc(String(g.reason).split('; ').map(part=>t(part)).join('; '))}</td></tr>`).join('')}</tbody></table></div><p class="copy-footnote">${t('Max. 100 angezeigt; vollständig unter Export → Lücken.')}</p>`:`<p class="muted">${t('Keine Messlücken in diesem Zeitraum.')}</p>`;
  $('#page-history').innerHTML=powerPanel(data)+panel(t('Verbrauch im Detail.'),periodText(),table)+panel(t('Messlücken'),'',gaps);
  mountOverlayToggles($('#page-history'),()=>renderHistory(overview));
}

function heatmap(cells) {
  if(!cells.length)return empty(t('Dein Tagesmuster wird hier sichtbar.'));
  const days=[...new Set(cells.map(c=>c.day))].slice(-62), lookup=new Map(cells.map(c=>[`${c.day}:${c.hour}`,c]));
  const maximum=Math.max(.01,...cells.map(c=>c.seconds?c.kwh*3600/c.seconds:0));
  let html='<div class="heat-scroll"><div class="heat-grid"><span></span>'+Array.from({length:24},(_,i)=>`<span class="heat-label">${String(i).padStart(2,'0')}</span>`).join('');
  for(const day of days){html+=`<span class="heat-label">${esc(dateLabel(day).slice(0,5))}</span>`;for(let h=0;h<24;h++){const cell=lookup.get(`${day}:${h}`), strength=cell?.seconds?Math.min(1,cell.kwh*3600/cell.seconds/maximum):null; const dark=window.kilowatchTheme?.isDark(); const color=strength==null?(dark?'#1d2622':'#eff2eb'):dark?`hsl(${83-strength*6} ${30+strength*30}% ${16+strength*42}%)`:`hsl(${83-strength*6} ${35+strength*20}% ${92-strength*54}%)`;html+=`<div class="heat-cell" style="background:${color}" title="${esc(dateLabel(day))} ${String(h).padStart(2,'0')}:00 · ${cell?t('{energy} / {hours} erfasst',{energy:unit(cell.kwh,'kWh',3),hours:unit(cell.seconds/3600,'h',2)}):t('keine Daten')}"></div>`;}}
  return html+'</div></div><div class="heat-key">'+esc(t('Wenig'))+' '+(window.kilowatchTheme?.isDark()?['#24301c','#3d5226','#64852f','#9dc23f']:['#eff4dd','#dce9ab','#b9d164','#86aa31']).map(c=>`<i style="background:${c}"></i>`).join('')+' '+esc(t('Viel · Farbe: Verbrauch je erfasster Stunde · letzte 62 Tage'))+'</div>';
}

function profileChart(rows) {
  const weekday=Array.from({length:24},(_,hour)=>({hours:hour,power_w:rows.find(r=>r.type==='weekday'&&r.hour===hour)?.average_kw*1000})).filter(r=>Number.isFinite(r.power_w));
  const weekend=Array.from({length:24},(_,hour)=>({hours:hour,power_w:rows.find(r=>r.type==='weekend'&&r.hour===hour)?.average_kw*1000})).filter(r=>Number.isFinite(r.power_w));
  const table=`<div class="table-wrap"><table><thead><tr><th>${t('Stunde')}</th><th>${t('Mo–Fr Ø W')}</th><th>${t('Sa–So Ø W')}</th></tr></thead><tbody>${Array.from({length:24},(_,h)=>`<tr><td>${String(h).padStart(2,'0')}:00</td><td>${number(weekday.find(r=>r.hours===h)?.power_w,0)}</td><td>${number(weekend.find(r=>r.hours===h)?.power_w,0)}</td></tr>`).join('')}</tbody></table></div>`;
  return table;
}

// Lastdauerlinie mit Nachtgrundlast und Grenze für hohe Last als Bezug.
function durationChart(data) {
  const spec={chart:'duration', trends:false, data:data.duration_curve, field:'power_w', xField:'hours',
    references:[{key:'baseline', label:t('Nachtgrundlast {watts}',{watts:unit(data.baseline_w,'W',0)}), value:data.baseline_w},
                {key:'highload', label:t('Grenze hohe Last {watts}',{watts:unit(settings.high_load_w,'W',0)}), value:settings.high_load_w}]};
  return overlayToggles(spec)+lineChart(data.duration_curve,'power_w','W','hours',{overlays:buildOverlays(spec)});
}

function renderAnalysis(data, base) {
  const forecast=data.forecast;
  const cards=`<div class="cards">${metric(t('Nachtgrundlast (P10)'),number(data.baseline_w,0),'W',t('{count} ausreichend erfasste Nachtintervalle',{count:data.night_quarters}),'☾',true)}${metric(t('Hohe Last'),number(base.summary.high_load_hours,2),'h',t('Intervallmittel ≥ {watts}',{watts:unit(settings.high_load_w,'W',0)}),'↗')}${metric(t('Zeitlich zugeordnet'),number(base.summary.allocated_import_kwh,2),'kWh',t('Aus Zählerstandsdifferenzen oder Schätzung'),'▥')}${metric(t('Monatsprognose'),number(forecast.available?forecast.expected_kwh:null,0),'kWh',forecast.available?t('{low} – {high} kWh Band',{low:number(forecast.low_kwh,0),high:number(forecast.high_kwh,0)}):t('Noch keine belastbare Datenbasis'),'⌁')}</div>`;
  const forecastText=t(forecast.available?forecast.method:forecast.reason);
  const anomaly=data.anomalies.map(a=>`<div class="insight"><span class="insight-icon">◉</span><div><h3>${esc(t(a.title))}</h3><p>${esc(t(a.text,numberParams(a.params)))}</p></div></div>`).join('');
  $('#page-analysis').innerHTML=cards+panel(t('Stundenmuster'),'',heatmap(data.heatmap))+`<div class="grid-two"><div>${panel(t('Lastdauerlinie'),'',durationChart(data))}${panel(t('Auffälligkeiten'),'',anomaly)}</div><div>${panel(t('Tagesverlauf'),'',profileChart(data.profile))}</div></div>`+panel(t('Prognose'),'',`<p class="muted">${esc(forecastText)}</p>`);
  mountOverlayToggles($('#page-analysis'),()=>loadPage());
  mountAnalysisInsights().catch(error=>toast(error.message,true));
}

function renderCosts(data, base) {
  const s=base.summary;
  const tariffRows=data.tariffs.map(tariff=>`<tr><td>${esc(dateLabel(tariff.start_date))}</td><td>${esc(tariff.name)}</td><td>${tariff.mode==='fixed'?t('1 Tarifstufe'):tariff.mode==='dual'?t('2 Tarifstufen (HT/NT)'):t('Variabel / CSV')}</td><td>${tariffRateLabel(tariff)}</td><td>${unit(tariff.base_month,'€',2)}</td><td><button class="secondary" data-edit-tariff="${esc(tariff.start_date)}">${t('Bearbeiten')}</button> <button class="danger-button" data-delete-tariff="${esc(tariff.start_date)}">${t('Entfernen')}</button></td></tr>`).join('');
  const costDetails=`<div class="stats-list">${stat(t('Bepreiste Bezugsenergie'),unit(s.energy_cost_eur,'€',2))}${stat(t('Anteilig bekannter Grundpreis'),unit(s.base_cost_eur,'€',2))}${stat(t('Einspeiseerlös'),unit(s.feedin_eur,'€',2))}${stat(t('Bekannter Gesamtbetrag'),unit(s.known_cost_eur,'€',2))}${stat(t('Energiemenge ohne Preiszuordnung'),unit(s.unpriced_kwh,'kWh',3))}</div><div class="divider"></div>${coverage(s)}${s.cost_complete?'':`<p class="copy-footnote">${t('Betrag unvollständig: nicht gemessene oder nicht bepreiste Energie fehlt.')}</p>`}`;
  const form=`<form id="tariff-form"><div class="form-grid"><label>${t('Gültig ab')}<input name="start_date" type="date" value="${today().slice(0,7)}-01" required></label><label>${t('Tarifname')}<input name="name" maxlength="80" placeholder="${esc(t('Mein Stromtarif'))}" required></label><label>${t('Preisart')}<select name="mode"><option value="fixed">${t('Festpreis')}</option><option value="dynamic">${t('Dynamisch per CSV-Import')}</option></select></label><label>${t('Arbeitspreis brutto (ct/kWh)')}<input name="ct_kwh" type="number" step=".001" min="-500" max="1000" required value="32"></label><label>${t('Grundpreis brutto (€/Monat)')}<input name="base_month" type="number" step=".01" min="0" max="1000" required value="0"></label><label>${t('Einspeisevergütung (ct/kWh)')}<input name="feedin_ct" type="number" step=".001" min="-500" max="1000" required value="0"></label></div><div class="form-actions"><button type="submit" class="primary">${t('Tarif speichern')}</button></div></form>`;
  const csv=`<p class="muted"><code>start,end,eur_kwh</code> ${t('· Bruttopreise · Zeit mit UTC-Offset · Viertelstundenraster')}</p><div class="form-actions"><label class="secondary">${t('CSV auswählen')}<input id="price-file" type="file" accept=".csv,text/csv" class="sr-only"></label><button class="danger-button" id="delete-prices">${t('Alle Importpreise löschen')}</button></div><p class="copy-footnote">${t('{count} Intervalle gespeichert',{count:data.prices.count})}${data.prices.start!=null?' · '+esc(localDate(data.prices.start))+' – '+esc(localDate(data.prices.end)):''}.</p><pre class="system-pre">start,end,eur_kwh\n2026-10-01T00:00:00+02:00,2026-10-01T01:00:00+02:00,0.295</pre>`;
  $('#page-costs').innerHTML=`<div class="grid-two"><div>${panel(t('Was dein Strom kostet.'),periodText(),costDetails)}<div id="budget-slot"></div></div><div>${panel(t('Tarif hinterlegen'),'',form)}</div></div>`+panel(t('Tarifhistorie'),'',tariffRows?`<div class="table-wrap"><table><thead><tr><th>${t('Ab')}</th><th>${t('Tarif')}</th><th>${t('Art')}</th><th>${t('Preis/kWh')}</th><th>${t('Grundpreis/Monat')}</th><th></th></tr></thead><tbody>${tariffRows}</tbody></table></div>`:empty(t('Noch kein Tarif hinterlegt.'),t('Trage deinen Arbeitspreis und Grundpreis ein.')))+'<div id="simulation-slot"></div>'+panel(t('Dynamische Preise'),'',csv);
  $('#tariff-form').addEventListener('submit',safely(async event=>{event.preventDefault();const values=Object.fromEntries(new FormData(event.target));await api('/api/tariffs','PUT',{start_date:values.start_date,name:values.name,mode:values.mode,eur_kwh:values.mode==='dynamic'?0:Number(values.ct_kwh)/100,base_month:Number(values.base_month),feedin_eur_kwh:Number(values.feedin_ct)/100,...tariffExtraValues(values)});toast(t('Tarif gespeichert.'));await loadPage();}));
  $$('[data-delete-tariff]').forEach(button=>button.addEventListener('click',safely(async()=>{await api('/api/tariffs/'+button.dataset.deleteTariff,'DELETE');toast(t('Tarif entfernt.'));await loadPage();})));
  $('#price-file').addEventListener('change',safely(async event=>{const file=event.target.files[0];if(!file)return;if(file.size>1500000)throw new Error(t('CSV darf höchstens 1,5 MB groß sein.'));const result=await api('/api/prices/import','POST',{csv:await file.text()});toast(t('{count} Preise importiert.',{count:result.count}));await loadPage();}));
  $('#delete-prices').addEventListener('click',safely(async()=>{await api('/api/prices','DELETE');toast(t('Importpreise entfernt.'));await loadPage();}));
  mountTariffOptions(data);
  mountCostInsights(data, base);
}

function renderEvents(events) {
  const items=events.map(e=>`<article class="event-item"><h3>${esc(e.title)}</h3><small>${esc(localDate(e.start))} – ${esc(localDate(e.end-1))}</small><p>${esc(e.note)}</p><div class="button-row"><button class="secondary" data-compare-event="${e.id}">${t('Verbrauch vergleichen')}</button><button class="danger-button" data-delete-event="${e.id}">${t('Entfernen')}</button></div><div id="event-result-${e.id}" hidden class="inline-result"></div></article>`).join('');
  const form=`<form id="event-form"><div class="form-grid"><label class="full">${t('Ereignis')}<input name="title" maxlength="120" placeholder="${esc(t('Zum Beispiel: neuer Kühlschrank'))}" required></label><label>${t('Von')}<input name="start_date" type="date" value="${today()}" required></label><label>${t('Bis einschließlich')}<input name="end_date" type="date" value="${today()}" required></label><label class="full">${t('Notiz')}<textarea name="note" rows="4" maxlength="2000" placeholder="${esc(t('Was hat sich verändert?'))}"></textarea></label></div><div class="form-actions"><button class="primary" type="submit">${t('Ereignis markieren')}</button></div></form>`;
  $('#page-events').innerHTML=`<div class="grid-two"><div>${panel(t('Ereignisse'),'',items||empty(t('Noch keine Ereignisse.'),t('Deine eigenen Markierungen erscheinen hier.')))}</div><div>${panel(t('Ereignis hinzufügen'),'',form)}</div></div>`;
  $('#event-form').addEventListener('submit',safely(async e=>{e.preventDefault();await api('/api/events','POST',Object.fromEntries(new FormData(e.target)));toast(t('Ereignis gespeichert.'));await loadPage();}));
  $$('[data-delete-event]').forEach(b=>b.addEventListener('click',safely(async()=>{await api('/api/events/'+b.dataset.deleteEvent,'DELETE');await loadPage();})));
  $$('[data-compare-event]').forEach(b=>b.addEventListener('click',safely(async()=>{const result=await api(`/api/events/${b.dataset.compareEvent}/comparison`);const node=$('#event-result-'+b.dataset.compareEvent);node.hidden=false;node.textContent=[t('Im Ereignis: {energy} ({coverage} erfasst)',{energy:unit(result.during.import_kwh,'kWh',2),coverage:unit(result.during.coverage*100,'%',1)}),t('Davor: {energy} ({coverage} erfasst)',{energy:unit(result.before.import_kwh,'kWh',2),coverage:unit(result.before.coverage*100,'%',1)}),t('Ein laufendes Ereignis ist kürzer als seine volle Vorperiode. Der Vergleich zeigt Zusammenhänge, keine nachgewiesene Ursache.')].join('\n');})));
}

function renderReports(data) {
  const s=data.summary;
  const rows=data.series.energy.map(r=>`<tr><td>${esc(localTime(r.ts,{day:'2-digit',month:'2-digit',year:'numeric',...(data.series.group==='quarter'?{hour:'2-digit',minute:'2-digit',timeZoneName:'short'}:{})}))}</td><td>${number(r.import_kwh,3)}</td><td>${number(r.export_kwh,3)}</td><td>${unit(r.import_s/3600,'h',2)}</td></tr>`).join('');
  const content=`<div class="report-heading"><h1>${t('Kilowatch · Energiebericht')}</h1><p>${esc(t(settings.name))} · ${esc(periodText())}</p></div><div class="report-actions button-row"><button class="primary" id="print-report">${t('Drucken / als PDF speichern')}</button><button class="secondary" id="month-report">${t('Aktueller Monat')}</button><button class="secondary" id="year-report">${t('Aktuelles Jahr')}</button></div><div class="report-summary"><p><strong>${esc(periodText())}</strong> · ${esc(t('Erstellt {time}',{time:localTime(Date.now()/1000)}))}</p><p>${t('Netzbezug:')} <strong>${unit(s.import_kwh,'kWh',3)}</strong> · ${t('Einspeisung:')} <strong>${unit(s.export_kwh,'kWh',3)}</strong></p><p>${t('Bekannte Kosten:')} <strong>${unit(s.known_cost_eur,'€',2)}</strong> · ${s.cost_complete?t('Nahezu vollständiger Zeitraum'):t('Unvollständiger Betrag')} · ${t('Datenabdeckung:')} ${unit(s.coverage*100,'%',2)}</p><p>${esc(t('Lückenenergie im Bezug: {energy}',{energy:unit(s.recovered_import_kwh,'kWh',3)}))} · ${esc(t('{count} Lücke(n)',{count:s.gap_count}))} · ${esc(t('{count} über die Zeitraumgrenzen',{count:s.crossing_gaps}))}</p></div>${rows?`<div class="table-wrap"><table><thead><tr><th>${t('Zeitraum')}</th><th>${t('Bezug kWh')}</th><th>${t('Einspeisung kWh')}</th><th>${t('Erfasster Bezug')}</th></tr></thead><tbody>${rows}</tbody></table></div>`:empty()}<p class="copy-footnote">${esc(t('Geschätzter Bezug aus Leistungsintegration: {energy}',{energy:unit(s.estimated_import_kwh,'kWh',3)}))}</p>`;
  const exports=`<div class="form-grid"><label>${t('Datentyp')}<select id="export-kind"><option value="quarters">${t('Viertelstunden · dauerhaft')}</option><option value="minutes">${t('Minutenwerte · innerhalb Aufbewahrung')}</option><option value="samples">${t('Einzelmessungen · innerhalb Aufbewahrung')}</option><option value="gaps">${t('Messlücken · separat')}</option></select></label><label>${t('Format')}<select id="export-format"><option value="csv">${t('CSV (Semikolon / UTF-8)')}</option><option value="json">JSON</option></select></label></div><div class="form-actions"><button class="primary" id="export-data">${t('Datei herunterladen')}</button><a href="/api/backup" class="secondary" download>${t('Datenbank sichern')}</a></div><p class="copy-footnote">${t('Max. 100.000 Zeilen pro Datei.')}</p>`;
  $('#page-reports').innerHTML=panel(t('Dein Energiebericht.'),periodText(),content)+`<div class="report-actions">${panel(t('Export'),'',exports)}</div>`;
  $('#print-report').addEventListener('click',()=>window.print());
  $('#month-report').addEventListener('click',()=>applyRange('month'));$('#year-report').addEventListener('click',()=>applyRange('year'));
  $('#export-data').addEventListener('click',()=>{window.location.href=`/api/export?${query()}&kind=${$('#export-kind').value}&format=${$('#export-format').value}`;});
}


function renderSystem(data) {
  const d=data.bridge;
  const info=`<div class="stats-list">${stat(t('Status'),data.collector.message?t(data.collector.message,data.collector.params||{}):'—')}${stat(t('Funkpegel Zähler → Bridge'),unit(d.rssi_dbm,'dBm',1))}${stat(t('Spannung am Lesekopf'),unit(d.battery_v,'V',2))}${stat(t('Temperatur'),unit(d.temperature_c,'°C',1))}${stat(t('Paketempfang'),unit(d.delivery_percent,'%',1))}${stat(t('Ungültige Telegramme laut Bridge'),number(d.invalid_readings,0))}${stat(t('Firmware'),d.firmware?Object.entries(d.firmware).map(([key,val])=>`${key}: ${val}`).join(' / '):'—')}${stat(t('Datenbank inklusive WAL'),unit(data.database_bytes/1024/1024,'MB',1))}${stat(t('Einzelmessungen'),number(data.counts.samples,0))}${stat(t('Viertelstunden'),number(data.counts.quarters,0))}</div>`;
  const issues=data.issues.length?`<div class="table-wrap"><table><thead><tr><th>${t('Zeit')}</th><th>${t('Art')}</th><th>${t('Hinweis')}</th></tr></thead><tbody>${data.issues.map(i=>`<tr><td>${esc(localTime(i.ts))}</td><td>${esc(i.code)}</td><td>${esc(t(i.message))}</td></tr>`).join('')}</tbody></table></div>`:`<p class="muted">${t('Keine gespeicherten Erfassungsfehler.')}</p>`;
  const obis=Object.entries(live.obis||{}).map(([key,val])=>`<tr><td>${esc(key)}</td><td>${esc(val.value)}</td><td>${esc(val.unit)}</td></tr>`).join('');
  $('#page-system').innerHTML=`<div class="grid-two"><div>${panel(t('Verbindung & Empfang'),'',info)}</div><div>${panel(t('Sicherungen'),'',`<p class="muted">${data.backups.length?data.backups.map(esc).join('<br>'):t('Noch keine automatische Sicherung.')}</p><div class="form-actions"><a class="primary" href="/api/backup" download>${t('Jetzt konsistent sichern')}</a></div>`)}${panel(t('Register'),'',obis?`<div class="table-wrap"><table><thead><tr><th>OBIS</th><th>${t('Wert')}</th><th>${t('Einheit')}</th></tr></thead><tbody>${obis}</tbody></table></div>`:empty())}</div></div>`+panel(t('Erfassungsprotokoll'),'',issues);
  mountUpdates().catch(error=>toast(error.message,true));
}

// Quelltexte; übersetzt wird erst bei der Anzeige, wenn die Sprache feststeht.
const pageText={
  dashboard:tk('Übersicht'),
  history:tk('Verlauf'),
  analysis:tk('Analysen'),
  costs:tk('Kosten & Tarife'),
  notifications:tk('Benachrichtigungen'),
  events:tk('Ereignisse'),
  reports:tk('Berichte & Export'),
  settings:tk('Einstellungen'),
  system:tk('System & Datenqualität')
};

async function loadPage() {
  lastPageRefresh=Date.now();
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
  const text=t(pageText[page]);$('#breadcrumb').textContent=text.toLocaleUpperCase(LOCALE);$('#page-title').textContent=text;
  $('#range-bar').hidden=['settings','system','events','notifications'].includes(page);
  $('.sidebar').classList.remove('open');
  if(updateHash)history.replaceState(null,'','#'+page);
  await loadPage();
}

async function applyRange(value) {
  const now=today();let start=now,end=now;
  rangeHours=value.startsWith('hours')?Number(value.slice(5)):null;
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
  setCurrency(settings.currency);
  // Die Wahl in diesem Browser gilt zuerst; der Server merkt sich die Sprache für Benachrichtigungen.
  if(!storedLanguage()&&settings.language&&settings.language!==LANGUAGE)await setLanguage(settings.language,false);
  if(!settings.language)api('/api/settings','PUT',{language:LANGUAGE}).then(()=>{settings.language=LANGUAGE;}).catch(()=>{});
  $('#login').hidden=true;$('#application').hidden=false;$('#home-name').textContent=t(settings.name);$('#version').textContent=settings.version;
  $('#today-label').textContent=new Date().toLocaleDateString(LOCALE,{weekday:'short',day:'numeric',month:'long',year:'numeric',timeZone:settings.timezone||'Europe/Berlin'});
  if(!$('#range-start').value){$('#range-start').value=today();$('#range-end').value=today();}
  $('#range-end').max=today();$('#range-start').max=today();
  let initial=location.hash.slice(1)||'dashboard';if(settings.setup_required&&!settings.demo)initial='settings';
  await navigate(initial);updateLiveParts();
}

$('#first-start-form').addEventListener('submit',async event=>{event.preventDefault();$('#setup-error').textContent='';try{const data=Object.fromEntries(new FormData(event.target));if(data.password!==data.confirmation)throw new Error(t('Passwörter stimmen nicht überein.'));delete data.confirmation;await api('/api/setup','POST',data);await api('/api/login','POST',{password:data.password});event.target.reset();$('#first-start-form').hidden=true;$('#login-form').hidden=false;await start();}catch(error){$('#setup-error').textContent=error.message;}});
$('#login-form').addEventListener('submit',async event=>{event.preventDefault();$('#login-error').textContent='';try{await api('/api/login','POST',{password:$('#login-password').value});$('#login-password').value='';await start();}catch(error){$('#login-error').textContent=error.message;}});
$('#login-language').addEventListener('change',safely(async event=>{await setLanguage(event.target.value);}));
$('#logout').addEventListener('click',safely(async()=>{await api('/api/logout','POST');showLogin();}));
$$('[data-page]').forEach(button=>button.addEventListener('click',()=>navigate(button.dataset.page)));
$$('[data-range]').forEach(button=>button.addEventListener('click',()=>applyRange(button.dataset.range)));
$('#range-form').addEventListener('submit',event=>{event.preventDefault();if($('#range-end').value<$('#range-start').value){toast(t('Das Ende liegt vor dem Beginn.'),true);return;}$$('[data-range]').forEach(button=>button.classList.remove('selected'));rangeHours=null;loadPage();});
$('#mobile-menu').addEventListener('click',()=>$('.sidebar').classList.toggle('open'));
// Farbschema: Auto → Hell → Dunkel; Diagramme neu zeichnen, weil Heatmap-Farben vom Schema abhängen.
window.kilowatchTheme?.refresh();
$('#theme-toggle').addEventListener('click',()=>{window.kilowatchTheme.cycle();if(!$('#application').hidden)loadPage();});
window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change',()=>{if(window.kilowatchTheme?.current()==='auto'&&!$('#application').hidden)loadPage();});
window.addEventListener('hashchange',()=>navigate(location.hash.slice(1),false));
// Live-Werte im eingestellten Abfrageintervall; Diagramme minütlich, in der Stundenansicht alle 15 Sekunden.
let lastLiveRefresh=Date.now();
setInterval(async()=>{
  if($('#application').hidden||document.hidden)return;
  if(Date.now()-lastLiveRefresh>=Math.min(60,Math.max(2,Number(settings?.poll_seconds)||5))*1000){
    lastLiveRefresh=Date.now();
    try{live=await api('/api/live');updateLiveParts();}catch(error){if(!$('#application').hidden)toast(error.message,true);}
  }
  if(['dashboard','history'].includes(page)&&Date.now()-lastPageRefresh>=(rangeHours?15000:60000))loadPage();
},1000);
setLanguage(pickLanguage(),false).then(start).catch(error=>{showLogin();if(error.status!==401)$('#login-error').textContent=error.message;});
