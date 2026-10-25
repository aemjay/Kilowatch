'use strict';

// Erweiterte Auswertungen und Update-Hinweis. Alle Werte laufen über esc/number/unit.

function hourChart(rows, field, label) {
  const values=rows.filter(row=>row[field]!=null);
  if(!values.length)return empty(t('Keine Werte im Zeitraum.'));
  const w=760,h=200,left=42,top=14,bottom=30,right=9,max=Math.max(.01,...values.map(row=>row[field]))*1.15,width=(w-left-right)/24;
  let grid='';
  for(let i=0;i<=4;i++){const y=h-bottom-(h-top-bottom)*i/4;grid+=`<line class="grid-line" x1="${left}" x2="${w-right}" y1="${y}" y2="${y}"/><text x="${left-8}" y="${y+3}" text-anchor="end">${number(max*i/4,2)}</text>`;}
  const bars=rows.map(row=>{const x=left+row.hour*width,value=row[field];if(value==null)return '';const y=h-bottom-value/max*(h-top-bottom);return `<rect x="${x+width*.18}" y="${y}" width="${width*.64}" height="${h-bottom-y}" rx="3" fill="#bfd559"><title>${String(row.hour).padStart(2,'0')}:00 · ${esc(unit(value,label,3))}</title></rect>`;}).join('');
  const labels=Array.from({length:8},(_,i)=>`<text x="${left+i*3*width+width/2}" y="${h-9}" text-anchor="middle">${String(i*3).padStart(2,'0')}</text>`).join('');
  return `<div class="chart"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(t('{label} nach Tageszeit',{label}))}">${grid}${bars}${labels}<text x="${left}" y="8">${esc(label)}</text></svg></div>`;
}

async function mountAnalysisInsights() {
  const target=$('#page-analysis'),version=requestVersion;
  const data=await api('/api/insights?'+query()).catch(error=>{toast(error.message,true);return null;});
  // Inzwischen neu geladene oder gewechselte Seite nicht doppelt ergänzen.
  if(!data||page!=='analysis'||version!==requestVersion)return;
  const trend=data.baseline_trend, valid=trend.points.filter(p=>p.baseline_w!=null), last=valid.at(-1);
  const bars=trend.points.map(p=>({ts:p.start,baseline_w:p.baseline_w,import_s:p.quarters*900}));
  const stats=`<div class="stats-list">${stat(trend.group==='week'?t('Letzte Woche'):t('Letzter Monat'),last?unit(last.baseline_w,'W',0):t('Zu wenig Nachtdaten'))}${stat(t('Grundlast pro Jahr'),last?unit(last.annual_kwh,'kWh',0):'—')}${stat(t('Kosten der Grundlast pro Jahr'),last&&last.annual_eur!=null?unit(last.annual_eur,'€',0):t('Tarif fehlt'))}${stat(t('Veränderung (2. gegen 1. Hälfte)'),trend.change_w==null?t('Zu wenige Punkte'):unit(trend.change_w,'W',0))}</div>`;
  const note=`<p class="copy-footnote">${esc(t(trend.method))} ${esc(t('Punkte mit weniger als {count} erfassten Nachtviertelstunden bleiben leer. Nächte mit Einspeisung oder Batterieentladung zählen nicht als Grundlast.',{count:trend.min_quarters}))}</p>`;
  target.insertAdjacentHTML('beforeend',panel('Grundlast-Entwicklung',t('Nachtgrundlast je ')+(trend.group==='week'?t('Woche'):t('Monat')),barChart(bars,'baseline_w','W')+stats+note));
  const feed=data.feedin;
  if(feed.total_kwh){
    target.insertAdjacentHTML('beforeend',panel(t('Einspeisung'),t('Mittlere Einspeiseleistung nach Tageszeit'),hourChart(feed.profile,'average_kw','kW')+`<div class="stats-list">${stat(t('Eingespeist im Zeitraum'),unit(feed.total_kwh,'kWh',2))}</div><p class="copy-footnote">${t('Gemessen wird nur der Überschuss am Netzanschluss. Eigenverbrauch und Autarkie lassen sich daraus nicht bestimmen.')}</p>`));
  }
}

function scenarioValues(form) {
  const v=Object.fromEntries(new FormData(form));
  const tariff={mode:v.mode,base_month:Number(v.base_month),feedin_eur_kwh:Number(v.feedin_ct)/100};
  if(v.mode!=='spot')tariff.eur_kwh=Number(v.ct_kwh)/100;
  if(v.mode==='dual')Object.assign(tariff,{low_eur_kwh:Number(v.low_ct)/100,low_start:v.low_start,low_end:v.low_end,weekend_low:v.weekend_low==='true'});
  if(v.mode==='spot')Object.assign(tariff,{markup_ct:Number(v.markup_ct),vat_percent:Number(v.vat_percent)});
  return {start:$('#range-start').value,end:$('#range-end').value,tariff};
}

function simulationResult(r) {
  const lines=[stat('Arbeitspreis-Kosten',unit(r.energy_cost_eur,'€',2)),stat(t('Grundpreis anteilig'),unit(r.base_cost_eur,'€',2)),stat(t('Einspeiseerlös'),unit(r.feedin_eur,'€',2)),stat(t('Gesamt mit diesem Tarif'),unit(r.total_eur,'€',2)),stat(t('Tatsächlich erfasst'),r.actual_total_eur==null?t('Kein Tarif hinterlegt'):unit(r.actual_total_eur,'€',2)),stat(t('Bepreister Anteil des Bezugs'),r.priced_share==null?'—':unit(r.priced_share*100,'%',1)),stat(t('Durchschnittspreis'),r.average_eur_kwh==null?'—':unit(r.average_eur_kwh*100,'ct/kWh',2))];
  if(r.spot_weighted_ct!=null)lines.push(stat(t('Dein Börsenpreis (verbrauchsgewichtet)'),unit(r.spot_weighted_ct,'ct/kWh',2)),stat(t('Börsenpreis im Zeitmittel'),unit(r.spot_time_average_ct,'ct/kWh',2)));
  let difference=`<p class="inline-result">${t('Kein Vergleich möglich: Für den Zeitraum fehlt ein hinterlegter Tarif oder ein Preis im simulierten Tarif.')}</p>`;
  if(r.difference_eur!=null)difference=`<p class="inline-result">${esc(r.difference_eur<0?t('Günstiger als dein Tarif: {amount} im Zeitraum',{amount:unit(-r.difference_eur,'€',2)}):t('Teurer als dein Tarif: {amount} im Zeitraum',{amount:unit(r.difference_eur,'€',2)}))}${r.paired_share<.995?' · '+esc(t('verglichen über {share} des Bezugs, der in beiden Tarifen bepreist ist',{share:unit(r.paired_share*100,'%',1)})):''}</p>`;
  const spotNote=r.spot_weighted_ct!=null?`<p class="copy-footnote">${t('Liegt dein verbrauchsgewichteter Börsenpreis über dem Zeitmittel, fällt dein Bezug eher in teure Stunden; Verschieben in günstige Zeiten könnte sich lohnen.')}</p>`:'';
  return `<div class="divider"></div><div class="stats-list">${lines.join('')}</div>${difference}${spotNote}<p class="copy-footnote">${t('Annahme: gleicher Verbrauch zur gleichen Zeit. Eine Verhaltensänderung durch den anderen Tarif ist nicht berücksichtigt.')}</p>`;
}

function mountSimulation(data) {
  const slot=$('#simulation-slot');if(!slot)return;
  const history=data.spot_history||{count:0};
  const historyText=history.count?esc(t('{count} Börsenpreis-Intervalle gespeichert · {start} – {end}',{count:number(history.count,0),start:localDate(history.start),end:localDate(history.end)})):t('Noch keine Börsenpreise gespeichert.');
  const form=`<form id="simulation-form"><div class="form-grid"><label>${t('Tarifart')}<select name="mode"><option value="fixed">${t('Festpreis')}</option><option value="dual">HT/NT</option>${CURRENCY===CURRENCIES.EUR?`<option value="spot">${t('Dynamisch (Börsenpreis + Aufschlag)')}</option>`:''}</select></label><label data-sim="fixed dual">${t('Arbeitspreis bzw. HT brutto (ct/kWh)')}<input name="ct_kwh" type="number" step=".001" value="30" required></label><label data-sim="dual">${t('NT brutto (ct/kWh)')}<input name="low_ct" type="number" step=".001" value="22"></label><label data-sim="dual">${t('NT von')}<input name="low_start" type="time" step="900" value="22:00"></label><label data-sim="dual">${t('NT bis')}<input name="low_end" type="time" step="900" value="06:00"></label><label data-sim="dual">${t('Wochenende NT')}<select name="weekend_low"><option value="false">${t('Nein')}</option><option value="true">${t('Ja')}</option></select></label><label data-sim="spot">${t('Aufschlag netto (ct/kWh)')}<input name="markup_ct" type="number" step=".01" value="17"><small>${t('Netzentgelt, Umlagen, Steuern und Marge des Anbieters')}</small></label><label data-sim="spot">${t('Mehrwertsteuer (%)')}<input name="vat_percent" type="number" step=".1" min="0" max="30" value="19"></label><label>${t('Grundpreis brutto (€/Monat)')}<input name="base_month" type="number" step=".01" min="0" value="12" required></label><label>${t('Einspeisevergütung (ct/kWh)')}<input name="feedin_ct" type="number" step=".001" value="0" required></label></div><div class="form-actions"><button type="submit" class="primary">${t('Für den Zeitraum berechnen')}</button></div></form>`;
  const spot=`<div data-sim="spot"><p class="muted">${historyText}</p><div class="form-actions"><button class="secondary" id="spot-history" type="button"${settings.demo?' disabled':''}>${t('Börsenpreise für den Zeitraum nachladen')}</button></div><p class="copy-footnote">${t('Internetabruf bei aWATTar DE, höchstens 62 Tage je Abruf. Es werden keine Messdaten übertragen.')}</p></div>`;
  slot.innerHTML=panel(t('Tarif simulieren'),t('Derselbe Lastgang mit einem anderen Tarif · ')+periodText(),form+spot+'<div id="simulation-result"></div>');
  const element=$('#simulation-form'),mode=element.elements.mode;
  const change=()=>{for(const node of slot.querySelectorAll('[data-sim]')){node.hidden=!node.dataset.sim.split(' ').includes(mode.value);for(const input of node.querySelectorAll('input,select'))input.disabled=node.hidden;}};
  mode.addEventListener('change',change);change();
  element.addEventListener('submit',safely(async event=>{event.preventDefault();const result=await api('/api/simulate','POST',scenarioValues(element));$('#simulation-result').innerHTML=simulationResult(result);}));
  $('#spot-history').addEventListener('click',safely(async event=>{const button=event.target;button.disabled=true;try{const result=await api('/api/market/history','POST',{start:$('#range-start').value,end:$('#range-end').value});toast(t('{count} Börsenpreis-Intervalle geladen.',{count:result.added}));await loadPage();}finally{button.disabled=false;}}));
}

function budgetStatus(data) {
  const m=data.month,a=data.annual,s=data.settings,lines=[];
  lines.push(stat(t('Bisher in diesem Monat'),m.observed_eur==null?t('Tarif fehlt'):unit(m.observed_eur,'€',2)+' · '+unit(m.observed_kwh,'kWh',1)));
  lines.push(stat(t('Prognose Monatsende'),m.forecast_eur==null?(m.forecast_reason?t(m.forecast_reason):t('Noch keine belastbare Prognose')):unit(m.forecast_eur,'€',0)+' · '+unit(m.forecast_kwh,'kWh',0)));
  if(s.monthly_eur)lines.push(stat(t('Monatsbudget'),unit(s.monthly_eur,'€',0)+(m.forecast_eur!=null?(m.forecast_eur>s.monthly_eur?t(' · voraussichtlich überschritten'):t(' · voraussichtlich eingehalten')):'')));
  if(s.monthly_kwh)lines.push(stat(t('Monatsziel Bezug'),unit(s.monthly_kwh,'kWh',0)+(m.forecast_kwh!=null?(m.forecast_kwh>s.monthly_kwh?t(' · voraussichtlich überschritten'):t(' · voraussichtlich eingehalten')):'')));
  if(a.available){
    lines.push(stat(t('Hochrechnung Jahr'),`${unit(a.annual_eur,'€',0)} (${unit(a.low_eur,'€',0)} – ${unit(a.high_eur,'€',0)})`));
    if(a.abschlag_year_eur!=null)lines.push(stat(t('12 × Abschlag'),unit(a.abschlag_year_eur,'€',0)+' · '+(a.difference_eur>0?t('voraussichtlich Nachzahlung ca. {amount}',{amount:unit(a.difference_eur,'€',0)}):t('voraussichtlich Guthaben ca. {amount}',{amount:unit(-a.difference_eur,'€',0)}))));
  } else lines.push(stat(t('Hochrechnung Jahr'),a.reason||t('Noch nicht möglich')));
  const note=a.available?`<p class="copy-footnote">${esc(t(a.method))} ${esc(t('Grundlage: {count} vollständig erfasste Tage',{count:number(a.valid_days,0)}))}${a.full_year?'':esc(t(' (weniger als ein Jahr)'))}.</p>`:'';
  return `<div class="stats-list">${lines.join('')}</div>${note}`;
}

async function mountBudget() {
  const slot=$('#budget-slot');if(!slot)return;
  const data=await api('/api/budget').catch(error=>{toast(error.message,true);return null;});
  if(!data||!slot.isConnected||$('#budget-slot')!==slot)return;
  const s=data.settings,value=v=>v==null?'':esc(v);
  const form=`<form id="budget-form"><div class="form-grid"><label>${t('Monatsbudget (€)')}<input name="monthly_eur" type="number" step="1" min="1" value="${value(s.monthly_eur)}" placeholder="${esc(t('optional'))}"></label><label>${t('Monatsziel Bezug (kWh)')}<input name="monthly_kwh" type="number" step="1" min="1" value="${value(s.monthly_kwh)}" placeholder="${esc(t('optional'))}"></label><label>${t('Monatlicher Abschlag (€)')}<input name="abschlag_eur" type="number" step=".01" min="1" value="${value(s.abschlag_eur)}" placeholder="${esc(t('optional'))}"></label></div><div class="form-actions"><button type="submit" class="secondary">${t('Speichern')}</button></div></form>`;
  slot.innerHTML=panel(t('Budget & Abschlag'),'',budgetStatus(data)+'<div class="divider"></div>'+form+`<p class="copy-footnote">${t('Eine Benachrichtigung bei erreichtem Monatsbudget lässt sich unter Benachrichtigungen einschalten.')}</p>`);
  $('#budget-form').addEventListener('submit',safely(async event=>{event.preventDefault();const v=Object.fromEntries(new FormData(event.target));const body={};for(const key of ['monthly_eur','monthly_kwh','abschlag_eur'])body[key]=v[key]===''?null:Number(v[key]);await api('/api/budget','PUT',body);toast(t('Budget gespeichert.'));await mountBudget();}));
}

function mountCostInsights(data) {
  mountSimulation(data);
  mountBudget().catch(error=>toast(error.message,true));
}

async function mountUpdates() {
  const target=$('#page-system'),version=requestVersion;
  const data=await api('/api/updates').catch(()=>null);
  if(!data||page!=='system'||version!==requestVersion)return;
  let state=t('Keine Information');
  if(data.available)state=`${t('Version {version} verfügbar',{version:data.latest})}${data.major_change?t(' · neue Hauptversion, vorher Hinweise lesen'):''}${data.schema_change?t(' · ändert die Datenbank (Sicherung wird automatisch angelegt)'):''}`;
  else if(data.latest)state=t('Aktuell');
  const link=data.available&&data.url?`<p><a href="${esc(data.url)}" target="_blank" rel="noopener noreferrer">${t('Release-Hinweise öffnen')}</a></p>`:'';
  const stats=`<div class="stats-list">${stat(t('Installiert'),data.current)}${stat(t('Stand'),state)}${stat(t('Zuletzt geprüft'),data.checked_at?localTime(data.checked_at):t('Noch nie'))}</div>${data.error?`<div class="notice">${esc(data.error)}</div>`:''}${link}`;
  const controls=`<div class="form-grid"><label>${t('Täglich nach Updates suchen')}<select id="update-enabled"${settings.demo?' disabled':''}><option value="false"${data.enabled?'':' selected'}>${t('Aus')}</option><option value="true"${data.enabled?' selected':''}>${t('Ein')}</option></select></label></div><div class="form-actions"><button class="secondary" id="update-check" type="button"${settings.demo?' disabled':''}>${t('Jetzt prüfen')}</button></div><p class="copy-footnote">${esc(t('Fragt bei GitHub ({repository}) nach dem neuesten Release. Es werden keine Messdaten übertragen. Installiert wird nie automatisch aus der App, sondern über DSM; siehe docs/UPDATES.md.',{repository:data.repository}))}</p>`;
  target.insertAdjacentHTML('beforeend',panel(t('Updates'),'',stats+controls));
  $('#update-enabled').addEventListener('change',safely(async event=>{await api('/api/updates','PUT',{enabled:event.target.value==='true'});toast(event.target.value==='true'?t('Update-Hinweis eingeschaltet.'):t('Update-Hinweis ausgeschaltet.'));}));
  $('#update-check').addEventListener('click',safely(async event=>{event.target.disabled=true;try{await api('/api/updates/check','POST');await loadPage();}finally{event.target.disabled=false;}}));
}
