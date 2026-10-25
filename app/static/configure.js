'use strict';

function renderInitialSetup() {
  $('#application').hidden=true;$('#login').hidden=false;
  $('#login-form').hidden=true;$('#first-start-form').hidden=false;
}

function bridgeFormValues() {
  const data=Object.fromEntries(new FormData($('#settings-form')));
  for(const name of ['node_id','poll_seconds','high_load_w','raw_retention_days','minute_retention_days','max_gap_seconds','max_power_w'])data[name]=Number(data[name]);
  data.enabled=data.enabled==='true';
  if(!data.bridge_password)delete data.bridge_password;
  return data;
}

function localeForm() {
  const currencies=Object.keys(CURRENCIES).map(code=>`<option value="${code}"${code===CURRENCY_CODE?' selected':''}>${code}</option>`).join('');
  return `<form id="locale-form"><div class="form-grid"><label>${t('Sprache')}<select name="language">${languageOptions(LANGUAGE)}</select></label><label>${t('Währung')}<select name="currency">${currencies}</select><small>${t('Nur das Zeichen ändert sich; Beträge werden nicht umgerechnet. Börsenpreise gibt es nur für Euro.')}</small></label></div><div class="form-actions"><button class="secondary" type="submit">${t('Übernehmen')}</button></div></form>`;
}

function gridForm() {
  const options=[['',t('Aus')],...Object.entries(GRID_COUNTRIES).map(([code,name])=>[code,t(name)])].map(([code,name])=>`<option value="${code}"${code===(settings.grid_country||'')?' selected':''}>${esc(name)}</option>`).join('');
  return `<form id="grid-form"><div class="form-grid"><label>${t('Land deines Stromnetzes')}<select name="grid_country">${options}</select><small>${t('Stündlich werden CO₂-Intensität und Ökostromanteil des Netzes abgerufen. Gesendet werden nur Land und Zeitraum, keine Messwerte.')}</small></label></div><div class="form-actions"><button class="secondary" type="submit">${t('Übernehmen')}</button></div></form>`;
}

function householdForm() {
  const persons=[[0,t('Keine Vergleichswerte')],...[1,2,3,4,5].map(n=>[n,n===5?t('5 und mehr'):String(n)])].map(([n,label])=>`<option value="${n}"${n===(settings.household_persons||0)?' selected':''}>${esc(label)}</option>`).join('');
  const types=[['apartment',t('Wohnung (Mehrfamilienhaus)')],['house',t('Haus (Ein-/Zweifamilienhaus)')]].map(([v,label])=>`<option value="${v}"${v===(settings.household_type||'apartment')?' selected':''}>${esc(label)}</option>`).join('');
  return `<form id="household-form"><div class="form-grid"><label>${t('Personen im Haushalt')}<select name="household_persons">${persons}</select></label><label>${t('Wohnform')}<select name="household_type">${types}</select></label><label>${t('Warmwasser')}<select name="household_hot_water"><option value="false"${settings.household_hot_water?'':' selected'}>${t('Nicht elektrisch (z. B. Gas, Fernwärme)')}</option><option value="true"${settings.household_hot_water?' selected':''}>${t('Elektrisch (Durchlauferhitzer, Boiler)')}</option></select></label></div><p class="copy-footnote">${t('Vergleichswerte aus dem Stromspiegel für Deutschland (co2online, Stand 05/2025). Elektrische Heizung, Wärmepumpe und E-Auto sind darin nicht enthalten; in Norwegen und Schweden sind sie daher wenig aussagekräftig.')}</p><div class="form-actions"><button class="secondary" type="submit">${t('Übernehmen')}</button></div></form>`;
}

function mountLocaleForm() {
  $('#household-form').addEventListener('submit',safely(async event=>{
    event.preventDefault();const v=Object.fromEntries(new FormData(event.target));
    await api('/api/settings','PUT',{household_persons:Number(v.household_persons),household_type:v.household_type,household_hot_water:v.household_hot_water==='true'});
    settings=await api('/api/settings');toast(t('Haushaltsangaben gespeichert.'));
  }));
  $('#grid-form').addEventListener('submit',safely(async event=>{
    event.preventDefault();await api('/api/settings','PUT',Object.fromEntries(new FormData(event.target)));
    settings=await api('/api/settings');toast(t('Strommix-Einstellung gespeichert.'));
  }));
  $('#locale-form').addEventListener('submit',safely(async event=>{
    event.preventDefault();const data=Object.fromEntries(new FormData(event.target));
    await setLanguage(data.language);await api('/api/settings','PUT',data);
    settings=await api('/api/settings');setCurrency(settings.currency);
    toast(t('Sprache und Währung gespeichert.'));await navigate('settings');
  }));
}

function renderSettings() {
  const first=settings.setup_required&&!settings.demo;
  const intro=first?`<div class="notice info"><strong>${t('Ersteinrichtung · Schritt 2 von 2')}</strong></div>`:'';
  const form=`${intro}<form id="settings-form"><div class="form-grid"><label>${t('Name deines Zuhauses')}<input name="name" value="${esc(settings.name)}" maxlength="80" required></label><label>${t('Bridge-Adresse: FQDN oder IP')}<input name="bridge_host" value="${esc(settings.bridge_host)}" placeholder="${esc(t('z. B. tibber-bridge.fritz.box'))}" autocomplete="off" required><small>${t('Ohne http://, Port oder Pfad.')}</small></label><label>${t('Bridge-Passwort')}<input name="bridge_password" type="password" autocomplete="new-password" ${settings.password_configured?'':'required'} placeholder="${settings.password_configured?t('Gespeichert · leer lassen zum Beibehalten'):t('Kennung vom Bridge-Aufkleber, z. B. ABCD-EFGH')}"></label><label>Node-ID<input name="node_id" type="number" min="1" max="64" value="${settings.node_id}" required></label><label>${t('Erfassung')}<select name="enabled"><option value="true"${settings.enabled?' selected':''}>${t('Aktiv')}</option><option value="false"${settings.enabled?'':' selected'}>${t('Pausiert / Wartung')}</option></select></label></div><details class="advanced-settings"${first?'':' open'}><summary>${t('Erweitert')}</summary><div class="form-grid"><label>${t('Bridge-Benutzer')}<input name="bridge_user" value="${esc(settings.bridge_user||'admin')}" autocomplete="off" required></label><label>${t('Abfrageintervall (Sekunden)')}<input name="poll_seconds" type="number" min="2" max="60" value="${settings.poll_seconds}" required></label><label>${t('Schwelle Lastanalyse (W)')}<input name="high_load_w" type="number" min="100" max="100000" value="${settings.high_load_w}" required></label><label>${t('Einzelwerte aufbewahren (Tage)')}<input name="raw_retention_days" type="number" min="0" max="3650" value="${settings.raw_retention_days}" required><small>${t('0 = unbegrenzt.')}</small></label><label>${t('Minutenwerte aufbewahren (Tage)')}<input name="minute_retention_days" type="number" min="0" max="10000" value="${settings.minute_retention_days}" required></label><label>${t('Normales Messintervall bis (Sekunden)')}<input name="max_gap_seconds" type="number" min="15" max="300" value="${settings.max_gap_seconds}" required></label><label>${t('Plausibilitätsgrenze (W)')}<input name="max_power_w" type="number" min="1000" max="1000000" value="${settings.max_power_w}" required></label></div></details><div class="form-actions"><button class="primary" type="submit">${first?t('Bridge speichern und starten'):t('Einstellungen speichern')}</button><button class="secondary" type="button" id="test-bridge">${t('Verbindung prüfen')}</button></div><div class="inline-result" id="bridge-result" hidden></div></form>`;
  const connection=`<div class="stats-list">${stat(t('Gerätename'),settings.bridge_host||t('Noch nicht eingegeben'))}${stat(t('Aktuell aufgelöste Adresse'),(live.collector?.resolved_addresses||[]).join(', ')||t('Nach Verbindungstest verfügbar'))}${stat(t('Zugangsdaten'),settings.password_configured?t('Gespeichert'):t('Fehlen'))}</div><div class="divider"></div><div class="form-actions"><button class="secondary" id="configure-alerts">${t('Benachrichtigungen einrichten')}</button></div>`;
  const account=`<form id="password-form"><div class="form-grid"><label>${t('Aktuelles App-Passwort')}<input name="current_password" type="password" autocomplete="current-password" required></label><label>${t('Neues App-Passwort')}<input name="new_password" type="password" autocomplete="new-password" minlength="12" maxlength="500" required></label><label>${t('Neues Passwort wiederholen')}<input name="confirmation" type="password" autocomplete="new-password" minlength="12" maxlength="500" required></label></div><div class="form-actions"><button class="secondary" type="submit">${t('App-Passwort ändern und abmelden')}</button></div></form>`;
  $('#page-settings').innerHTML=`<div class="grid-main"><div>${panel(first?t('Deine Bridge verbinden.'):t('Verbindung und Zugangsdaten.'),t('Jederzeit änderbar · ohne mitgelieferte persönliche Daten.'),form)}</div><div>${panel(t('Verbindung'),'',connection)}</div></div>`+panel(t('Sprache und Währung'),t('Gilt für die Oberfläche und für Benachrichtigungen.'),localeForm())+panel(t('Strommix und CO₂'),t('Optional · Internetabruf bei Energy-Charts.info'),gridForm())+panel(t('Dein Haushalt'),t('Optional · für Vergleichswerte typischer Haushalte'),householdForm())+panel(t('App-Passwort'),'',account)+panel(t('Bridge-Zugang entfernen'),t('Pausiert die Erfassung, Historie bleibt.'),`<button id="forget-bridge" class="danger-button">${t('Gespeichertes Bridge-Passwort entfernen')}</button>`);
  $('#settings-form').addEventListener('submit',safely(async event=>{event.preventDefault();await api('/api/settings','PUT',bridgeFormValues());settings=await api('/api/settings');$('#home-name').textContent=t(settings.name);toast(t('Bridge-Einstellungen gespeichert.'));if(first&&!settings.setup_required){await navigate('dashboard');}else{renderSettings();}}));
  $('#test-bridge').addEventListener('click',safely(async event=>{const form=$('#settings-form');if(!form.reportValidity())return;const button=event.target;button.disabled=true;try{const result=await api('/api/bridge/test','POST',bridgeFormValues());const box=$('#bridge-result');box.hidden=false;box.textContent=[t('Verbindung erfolgreich · {protocol}',{protocol:result.protocol}),t('Adresse: {address} · Datenpfad: {endpoint}',{address:(result.resolved_addresses||[]).join(', ')||'Demo',endpoint:result.endpoint}),t('Bezug: {import} · Einspeisung: {export} · Leistung: {power}',{import:result.has_import?t('ja'):t('nein'),export:result.has_export?t('ja'):t('nein'),power:result.has_power?t('ja'):t('nein')}),t('Anschließend speichern, um diese Daten für die Erfassung zu verwenden.')].join('\n');}finally{button.disabled=false;}}));
  $('#configure-alerts').addEventListener('click',()=>navigate('notifications'));
  mountLocaleForm();
  $('#password-form').addEventListener('submit',safely(async event=>{event.preventDefault();const values=Object.fromEntries(new FormData(event.target));if(values.new_password!==values.confirmation)throw new Error(t('Die neuen Passwörter stimmen nicht überein.'));delete values.confirmation;await api('/api/account/password','PUT',values);event.target.reset();showLogin();toast(t('App-Passwort geändert. Bitte neu anmelden.'));}));
  $('#forget-bridge').addEventListener('click',safely(async()=>{await api('/api/credentials/bridge','DELETE');settings=await api('/api/settings');toast(t('Bridge-Passwort entfernt. Erfassung pausiert.'));renderSettings();}));
  mountDiscovery();
}

function choice(name,label,value,on=t('Aktiv'),off=t('Aus')) {return `<label>${esc(label)}<select name="${name}"><option value="false"${value?'':' selected'}>${esc(off)}</option><option value="true"${value?' selected':''}>${esc(on)}</option></select></label>`;}
function numeric(name,label,value,min,max,step='1'){return `<label>${esc(label)}<input name="${name}" type="number" min="${min}" max="${max}" step="${step}" value="${value}" required></label>`;}

function notificationFormValues() {
  const values=Object.fromEntries(new FormData($('#notification-form')));
  for(const key of ['enabled','email_enabled','quiet_enabled','recovery','offline_enabled','load_enabled','battery_enabled','disk_enabled','budget_enabled','clear_smtp_password'])values[key]=values[key]==='true';
  for(const key of ['smtp_port','cooldown_minutes','offline_seconds','load_w','load_minutes','daily_kwh','battery_v','disk_free_mb'])values[key]=Number(values[key]);
  for(const key of ['email_to'])values[key]=values[key].split(/[;,\s]+/).map(v=>v.trim()).filter(Boolean);
  if(!values.smtp_password)delete values.smtp_password;
  return values;
}

function renderNotifications(data) {
  const n=data.settings;
  const master=`<div class="form-grid">${choice('enabled',t('Automatische Benachrichtigungen'),n.enabled)}${choice('recovery',t('Wiederkehr / Normalzustand melden'),n.recovery)}${numeric('cooldown_minutes',t('Mindestabstand je Alarm (Minuten)'),n.cooldown_minutes,5,1440)}${choice('quiet_enabled',t('Ruhezeiten'),n.quiet_enabled)}<label>${t('Ruhezeit ab')}<input name="quiet_start" type="time" value="${n.quiet_start}" required></label><label>${t('Ruhezeit bis')}<input name="quiet_end" type="time" value="${n.quiet_end}" required></label></div>`;
  const email=`<div class="form-grid">${choice('email_enabled',t('E-Mail als Kanal'),n.email_enabled)}<label>SMTP-Server<input name="smtp_host" value="${esc(n.smtp_host)}" placeholder="${esc(t('smtp.dein-anbieter.de'))}" autocomplete="off"></label>${numeric('smtp_port','SMTP-Port',n.smtp_port,1,65535)}<label>${t('Verschlüsselung')}<select name="smtp_security"><option value="starttls"${n.smtp_security==='starttls'?' selected':''}>${t('STARTTLS (z. B. Port 587)')}</option><option value="ssl"${n.smtp_security==='ssl'?' selected':''}>${t('Direktes TLS (z. B. Port 465)')}</option></select></label><label>${t('SMTP-Benutzer')}<input name="smtp_user" value="${esc(n.smtp_user)}" autocomplete="off"></label><label>${t('SMTP-Passwort / App-Passwort')}<input name="smtp_password" type="password" autocomplete="new-password" placeholder="${data.smtp_password_configured?t('Gespeichert · leer lassen zum Beibehalten'):t('Noch nicht hinterlegt')}"></label><label>${t('Absenderadresse')}<input name="smtp_from" type="email" value="${esc(n.smtp_from)}"></label><label>${t('Absendername')}<input name="smtp_from_name" value="${esc(n.smtp_from_name)}" maxlength="80" placeholder="Kilowatch" autocomplete="off"></label><label>${t('Erkennungswort im Betreff')}<input name="subject_code" value="${esc(n.subject_code)}" maxlength="40" placeholder="${esc(t('z. B. Kuckuck-17'))}" autocomplete="off"><small>${t('Steht in jedem Betreff. Mails ohne dieses Wort stammen nicht von Kilowatch.')}</small></label><label>${t('Empfänger (bis zu 5)')}<textarea name="email_to" rows="2" placeholder="${esc(t('Eine Adresse je Zeile'))}">${esc(n.email_to.join('\n'))}</textarea></label>${choice('clear_smtp_password',t('Gespeichertes SMTP-Passwort entfernen'),false,t('Beim Speichern entfernen'),t('Beibehalten'))}</div><div class="form-actions"><button type="button" class="secondary" id="test-email">${t('Speichern & E-Mail-Test senden')}</button></div>`;
  const rules=`<div class="form-grid">${choice('offline_enabled',t('Keine frischen Zählerdaten melden'),n.offline_enabled)}${numeric('offline_seconds',t('Ausfall erst nach (Sekunden)'),n.offline_seconds,30,3600)}${choice('load_enabled',t('Hohe Dauerlast melden'),n.load_enabled)}${numeric('load_w',t('Grenze Dauerlast (W)'),n.load_w,100,1000000)}${numeric('load_minutes',t('Dauerlast mindestens (Minuten)'),n.load_minutes,1,240)}${numeric('daily_kwh',t('Tagesbudget Bezug (kWh; 0 = aus)'),n.daily_kwh,0,10000,'.1')}${choice('budget_enabled',t('Monatsbudget erreicht melden'),n.budget_enabled)}${choice('battery_enabled',t('Niedrige Batteriespannung melden'),n.battery_enabled)}${numeric('battery_v',t('Batterieschwelle (V)'),n.battery_v,1,5,'.05')}${choice('disk_enabled',t('Knappen Datenspeicher melden'),n.disk_enabled)}${numeric('disk_free_mb',t('Hinweis unter freiem Speicher (MiB)'),n.disk_free_mb,100,100000)}</div>`;
  const statuses={sent:t('Gesendet'),pending:t('Wartet'),failed:t('Fehlgeschlagen'),cancelled:t('Verworfen')};
  const history=data.history.length?`<div class="table-wrap"><table><thead><tr><th>${t('Zeit')}</th><th>${t('Kanal')}</th><th>${t('Meldung')}</th><th>${t('Zustellung')}</th><th>${t('Hinweis')}</th></tr></thead><tbody>${data.history.map(item=>`<tr><td>${esc(localTime(item.created))}</td><td>${item.channel==='email'?'E-Mail':esc(item.channel)}</td><td>${esc(item.subject)}</td><td>${esc(statuses[item.status]||item.status)}</td><td>${esc(item.last_error||'')}</td></tr>`).join('')}</tbody></table></div>`:empty(t('Noch keine Nachrichten.'),t('Speichere einen Kanal und sende bei Bedarf eine Testnachricht.'));
  $('#page-notifications').innerHTML=(settings.demo?`<div class="notice info">${t('Demo-Modus: Es werden keine externen Nachrichten versendet.')}</div>`:'')+(data.last_error?`<div class="notice">${esc(data.last_error)}</div>`:'')+`<form id="notification-form">${panel(t('Benachrichtigungen'),'',master)}${panel('E-Mail','',email)}${panel(t('Alarmregeln'),'',rules)}<div class="form-actions notification-save"><button class="primary" type="submit">${t('Benachrichtigungen speichern')}</button></div></form><div class="section-space">${panel(t('Zustellverlauf'),'',history)}</div>`;
  async function save(){if(!$('#notification-form').reportValidity())throw new Error(t('Bitte Eingaben prüfen.'));await api('/api/notifications','PUT',notificationFormValues());}
  $('#notification-form').addEventListener('submit',safely(async event=>{event.preventDefault();await save();toast(t('Benachrichtigungen gespeichert.'));await loadPage();}));
  for(const channel of ['email'])$('#test-'+channel).addEventListener('click',safely(async event=>{const button=event.target;button.disabled=true;try{await save();await api('/api/notifications/test/'+channel,'POST');toast(t('Testnachricht an den konfigurierten Kanal übergeben.'));await loadPage();}finally{button.disabled=false;}}));
}
