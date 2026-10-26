"""Erweiterte Auswertungen aus der Netzanschlussmessung.

Grundsätze: nur aus vorhandenen Messintervallen rechnen, Abdeckung immer mit ausgeben,
fehlende Daten nie als null behandeln und keine Geräte- oder PV-Eigenverbrauchsaussagen.
"""
import bisect
from datetime import datetime, timedelta
import math
import statistics
from zoneinfo import ZoneInfo

from .analytics import local_day, midnight

HOURS_PER_YEAR = 8766
MIN_NIGHT_QUARTERS = 24


def night_quarters(analytics, rows):
    """Viertelstundenmittel 0–5 Uhr mit mindestens 80 % Leistungsabdeckung."""
    zone = ZoneInfo(analytics.zone)
    for row in rows:
        if row["power_s"] >= 720 and datetime.fromtimestamp(row["ts"], zone).hour < 5:
            power = row["power_ws"] / row["power_s"]
            # Negative Nachtwerte (Batterie, Einspeisung) sind keine Grundlast.
            if power >= 0:
                yield row["ts"], power


def average_rate(analytics, end, days=7):
    """Zeitgemitteltes Arbeitspreisniveau des aktuellen Tarifs über die letzten Tage.

    Eine Grundlast ist konstant; daher ist der zeitliche (nicht verbrauchsgewichtete) Mittelwert richtig.
    """
    start = end - days * 86400
    if any(t["mode"] == "dynamic" for t in analytics.tariffs):
        analytics.load_prices(start, end)
    rates = []
    for ts in range(int(start // 900) * 900, int(end), 900):
        tariff = analytics.tariff(ts)
        rate = analytics.rate(ts, tariff) if tariff else None
        if rate is not None:
            rates.append(rate)
    # Erst ab drei Vierteln bepreister Zeit eine Zahl nennen.
    return statistics.mean(rates) if len(rates) >= days * 96 * .75 else None


def baseline_trend(analytics, start, end):
    rows = analytics.store.bucket_rows(start, end)
    zone = ZoneInfo(analytics.zone)
    monthly = end - start > 120 * 86400
    groups = {}
    for ts, power in night_quarters(analytics, rows):
        day = datetime.fromtimestamp(ts, zone).date()
        first = day.replace(day=1) if monthly else day - timedelta(days=day.weekday())
        groups.setdefault(first, []).append(power)
    rate = average_rate(analytics, end)
    points = []
    for first, values in sorted(groups.items()):
        values.sort()
        enough = len(values) >= MIN_NIGHT_QUARTERS
        baseline = values[int((len(values) - 1) * .1)] if enough else None
        points.append({"start": midnight(first, analytics.zone), "label": first.isoformat(), "quarters": len(values),
                       "baseline_w": baseline,
                       "annual_kwh": baseline * HOURS_PER_YEAR / 1000 if enough else None,
                       "annual_eur": baseline * HOURS_PER_YEAR / 1000 * rate if enough and rate is not None else None})
    valid = [p for p in points if p["baseline_w"] is not None]
    change = None
    if len(valid) >= 4:
        half = len(valid) // 2
        change = statistics.median(p["baseline_w"] for p in valid[half:]) - statistics.median(p["baseline_w"] for p in valid[:half])
    return {"group": "month" if monthly else "week", "points": points, "rate_eur_kwh": rate,
            "change_w": change, "min_quarters": MIN_NIGHT_QUARTERS,
            "method": "P10 der Viertelstundenmittel zwischen 0 und 5 Uhr je Woche bzw. Monat; Jahreswerte = Grundlast × 8766 h × aktueller mittlerer Arbeitspreis."}


def feedin_profile(analytics, start, end):
    rows = analytics.store.bucket_rows(start, end)
    zone = ZoneInfo(analytics.zone)
    hours = {}
    for row in rows:
        cell = hours.setdefault(datetime.fromtimestamp(row["ts"], zone).hour, [0.0, 0.0])
        cell[0] += row["export_kwh"]
        cell[1] += row["export_s"]
    total = sum(cell[0] for cell in hours.values())
    return {"total_kwh": total if any(cell[1] for cell in hours.values()) else None,
            "profile": [{"hour": hour, "average_kw": kwh * 3600 / seconds if seconds else None,
                         "share": kwh / total if total else None} for hour, (kwh, seconds) in sorted(hours.items())]}


class Scenario:
    """Hypothetischer Tarif für die Simulation mit demselben Lastgang."""

    def __init__(self, analytics, tariff, start, end):
        self.analytics, self.tariff = analytics, tariff
        self.spot, self.spot_starts = [], []
        if tariff["mode"] == "spot":
            self.spot = analytics.store.rows("SELECT * FROM spot_prices WHERE start<? AND end>? ORDER BY start", (end, start))
            self.spot_starts = [row["start"] for row in self.spot]

    def spot_eur_kwh(self, ts):
        i = bisect.bisect_right(self.spot_starts, ts) - 1
        if i >= 0 and ts < self.spot[i]["end"]:
            return self.spot[i]["eur_mwh"] / 1000
        return None

    def rate(self, ts):
        if self.tariff["mode"] == "spot":
            spot = self.spot_eur_kwh(ts)
            if spot is None:
                return None
            return (spot + self.tariff["markup_eur_kwh"]) * (1 + self.tariff["vat_percent"] / 100)
        return self.analytics.rate(ts, self.tariff)


def simulate(analytics, start, end, tariff):
    rows = analytics.store.bucket_rows(start, end)
    scenario = Scenario(analytics, tariff, start, end)
    cost = priced = unpriced = exported = 0.0
    weighted_spot = spot_seconds = spot_sum = 0.0
    # Gepaarter Vergleich: beide Tarife über genau dieselben bepreisten Viertelstunden.
    paired_kwh = paired_scenario = paired_actual = 0.0
    if any(t["mode"] == "dynamic" for t in analytics.tariffs) and rows:
        analytics.load_prices(rows[0]["ts"], rows[-1]["ts"] + 900)
    for row in rows:
        rate = scenario.rate(row["ts"])
        if rate is None:
            unpriced += row["import_kwh"]
        else:
            cost += row["import_kwh"] * rate
            priced += row["import_kwh"]
            current = analytics.tariff(row["ts"])
            actual_rate = analytics.rate(row["ts"], current) if current else None
            if actual_rate is not None:
                paired_kwh += row["import_kwh"]
                paired_scenario += row["import_kwh"] * rate
                paired_actual += row["import_kwh"] * actual_rate
        exported += row["export_kwh"]
        if tariff["mode"] == "spot" and (spot := scenario.spot_eur_kwh(row["ts"])) is not None and row["import_s"]:
            weighted_spot += row["import_kwh"] * spot
            spot_sum += spot * row["import_s"]
            spot_seconds += row["import_s"]
    actual = analytics.summary(start, end)
    recovered = actual["recovered_import_kwh"]
    base = tariff["base_month"] * analytics.base_factor(start, end)
    feedin = exported * tariff["feedin_eur_kwh"]
    result = {"start": start, "end": end, "energy_cost_eur": cost, "base_cost_eur": base, "feedin_eur": feedin,
              "total_eur": cost + base - feedin, "priced_kwh": priced, "unpriced_kwh": unpriced + recovered,
              "priced_share": priced / (priced + unpriced + recovered) if priced + unpriced + recovered else None,
              "coverage": actual["coverage"], "actual_total_eur": actual["known_cost_eur"],
              "actual_complete": actual["cost_complete"],
              "comparable": actual["cost_complete"] and not unpriced and not recovered,
              "average_eur_kwh": cost / priced if priced else None}
    total_kwh = priced + unpriced + recovered
    if paired_kwh and analytics.tariffs:
        # Grundpreis und Einspeisung über den ganzen Zeitraum, Arbeitspreis nur über gemeinsam bepreiste Energie.
        actual_base, _ = analytics.base_cost(start, end)
        actual_feedin = actual["feedin_eur"]
        result["paired_share"] = paired_kwh / total_kwh if total_kwh else None
        result["difference_eur"] = (paired_scenario + base - feedin) - (paired_actual + actual_base - actual_feedin)
    if tariff["mode"] == "spot" and priced and spot_seconds:
        # Liegt der eigene (verbrauchsgewichtete) Börsenpreis unter dem Zeitmittel, fällt der Bezug eher in günstige Zeiten.
        result["spot_weighted_ct"] = weighted_spot / priced * 100
        result["spot_time_average_ct"] = spot_sum / spot_seconds * 100
    return result


def month_budget(analytics, now, budget):
    zone = analytics.zone
    today = local_day(now, zone)
    month_start = today.replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    observed = analytics.summary(midnight(month_start, zone), now)
    forecast = analytics.forecast(now)
    result = {"monthly_eur": budget.get("monthly_eur"), "monthly_kwh": budget.get("monthly_kwh"),
              "observed_kwh": observed["import_kwh"], "observed_eur": observed["known_cost_eur"],
              "coverage": observed["coverage"], "forecast_kwh": forecast.get("expected_kwh") if forecast["available"] else None,
              "forecast_eur": None, "forecast_reason": forecast.get("reason", "")}
    if result["forecast_kwh"] is not None and observed["import_kwh"]:
        # Bisherige Kosten plus Rest-kWh zum bisher beobachteten mittleren Arbeitspreis plus voller Monatsgrundpreis.
        rate = observed["energy_cost_eur"] / observed["import_kwh"] if observed["energy_cost_eur"] else None
        if rate is not None and not observed["tariff_missing"]:
            remaining = max(0.0, result["forecast_kwh"] - observed["import_kwh"])
            base_full = analytics.base_cost(midnight(month_start, zone), midnight(next_month, zone))[0]
            result["forecast_eur"] = observed["energy_cost_eur"] + remaining * rate + base_full - observed["feedin_eur"]
    return result


def annual_projection(analytics, now, abschlag_eur):
    """Hochrechnung aufs Jahr aus vollständig erfassten Tagen der letzten 365 Tage."""
    zone = analytics.zone
    today = local_day(now, zone)
    first = today - timedelta(days=365)
    days = {}
    for row in analytics.store.bucket_rows(midnight(first, zone), midnight(today, zone)):
        cell = days.setdefault(local_day(row["ts"], zone), [0.0, 0.0])
        cell[0] += row["import_kwh"]
        cell[1] += row["import_s"]
    valid = []
    for day, (kwh, seconds) in days.items():
        length = midnight(day + timedelta(days=1), zone) - midnight(day, zone)
        if seconds / length >= .98:
            valid.append(kwh)
    result = {"valid_days": len(valid), "abschlag_eur": abschlag_eur, "available": False}
    if len(valid) < 60:
        result["reason"] = "Mindestens 60 vollständig erfasste Tage erforderlich."
        return result
    rate = average_rate(analytics, now, days=30)
    tariff = analytics.tariff(now)
    if rate is None or tariff is None:
        result["reason"] = "Für die letzten 30 Tage fehlen Preise."
        return result
    daily = statistics.mean(valid)
    annual_kwh = daily * 365.25
    annual_eur = annual_kwh * rate + tariff["base_month"] * 12
    spread = statistics.stdev(valid) * 365.25 ** .5 * 1.96 * rate if len(valid) > 1 else 0
    result.update(available=True, annual_kwh=annual_kwh, annual_eur=annual_eur, low_eur=annual_eur - spread,
                  high_eur=annual_eur + spread, full_year=len(valid) >= 330,
                  method="Mittel vollständig erfasster Tage × 365 × mittlerer Arbeitspreis der letzten 30 Tage + 12 × Grundpreis. "
                         "Ohne Jahreszeitbereinigung: bei weniger als einem Jahr Daten kann das Ergebnis deutlich abweichen; Einspeisung nicht berücksichtigt.")
    if abschlag_eur:
        result["abschlag_year_eur"] = abschlag_eur * 12
        result["difference_eur"] = annual_eur - abschlag_eur * 12
    return result


# Durchschnittlicher Jahresverbrauch deutscher Haushalte in kWh nach Wohnform, Personen und Warmwasser
# (Stromspiegel für Deutschland, co2online, Stand 05/2025). Gilt für den gesamten Haushaltsstrom;
# mit eigener PV liegt der gemessene Netzbezug darunter.
STROMSPIEGEL = {
    ("apartment", False): (1200, 1900, 2400, 2600, 3100),
    ("apartment", True): (1600, 2500, 3500, 4000, 5000),
    ("house", False): (1800, 2700, 3500, 3800, 4500),
    ("house", True): (2100, 3200, 4100, 4700, 6000),
}
REFERENCE_SOURCE = "Stromspiegel für Deutschland (co2online), Stand 05/2025"


def household_reference(settings):
    persons = settings.get("household_persons") or 0
    if not 1 <= persons <= 5:
        return None
    kind, hot_water = settings.get("household_type", "apartment"), bool(settings.get("household_hot_water"))
    return {"annual_kwh": STROMSPIEGEL[(kind, hot_water)][persons - 1], "persons": persons, "type": kind,
            "hot_water": hot_water, "source": REFERENCE_SOURCE}


def live_cost(analytics, now, power_w):
    """Kostenrate aus aktueller Netzleistung und dem Arbeitspreis der laufenden Viertelstunde.

    Bezug kostet Arbeitspreis × Leistung, Einspeisung bringt Einspeisevergütung × Leistung. Eine Vergütung
    von 0 gilt als nicht hinterlegt. Ohne Leistung (keine frische Messung) nur die Preise.
    """
    tariff = analytics.tariff(now)
    result = {"tariff": tariff is not None, "mode": tariff["mode"] if tariff else None, "rate_eur_kwh": None,
              "feedin_eur_kwh": None, "direction": None, "eur_per_hour": None}
    if not tariff:
        return result
    if tariff["mode"] == "dynamic":
        analytics.load_prices(now, now + 1)
    rate = analytics.rate(now, tariff)
    feedin = tariff["feedin_eur_kwh"] or None
    result.update(rate_eur_kwh=rate, feedin_eur_kwh=feedin)
    if power_w is None:
        return result
    if power_w >= 0:
        result.update(direction="import", eur_per_hour=power_w / 1000 * rate if rate is not None else None)
    else:
        result.update(direction="export", eur_per_hour=-power_w / 1000 * feedin if feedin else None)
    return result


def cheapest_window(intervals, first, quarters):
    """Günstigstes zusammenhängendes Fenster aus `quarters` Viertelstunden, Beginn frühestens bei `first`.

    Mittel über die Zeit (jede Viertelstunde zählt gleich); bei Gleichstand gewinnt das frühere Fenster.
    """
    best = None
    for index in range(len(intervals) - quarters + 1):
        start = intervals[index]["start"]
        if start < first or intervals[index + quarters - 1]["start"] != start + (quarters - 1) * 900:
            continue
        average = math.fsum(item["eur_kwh"] for item in intervals[index:index + quarters]) / quarters
        if best is None or average < best["average_eur_kwh"] - 1e-12:
            best = {"start": start, "end": start + quarters * 900, "average_eur_kwh": average}
    return best


def price_outlook(analytics, now, window_hours):
    """Bruttopreise je Viertelstunde für heute und morgen (Ortszeit) und das günstigste Fenster ab jetzt.

    Nur bei einem aktuell gültigen dynamischen Tarif; längere Preisintervalle werden auf Viertelstunden verteilt.
    """
    zone = analytics.zone
    today = local_day(now, zone)
    tomorrow = today + timedelta(days=1)
    start, middle, end = midnight(today, zone), midnight(tomorrow, zone), midnight(today + timedelta(days=2), zone)
    current = analytics.tariff(now)
    result = {"dynamic": bool(current and current["mode"] == "dynamic"), "timezone": zone, "now": now,
              "current_start": int(now // 900 * 900), "window_hours": window_hours, "start": start, "end": end,
              "tomorrow_start": middle, "intervals": [], "tomorrow_available": False, "low_eur_kwh": None,
              "high_eur_kwh": None, "cheapest": None}
    if not result["dynamic"]:
        return result
    analytics.load_prices(start, end)
    intervals = []
    for ts in range(int(start), int(end), 900):
        tariff = analytics.tariff(ts)
        rate = analytics.rate(ts, tariff) if tariff else None
        if rate is not None:
            intervals.append({"start": ts, "end": ts + 900, "eur_kwh": rate})
    if intervals:
        rates = [item["eur_kwh"] for item in intervals]
        result.update(intervals=intervals, low_eur_kwh=min(rates), high_eur_kwh=max(rates),
                      tomorrow_available=intervals[-1]["start"] >= middle,
                      cheapest=cheapest_window(intervals, result["current_start"], window_hours * 4))
    return result
