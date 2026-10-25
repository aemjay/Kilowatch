'use strict';

function mountDiscovery() {
  $('#page-settings .grid-main').insertAdjacentHTML('afterend',panel(t('Bridge im Heimnetz suchen'),'',`<div class="form-grid"><label>${t('Subnetz (CIDR)')}<input id="discovery-network" placeholder="z. B. 192.168.1.0/24" autocomplete="off"><small id="discovery-hint">${t('Netzvorschlag wird ermittelt …')}</small></label><label>${t('Erkannte Netzvorschläge')}<select id="discovery-suggestion"><option value="">${t('Eigenes Netz eingeben')}</option></select></label></div><div class="form-actions"><button class="secondary" id="discover-bridge" type="button"${settings.demo?' disabled':''}>${t('Im Subnetz suchen')}</button></div><div id="discovery-result" aria-live="polite"></div>`));
  const field=$('#discovery-network'),select=$('#discovery-suggestion'),hint=$('#discovery-hint'),box=$('#discovery-result');
  if(settings.demo){hint.textContent=t('Im Demo-Modus wird kein Netzwerk durchsucht.');return;}
  api('/api/discovery/network').then(data=>{if(!field.isConnected)return;for(const item of data.suggestions||[]){const option=document.createElement('option');option.value=item.network;option.textContent=`${item.network} · ${t(item.reason)}`;select.append(option);}if(data.suggestions?.length&&!field.value.trim()){field.value=data.suggestions[0].network;select.value=field.value;}hint.textContent=t('Subnetz vor dem Suchen prüfen. DHCP kann eingeschaltet bleiben.');}).catch(()=>{if(hint.isConnected)hint.textContent=t('Subnetz bitte selbst eingeben; es konnte kein Netzvorschlag ermittelt werden.');});
  select.addEventListener('change',()=>{if(select.value)field.value=select.value;});
  $('#discover-bridge').addEventListener('click',safely(async event=>{const button=event.target;if(!field.value.trim())throw new Error(t('Bitte ein lokales Subnetz eingeben.'));button.disabled=true;box.textContent=t('Suche läuft …');try{const result=await api('/api/discovery/scan','POST',{network:field.value.trim()});if(!box.isConnected)return;box.innerHTML=result.devices.length?`<p class="muted">${esc(t('{count} mögliche Bridge(s) in {network} gefunden.',{count:result.devices.length,network:result.network}))}</p><div class="table-wrap"><table><thead><tr><th>${t('Adresse')}</th><th>${t('Gerätename')}</th><th></th></tr></thead><tbody>${result.devices.map((device,index)=>`<tr><td>${esc(device.ip)}</td><td>${esc(device.fqdn||t('Kein DNS-Name erkannt'))}</td><td><button type="button" class="secondary" data-use-device="${index}">${t('Verwenden')}</button></td></tr>`).join('')}</tbody></table></div>`:`<div class="notice">${esc(t('Keine eindeutige Bridge in {network} gefunden ({checked} Adressen geprüft). Webserver, Netzmaske und Firewall prüfen oder den Gerätenamen direkt eintragen.',{network:result.network,checked:result.checked}))}</div>`;$$('[data-use-device]',box).forEach(button=>button.addEventListener('click',()=>{const device=result.devices[Number(button.dataset.useDevice)];$('#settings-form [name="bridge_host"]').value=device.host;toast(device.fqdn?t('Gerätename übernommen. Zugangsdaten eingeben und Verbindung prüfen.'):t('Adresse übernommen. Für DHCP bei Bedarf den DNS-Namen aus dem Router einsetzen.'));}));}finally{button.disabled=false;}}));
}

function tariffExtraValues(values) {
  return values.mode==='dual'?{low_eur_kwh:Number(values.low_ct)/100,low_start:values.low_start,low_end:values.low_end,weekend_low:values.weekend_low==='true'}:{};
}

function tariffRateLabel(tariff) {
  if(tariff.mode==='dual')return esc(`${unit(tariff.eur_kwh*100,'ct',2)} HT / ${unit(tariff.low_eur_kwh*100,'ct',2)} NT · NT ${tariff.low_start}–${tariff.low_end}${tariff.weekend_low?' + '+t('Wochenende'):''}`);
  return tariff.mode==='fixed'?unit(tariff.eur_kwh*100,'ct',2):t('CSV-Bruttopreise');
}

function mountTariffOptions(data) {
  const form=$('#tariff-form'),mode=form.elements.mode,price=form.elements.ct_kwh;
  mode.options[0].textContent=t('1 Tarifstufe · ein Preis');
  const dual=document.createElement('option');dual.value='dual';dual.textContent=t('2 Tarifstufen · HT/NT');mode.add(dual,1);
  mode.options[2].textContent=t('Variabel · vollständige Preise per CSV');
  price.value='';price.placeholder=t('Dein Bruttopreis');
  form.querySelector('.form-grid').insertAdjacentHTML('beforeend',`<label data-dual hidden>${t('Niedertarif NT brutto (ct/kWh)')}<input name="low_ct" type="number" step=".001" min="-500" max="1000" required disabled></label><label data-dual hidden>${t('NT beginnt um')}<input name="low_start" type="time" step="900" value="22:00" required disabled></label><label data-dual hidden>${t('NT endet um')}<input name="low_end" type="time" step="900" value="06:00" required disabled></label><label data-dual hidden>${t('Samstag und Sonntag')}<select name="weekend_low" disabled><option value="false">${t('Gleiche Uhrzeiten wie werktags')}</option><option value="true">${t('Ganztägig NT')}</option></select></label>`);
  const note=document.createElement('p');note.className='copy-footnote';note.textContent=t('HT gilt außerhalb des NT-Zeitfensters. Europe/Berlin, Viertelstundenraster, auch über Mitternacht. Feiertage werden nicht gesondert erkannt. Dies ist eine zeitliche Preiszuordnung und keine direkte T1-/T2-Abrechnung.');form.append(note);
  const change=()=>{for(const label of form.querySelectorAll('[data-dual]')){label.hidden=mode.value!=='dual';for(const input of label.querySelectorAll('input,select'))input.disabled=label.hidden;}price.disabled=mode.value==='dynamic';price.required=!price.disabled;price.parentElement.firstChild.textContent=mode.value==='dual'?t('Hochtarif HT brutto (ct/kWh)'):t('Arbeitspreis brutto (ct/kWh)');};
  mode.addEventListener('change',change);change();
  for(const button of $$('[data-edit-tariff]'))button.addEventListener('click',()=>{const tariff=data.tariffs.find(row=>row.start_date===button.dataset.editTariff);if(!tariff)return;for(const key of ['start_date','name','mode','base_month'])form.elements[key].value=tariff[key];price.value=tariff.eur_kwh*100;form.elements.feedin_ct.value=tariff.feedin_eur_kwh*100;change();if(tariff.mode==='dual'){form.elements.low_ct.value=tariff.low_eur_kwh*100;form.elements.low_start.value=tariff.low_start;form.elements.low_end.value=tariff.low_end;form.elements.weekend_low.value=String(tariff.weekend_low);}toast(t('Tarif zum Bearbeiten übernommen. Speichern ersetzt dieses Anfangsdatum.'));});
  // Börsenpreise kommen von aWATTar DE in Euro; bei anderer Währung nicht neben eigenen Preisen zeigen.
  if(CURRENCY===CURRENCIES.EUR)mountMarket(data.market||{rows:[],fetched_at:null,error:''});
}

function mountMarket(data) {
  const stale=data.fetched_at&&Date.now()/1000-data.fetched_at>86400;
  const rows=(data.rows||[]).map(row=>`<tr><td>${esc(localTime(row.start,{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',timeZoneName:'short'}))}</td><td>${esc(localTime(row.end,{hour:'2-digit',minute:'2-digit',timeZoneName:'short'}))}</td><td>${number(row.ct_kwh,3)}</td></tr>`).join('');
  $('#page-costs').insertAdjacentHTML('beforeend',panel(t('Börsenpreise'),t('Internetabruf · aWATTar DE'),`<p class="muted">${t('Netto-Börsenpreise in ct/kWh, nicht Teil der Kostenberechnung.')}</p><div class="form-actions"><button class="secondary" id="market-refresh" type="button"${settings.demo?' disabled':''}>${t('Verfügbare Börsenpreise abrufen')}</button></div><p class="copy-footnote">${data.fetched_at?t('Stand: ')+esc(localTime(data.fetched_at))+(stale?t(' · veraltet'):''):t('Noch nicht abgerufen.')}</p>${data.error?`<div class="notice">${esc(data.error)}</div>`:''}${rows?`<details><summary>${t('{count} Preisintervalle anzeigen',{count:data.rows.length})}</summary><div class="table-wrap" style="max-height:350px;overflow:auto"><table><thead><tr><th>${t('Beginn')}</th><th>${t('Ende')}</th><th>${t('Börse netto ct/kWh')}</th></tr></thead><tbody>${rows}</tbody></table></div></details>`:''}`));
  $('#market-refresh').addEventListener('click',safely(async event=>{const button=event.target;button.disabled=true;try{await api('/api/market/refresh','POST');toast(t('Börsenpreise geladen. Deine gespeicherten Vertragspreise bleiben maßgeblich.'));await loadPage();}finally{button.disabled=false;}}));
}
