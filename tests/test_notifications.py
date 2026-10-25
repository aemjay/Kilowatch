import asyncio
from datetime import datetime
from types import SimpleNamespace
import smtplib

import pytest

from app.decoder import Reading
from app.notifications import NotificationSettings, quiet_now, send_email


def email_config(**extra):
    return {"enabled":True,"email_enabled":True,"smtp_host":"smtp.example.org","smtp_from":"sender@example.org","email_to":["recipient@example.org"],"battery_enabled":False,"disk_enabled":False,**extra}


def test_settings_mask_passwords_and_store_encrypted(authenticated):
    data=email_config(smtp_password="synthetic-mail-secret")
    assert authenticated.put("/api/notifications",json=data).status_code==200
    response=authenticated.get("/api/notifications")
    assert response.json()["smtp_password_configured"]
    assert "synthetic-mail-secret" not in response.text
    assert "synthetic-mail-secret" not in str(authenticated.app_store.state("notification_settings"))
    assert b"synthetic-mail-secret" not in authenticated.app.state.vault.path.read_bytes()


@pytest.mark.parametrize("extra",[{"smtp_security":"none"},{"email_to":["bad\r\nBcc: ex@example.org"]},{"quiet_start":"25:60"}])
def test_invalid_or_insecure_settings_rejected(authenticated,extra):
    assert authenticated.put("/api/notifications",json=email_config(**extra)).status_code==422


class FakeSMTP:
    calls=[]
    def __init__(self,*args,**kwargs):
        self.calls.clear()
    def __enter__(self):
        return self
    def __exit__(self,*args):
        pass
    def ehlo(self):
        self.calls.append("ehlo")
    def starttls(self,context):
        assert context.check_hostname
        self.calls.append("tls")
    def login(self,user,password):
        self.calls.append("login")
        assert password=="synthetic-mail-secret"
    def send_message(self,message):
        self.calls.append("send")
        assert message["To"]=="recipient@example.org"


def test_smtp_login_only_after_verified_tls(monkeypatch):
    monkeypatch.setattr(smtplib,"SMTP",FakeSMTP)
    config=NotificationSettings(**email_config(smtp_user="synthetic-user"))
    send_email(config,"synthetic-mail-secret","Synthetic test","No real message")
    assert FakeSMTP.calls==["ehlo","tls","ehlo","login","send"]


def test_smtp_does_not_fallback_to_plaintext(monkeypatch):
    class NoTLS(FakeSMTP):
        def starttls(self,context):
            raise smtplib.SMTPNotSupportedError()
    monkeypatch.setattr(smtplib,"SMTP",NoTLS)
    with pytest.raises(ValueError,match="TLS"):
        send_email(NotificationSettings(**email_config(smtp_user="user")),"synthetic-mail-secret","test","test")
    assert "login" not in FakeSMTP.calls


def test_test_message_is_explicit_rate_limited_and_not_automatic(authenticated,monkeypatch):
    assert authenticated.put("/api/notifications",json=email_config(smtp_user="user",smtp_password="synthetic-mail-secret",enabled=False)).status_code==200
    monkeypatch.setattr(smtplib,"SMTP",FakeSMTP)
    assert authenticated.post("/api/notifications/test/email").status_code==200
    assert authenticated.post("/api/notifications/test/email").status_code==400
    history=authenticated.get("/api/notifications").json()["history"]
    assert len(history)==1 and history[0]["status"]=="sent"


@pytest.mark.parametrize("stamp,expected",[("2026-10-25T02:30:00+02:00",True),("2026-10-25T02:30:00+01:00",True),("2026-10-25T08:00:00+01:00",False)])
def test_quiet_hours_also_cover_repeated_dst_hour(stamp,expected):
    config=NotificationSettings(quiet_enabled=True,quiet_start="22:00",quiet_end="07:00")
    assert quiet_now(config,datetime.fromisoformat(stamp).timestamp(),"Europe/Berlin")==expected


def prepare_engine(client,monkeypatch,**extra):
    engine=client.app.state.notifier
    engine.save(NotificationSettings(**email_config(**extra)))
    client.app_store.update_settings({"bridge_host":"bridge.fritz.box","bridge_user":"synthetic-user"})
    client.app.state.vault.update({"bridge_password":"synthetic-password"})
    monkeypatch.setattr("app.notifications.shutil.disk_usage",lambda _:SimpleNamespace(free=10*1024**3))
    return engine


def test_outage_once_and_recovery_only_after_sent_alert(authenticated,monkeypatch):
    engine=prepare_engine(authenticated,monkeypatch)
    now=2000000000
    engine.started=now-200
    messages=[]
    async def fake_send(*args):
        messages.append(args[1])
    monkeypatch.setattr(engine,"send",fake_send)
    engine.evaluate(now)
    engine.evaluate(now+10)
    assert len(authenticated.app_store.rows("SELECT * FROM notifications"))==1
    asyncio.run(engine.dispatch(now+10))
    authenticated.app_store.ingest(Reading(500,100,0,"SYNTHETIC"),now+20)
    engine.evaluate(now+20)
    asyncio.run(engine.dispatch(now+20))
    assert len(messages)==2
    assert "Wieder in Ordnung" in messages[-1]


def test_outage_resolved_before_delivery_is_silently_cancelled(authenticated,monkeypatch):
    engine=prepare_engine(authenticated,monkeypatch)
    now=2000000000
    engine.started=now-200
    engine.evaluate(now)
    authenticated.app_store.ingest(Reading(100,100,0,"SYNTHETIC"),now+5)
    engine.evaluate(now+5)
    rows=authenticated.app_store.rows("SELECT * FROM notifications")
    assert len(rows)==1 and rows[0]["status"]=="cancelled"


def test_retry_is_bounded_and_survives_restart(authenticated,monkeypatch):
    engine=prepare_engine(authenticated,monkeypatch)
    now=2000000000
    engine.started=now-200
    engine.evaluate(now)
    async def fail(*args):
        raise ValueError("synthetic delivery failure")
    monkeypatch.setattr(engine,"send",fail)
    for i in range(5):
        asyncio.run(engine.dispatch(now+i*4000))
    row=authenticated.app_store.rows("SELECT * FROM notifications")[0]
    assert row["status"]=="failed" and row["attempts"]==5
    assert engine.store.state("notification_rules")["offline"]["active"]


def test_high_load_requires_configured_duration(authenticated,monkeypatch):
    engine=prepare_engine(authenticated,monkeypatch,load_enabled=True,load_minutes=1,load_w=3000)
    now=2000000000
    engine.started=now
    for offset in [0,20,40,60]:
        authenticated.app_store.ingest(Reading(4000,None,None,"SYNTHETIC"),now+offset)
        engine.evaluate(now+offset)
    rows=authenticated.app_store.rows("SELECT * FROM notifications WHERE rule_key='load'")
    assert len(rows)==1


def test_no_alarms_for_paused_or_unconfigured_collector(authenticated,monkeypatch):
    engine=prepare_engine(authenticated,monkeypatch)
    engine.started=0
    authenticated.app_store.update_settings({"enabled":False})
    engine.evaluate(2000000000)
    assert not authenticated.app_store.rows("SELECT * FROM notifications")


def test_changing_channel_config_cancels_old_recipients_queue(authenticated,monkeypatch):
    engine=prepare_engine(authenticated,monkeypatch)
    engine.started=0
    engine.evaluate(2000000000)
    engine.save(NotificationSettings())
    assert all(r["status"]=="cancelled" for r in engine.store.rows("SELECT * FROM notifications"))


def test_saving_unchanged_config_does_not_repeat_alarm(authenticated,monkeypatch):
    engine=prepare_engine(authenticated,monkeypatch)
    engine.started=0
    now=2000000000
    engine.evaluate(now)
    engine.save(engine.config())
    engine.evaluate(now+10)
    rows=engine.store.rows("SELECT * FROM notifications")
    assert len(rows)==1 and rows[0]["status"]=="pending"


def test_measurement_gap_does_not_prove_continuous_high_load(authenticated,monkeypatch):
    engine=prepare_engine(authenticated,monkeypatch,load_enabled=True,load_minutes=1,load_w=3000)
    now=2000000000
    engine.started=now
    authenticated.app_store.ingest(Reading(4000,None,None,"SYNTHETIC"),now)
    engine.evaluate(now)
    engine.evaluate(now+40)
    authenticated.app_store.ingest(Reading(4000,None,None,"SYNTHETIC"),now+80)
    engine.evaluate(now+80)
    assert not engine.store.rows("SELECT * FROM notifications WHERE rule_key='load'")


def test_settings_from_versions_with_signal_still_load_and_leftovers_are_removed(tmp_path):
    from app.config import Config
    from app.main import create_app
    app=create_app(Config(tmp_path,testing=True))
    store,vault=app.state.store,app.state.vault
    store.set_state("notification_settings",{**email_config(),"signal_enabled":True,"signal_url":"http://signal-api:8080","signal_number":"+49301234567","signal_to":[]})
    vault.update({"signal_token":"old-token","smtp_password":"kept"})
    with store.transaction():
        store.conn.execute("INSERT INTO notifications(rule_key,kind,channel,subject,body,status,created,next_try) VALUES('offline','alert','signal','s','b','pending',1,1)")
    store.close()
    app=create_app(Config(tmp_path,testing=True))
    assert app.state.notifier.config().smtp_host=="smtp.example.org"
    assert app.state.vault.get("signal_token",None) is None and app.state.vault.get("smtp_password")=="kept"
    assert app.state.store.rows("SELECT status FROM notifications WHERE channel='signal'")[0]["status"]=="cancelled"
    app.state.store.close()


def test_signal_endpoints_and_fields_are_gone(authenticated):
    assert authenticated.post("/api/notifications/test/signal").status_code==400
    assert authenticated.post("/api/notifications/signal/qr").status_code in (404,405)
    assert authenticated.put("/api/notifications",json={"signal_url":"http://signal-api:8080"}).status_code==422
    assert "signal_token_configured" not in authenticated.get("/api/notifications").json()


def test_disabling_rule_cancels_pending_alert_without_fresh_measurement(authenticated,monkeypatch):
    engine=prepare_engine(authenticated,monkeypatch,load_enabled=True,load_minutes=1)
    now=2000000000
    engine.started=now
    for offset in [0,20,40,60]:
        engine.store.ingest(Reading(4000,None,None,"SYNTHETIC"),now+offset)
        engine.evaluate(now+offset)
    assert engine.store.rows("SELECT * FROM notifications WHERE rule_key='load'")[0]["status"]=="pending"
    engine.save(engine.config().model_copy(update={"load_enabled":False}))
    assert engine.store.rows("SELECT * FROM notifications WHERE rule_key='load'")[0]["status"]=="cancelled"


def test_load_below_threshold_restarts_delay_before_first_alarm(authenticated,monkeypatch):
    engine=prepare_engine(authenticated,monkeypatch,load_enabled=True,load_minutes=1,load_w=3000)
    now=2000000000
    engine.started=now
    for offset,power in [(0,4000),(20,2900),(40,4000),(60,4000),(80,4000)]:
        engine.store.ingest(Reading(power,None,None,"SYNTHETIC"),now+offset)
        engine.evaluate(now+offset)
    assert not engine.store.rows("SELECT * FROM notifications WHERE rule_key='load'")
    engine.store.ingest(Reading(4000,None,None,"SYNTHETIC"),now+100)
    engine.evaluate(now+100)
    assert len(engine.store.rows("SELECT * FROM notifications WHERE rule_key='load'"))==1


def test_restart_grace_does_not_emit_false_outage_recovery(authenticated,monkeypatch):
    engine=prepare_engine(authenticated,monkeypatch)
    now=2000000000
    engine.started=now-200
    engine.evaluate(now)
    engine.rule_state["offline"]["notified"]=["email"]
    engine.store.set_state("notification_rules",engine.rule_state)
    from app.notifications import Notifications
    restarted=Notifications(engine.store,engine.vault,engine.collector)
    restarted.started=now+20
    restarted.evaluate(now+20)
    assert restarted.rule_state["offline"]["active"]
    assert not engine.store.rows("SELECT * FROM notifications WHERE kind='recovery'")
    engine.store.ingest(Reading(500,100,0,"SYNTHETIC"),now+25)
    restarted.evaluate(now+25)
    assert engine.store.rows("SELECT * FROM notifications WHERE kind='recovery'")


def test_monthly_budget_alert_once_per_month(authenticated,monkeypatch):
    from app.demo import seed
    from app.analytics import midnight
    now=midnight("2026-10-20","Europe/Berlin")+12*3600
    seed(authenticated.app_store,now)
    engine=prepare_engine(authenticated,monkeypatch,offline_enabled=False,battery_enabled=False,disk_enabled=False)
    authenticated.app_store.set_state("budget",{"monthly_eur":5})
    engine.evaluate(now)
    assert not authenticated.app_store.rows("SELECT * FROM notifications WHERE rule_key LIKE 'budget:%'")
    engine.save(NotificationSettings(**email_config(offline_enabled=False,battery_enabled=False,disk_enabled=False,budget_enabled=True)))
    engine.evaluate(now)
    engine.evaluate(now+60)
    alerts=authenticated.app_store.rows("SELECT * FROM notifications WHERE rule_key='budget:2026-10'")
    assert len(alerts)==1 and "Monatsbudget" in alerts[0]["subject"]


def test_sender_name_and_subject_code(authenticated,monkeypatch):
    sent=[]
    class Capture(FakeSMTP):
        def send_message(self,message):
            sent.append(message)
    monkeypatch.setattr(smtplib,"SMTP",Capture)
    config=NotificationSettings(**email_config(smtp_from_name="Stromzähler Müller"))
    send_email(config,"","Betreff","Text")
    assert sent[-1]["From"].addresses[0].display_name=="Stromzähler Müller"
    assert "=?utf-8?" in sent[-1].as_string().split("From:")[1].splitlines()[0]  # Umlaute RFC-2047-kodiert
    send_email(NotificationSettings(**email_config(smtp_from_name="")),"","Betreff","Text")
    assert str(sent[-1]["From"])=="sender@example.org"
    for bad in ({"smtp_from_name":"Evil\r\nBcc: x@example.org"},{"subject_code":"a\nb"},{"subject_code":"x"*41}):
        assert authenticated.put("/api/notifications",json=email_config(**bad)).status_code==422
    assert authenticated.put("/api/notifications",json=email_config(subject_code="Kuckuck-17")).status_code==200
    assert authenticated.get("/api/notifications").json()["settings"]["subject_code"]=="Kuckuck-17"
    assert authenticated.post("/api/notifications/test/email").status_code==200
    assert sent[-1]["Subject"].startswith("[Kuckuck-17] Kilowatch")
