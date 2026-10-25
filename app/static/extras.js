'use strict';

function mountDiscovery() {
  $('#page-settings .grid-main').insertAdjacentHTML('afterend',panel('Bridge im Heimnetz suchen','',`<div class="form-grid"><label>Subnetz (CIDR)<input id="discovery-network" placeholder="z. B. 192.168.1.0/24" autocomplete="off"><small id="discovery-hint">Netzvorschlag wird ermittelt …</small></label><label>Erkannte Netzvorschläge<select id="discovery-suggestion"><option value="">Eigenes Netz eingeben</option></select></label></div><div class="form-actions"><button class="secondary" id="discover-bridge" type="button"${settings.demo?' disabled':''}>Im Subnetz suchen</button></div><div id="discovery-result" aria-live="polite"></div>`));
  const field=$('#discovery-network'),select=$('#discovery-suggestion'),hint=$('#discovery-hint'),box=$('#discovery-result');
  if(settings.demo){hint.textContent='Im Demo-Modus wird kein Netzwerk durchsucht.';return;}
  api('/api/discovery/network').then(data=>{if(!field.isConnected)return;for(const item of data.suggestions||[]){const option=document.createElement('option');option.value=item.network;option.textContent=`${item.network} · ${item.reason}`;select.append(option);}if(data.suggestions?.length&&!field.value.trim()){field.value=data.suggestions[0].network;select.value=field.value;}hint.textContent='Subnetz vor dem Suchen prüfen. DHCP kann eingeschaltet bleiben.';}).catch(()=>{if(hint.isConnected)hint.textContent='Subnetz bitte selbst eingeben; es konnte kein Netzvorschlag ermittelt werden.';});
  select.addEventListener('change',()=>{if(select.value)field.value=select.value;});
  $('#discover-bridge').addEventListener('click',safely(async event=>{const button=event.target;if(!field.value.trim())throw new Error('Bitte ein lokales Subnetz eingeben.');button.disabled=true;box.textContent='Suche läuft …';try{const result=await api('/api/discovery/scan','POST',{network:field.value.trim()});if(!box.isConnected)return;box.innerHTML=result.devices.length?`<p class="muted">${result.devices.length} mögliche Bridge(s) in ${esc(result.network)} gefunden.</p><div class="table-wrap"><table><thead><tr><th>Adresse</th><th>Gerätename</th><th></th></tr></thead><tbody>${result.devices.map((device,index)=>`<tr><td>${esc(device.ip)}</td><td>${esc(device.fqdn||'Kein DNS-Name erkannt')}</td><td><button type="button" class="secondary" data-use-device="${index}">Verwenden</button></td></tr>`).join('')}</tbody></table></div>`:`<div class="notice">Keine eindeutige Bridge in ${esc(result.network)} gefunden (${result.checked} Adressen geprüft). Webserver, Netzmaske und Firewall prüfen oder den Gerätenamen direkt eintragen.</div>`;$$('[data-use-device]',box).forEach(button=>button.addEventListener('click',()=>{const device=result.devices[Number(button.dataset.useDevice)];$('#settings-form [name="bridge_host"]').value=device.host;toast(device.fqdn?'Gerätename übernommen. Zugangsdaten eingeben und Verbindung prüfen.':'Adresse übernommen. Für DHCP bei Bedarf den DNS-Namen aus dem Router einsetzen.');}));}finally{button.disabled=false;}}));
}

function tariffExtraValues(values) {
  return values.mode==='dual'?{low_eur_kwh:Number(values.low_ct)/100,low_start:values.low_start,low_end:values.low_end,weekend_low:values.weekend_low==='true'}:{};
}

function tariffRateLabel(t) {
  if(t.mode==='dual')return esc(`${unit(t.eur_kwh*100,'ct',2)} HT / ${unit(t.low_eur_kwh*100,'ct',2)} NT · NT ${t.low_start}–${t.low_end}${t.weekend_low?' + Wochenende':''}`);
  return t.mode==='fixed'?unit(t.eur_kwh*100,'ct',2):'CSV-Bruttopreise';
}

function mountTariffOptions(data) {
  const form=$('#tariff-form'),mode=form.elements.mode,price=form.elements.ct_kwh;
  mode.options[0].textContent='1 Tarifstufe · ein Preis';
  const dual=document.createElement('option');dual.value='dual';dual.textContent='2 Tarifstufen · HT/NT';mode.add(dual,1);
  mode.options[2].textContent='Variabel · vollständige Preise per CSV';
  price.value='';price.placeholder='Dein Bruttopreis';
  form.querySelector('.form-grid').insertAdjacentHTML('beforeend',`<label data-dual hidden>Niedertarif NT brutto (ct/kWh)<input name="low_ct" type="number" step=".001" min="-500" max="1000" required disabled></label><label data-dual hidden>NT beginnt um<input name="low_start" type="time" step="900" value="22:00" required disabled></label><label data-dual hidden>NT endet um<input name="low_end" type="time" step="900" value="06:00" required disabled></label><label data-dual hidden>Samstag und Sonntag<select name="weekend_low" disabled><option value="false">Gleiche Uhrzeiten wie werktags</option><option value="true">Ganztägig NT</option></select></label>`);
  const note=document.createElement('p');note.className='copy-footnote';note.textContent='HT gilt außerhalb des NT-Zeitfensters. Europe/Berlin, Viertelstundenraster, auch über Mitternacht. Feiertage werden nicht gesondert erkannt. Dies ist eine zeitliche Preiszuordnung und keine direkte T1-/T2-Abrechnung.';form.append(note);
  const change=()=>{for(const label of form.querySelectorAll('[data-dual]')){label.hidden=mode.value!=='dual';for(const input of label.querySelectorAll('input,select'))input.disabled=label.hidden;}price.disabled=mode.value==='dynamic';price.required=!price.disabled;price.parentElement.firstChild.textContent=mode.value==='dual'?'Hochtarif HT brutto (ct/kWh)':'Arbeitspreis brutto (ct/kWh)';};
  mode.addEventListener('change',change);change();
  for(const button of $$('[data-edit-tariff]'))button.addEventListener('click',()=>{const t=data.tariffs.find(row=>row.start_date===button.dataset.editTariff);if(!t)return;for(const key of ['start_date','name','mode','base_month'])form.elements[key].value=t[key];price.value=t.eur_kwh*100;form.elements.feedin_ct.value=t.feedin_eur_kwh*100;change();if(t.mode==='dual'){form.elements.low_ct.value=t.low_eur_kwh*100;form.elements.low_start.value=t.low_start;form.elements.low_end.value=t.low_end;form.elements.weekend_low.value=String(t.weekend_low);}toast('Tarif zum Bearbeiten übernommen. Speichern ersetzt dieses Anfangsdatum.');});
  mountMarket(data.market||{rows:[],fetched_at:null,error:''});
}

function mountMarket(data) {
  const stale=data.fetched_at&&Date.now()/1000-data.fetched_at>86400;
  const rows=(data.rows||[]).map(row=>`<tr><td>${esc(localTime(row.start,{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',timeZoneName:'short'}))}</td><td>${esc(localTime(row.end,{hour:'2-digit',minute:'2-digit',timeZoneName:'short'}))}</td><td>${number(row.ct_kwh,3)}</td></tr>`).join('');
  $('#page-costs').insertAdjacentHTML('beforeend',panel('Börsenpreise','Internetabruf · aWATTar DE',`<p class="muted">Netto-Börsenpreise in ct/kWh, nicht Teil der Kostenberechnung.</p><div class="form-actions"><button class="secondary" id="market-refresh" type="button"${settings.demo?' disabled':''}>Verfügbare Börsenpreise abrufen</button></div><p class="copy-footnote">${data.fetched_at?'Stand: '+esc(localTime(data.fetched_at))+(stale?' · veraltet':''):'Noch nicht abgerufen.'}</p>${data.error?`<div class="notice">${esc(data.error)}</div>`:''}${rows?`<details><summary>${data.rows.length} Preisintervalle anzeigen</summary><div class="table-wrap" style="max-height:350px;overflow:auto"><table><thead><tr><th>Beginn</th><th>Ende</th><th>Börse netto ct/kWh</th></tr></thead><tbody>${rows}</tbody></table></div></details>`:''}`));
  $('#market-refresh').addEventListener('click',safely(async event=>{const button=event.target;button.disabled=true;try{await api('/api/market/refresh','POST');toast('Börsenpreise geladen. Deine gespeicherten Vertragspreise bleiben maßgeblich.');await loadPage();}finally{button.disabled=false;}}));
}
