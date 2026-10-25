from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, time as dt_time, timedelta
import bisect
import math
import statistics
from zoneinfo import ZoneInfo


def midnight(day, zone):
    if isinstance(day, str):
        day = date.fromisoformat(day)
    return datetime.combine(day, dt_time.min, tzinfo=ZoneInfo(zone)).timestamp()


def iso(ts, zone="UTC"):
    return datetime.fromtimestamp(ts, ZoneInfo(zone)).isoformat()


def local_day(ts, zone):
    return datetime.fromtimestamp(ts, ZoneInfo(zone)).date()


def period(start, end, zone, now, hours=None, minutes=None, since=None, until=None):
    if since is not None:
        # Frei gewähltes Fenster (Zeitbalken, Zoom): Beginn auf die Minute bzw. Viertelstunde gerundet, Ende höchstens jetzt.
        stop = int(min(now, until)) if until is not None else int(now)
        step = 60 if stop - since <= 7200 else 900
        first = int(since // step) * step
        if first < 0 or stop - first < 300 or stop - first > 3660 * 86400:
            raise ValueError("Zeitfenster: mindestens 5 Minuten, höchstens zehn Jahre und nur in der Vergangenheit.")
        return first, stop
    if minutes is not None:
        # Letzte Minuten: Energie aus Minutenwerten, daher Beginn auf die Minute gerundet.
        if not 5 <= minutes <= 120:
            raise ValueError("Minutenansicht: 5 bis 120 Minuten.")
        return int((now - minutes * 60) // 60) * 60, now
    if hours is not None:
        # Letzte Stunden: Beginn auf die Viertelstunde gerundet, weil Energie in Viertelstunden gespeichert ist.
        if not 1 <= hours <= 48:
            raise ValueError("Stundenansicht: 1 bis 48 Stunden.")
        return int((now - hours * 3600) // 900) * 900, now
    today = local_day(now, zone)
    a = date.fromisoformat(start) if start else today
    b = date.fromisoformat(end) + timedelta(days=1) if end else today + timedelta(days=1)
    s, e = midnight(a, zone), min(midnight(b, zone), now)
    if e <= s or e - s > 3660 * 86400:
        raise ValueError("Zeitraum muss in der Vergangenheit liegen und darf höchstens zehn Jahre umfassen.")
    return s, e


class Analytics:
    def __init__(self, store):
        self.store = store
        self.zone = store.settings()["timezone"]
        self.tariffs = store.rows("SELECT * FROM tariffs ORDER BY start_date")
        schedules = store.state("tariff_schedules", {})
        self.tariffs = [dict(row, **schedules.get(row["start_date"], {})) for row in self.tariffs]
        self.tariff_dates = [t["start_date"] for t in self.tariffs]
        # Importpreise erst bei Bedarf und nur für den angefragten Zeitraum laden.
        self.prices, self.price_starts = [], []

    def load_prices(self, start, end):
        self.prices = self.store.rows("SELECT * FROM prices WHERE start<? AND end>? ORDER BY start", (end, start))
        self.price_starts = [p["start"] for p in self.prices]

    def tariff(self, ts):
        key = local_day(ts, self.zone).isoformat()
        index = bisect.bisect_right(self.tariff_dates, key) - 1
        return self.tariffs[index] if index >= 0 else None

    def rate(self, ts, tariff):
        if tariff["mode"] == "fixed":
            return tariff["eur_kwh"]
        if tariff["mode"] == "dual":
            if "low_eur_kwh" not in tariff:
                return None
            local = datetime.fromtimestamp(ts, ZoneInfo(self.zone))
            clock = local.strftime("%H:%M")
            start, end = tariff["low_start"], tariff["low_end"]
            low = (start <= clock < end) if start < end else (clock >= start or clock < end)
            low |= tariff.get("weekend_low", False) and local.weekday() >= 5
            return tariff["low_eur_kwh"] if low else tariff["eur_kwh"]
        i = bisect.bisect_right(self.price_starts, ts) - 1
        if i >= 0 and ts < self.prices[i]["end"]:
            return self.prices[i]["eur_kwh"]
        return None

    def base_cost(self, start, end):
        cursor, total, missing = local_day(start, self.zone), 0.0, False
        while midnight(cursor, self.zone) < end:
            a, b = midnight(cursor, self.zone), midnight(cursor + timedelta(days=1), self.zone)
            tariff = self.tariff(a)
            overlap = max(0, min(b, end) - max(a, start))
            if tariff:
                total += tariff["base_month"] / monthrange(cursor.year, cursor.month)[1] * overlap / (b - a)
            else:
                missing = True
            cursor += timedelta(days=1)
        return total, missing

    def base_factor(self, start, end):
        day, factor = local_day(start, self.zone), 0.0
        while midnight(day, self.zone) < end:
            a, b = midnight(day, self.zone), midnight(day + timedelta(days=1), self.zone)
            overlap = max(0, min(b, end) - max(a, start))
            factor += overlap / (b - a) / monthrange(day.year, day.month)[1]
            day += timedelta(days=1)
        return factor

    def summary(self, start, end, resolution=900):
        rows = self.store.bucket_rows(start, end, resolution)
        if rows and any(t["mode"] == "dynamic" for t in self.tariffs):
            self.load_prices(rows[0]["ts"], rows[-1]["ts"] + resolution)
        imported = sum(r["import_kwh"] for r in rows)
        exported = sum(r["export_kwh"] for r in rows)
        imp_s = sum(r["import_s"] for r in rows)
        exp_s = sum(r["export_s"] for r in rows)
        peak = max((r["max_w"] for r in rows if r["max_w"] is not None), default=None)
        energy_cost, revenue, unpriced_kwh = 0.0, 0.0, 0.0
        tariff_missing = False
        for row in rows:
            tariff = self.tariff(row["ts"])
            rate = self.rate(row["ts"], tariff) if tariff else None
            if rate is None:
                unpriced_kwh += row["import_kwh"]
                tariff_missing |= row["import_s"] > 0
            else:
                energy_cost += row["import_kwh"] * rate
            if tariff:
                revenue += row["export_kwh"] * tariff["feedin_eur_kwh"]
        gaps = self.store.gap_rows(start, end)
        recovered_import, recovered_export, crossing = 0.0, 0.0, 0
        for gap in gaps:
            if gap["start"] >= start and gap["end"] <= end:
                recovered_import += gap["import_kwh"] or 0
                recovered_export += gap["export_kwh"] or 0
            else:
                crossing += 1
        base, base_missing = self.base_cost(start, end)
        seconds = end - start
        coverage = min(1, imp_s / seconds) if seconds > 0 else 0
        complete = not tariff_missing and not base_missing and coverage >= 0.995 and not gaps
        return {
            "start": start, "end": end,
            "import_kwh": imported + recovered_import if imp_s > 0 or recovered_import > 0 else None,
            "export_kwh": exported + recovered_export if exp_s > 0 or recovered_export > 0 else None,
            "allocated_import_kwh": imported if imp_s > 0 else None,
            "recovered_import_kwh": recovered_import, "recovered_export_kwh": recovered_export,
            "gap_count": len(gaps), "crossing_gaps": crossing,
            "coverage": coverage, "export_coverage": min(1, exp_s / seconds) if seconds > 0 else 0,
            "estimated_import_kwh": sum(r["estimated_import"] for r in rows),
            "estimated_export_kwh": sum(r["estimated_export"] for r in rows),
            "peak_w": peak, "high_load_hours": sum(r["high_s"] for r in rows) / 3600,
            "energy_cost_eur": energy_cost, "base_cost_eur": base, "feedin_eur": revenue,
            "base_month_factor": self.base_factor(start, end),
            "known_cost_eur": energy_cost + base - revenue if self.tariffs else None,
            "cost_complete": complete, "unpriced_kwh": unpriced_kwh + recovered_import,
            "tariff_missing": tariff_missing or base_missing,
        }

    def series(self, start, end):
        # Energie immer aus permanenten Viertelstundenwerten, Leistung für kurze
        # Ansichten aus Minutenwerten. Keine Lücken durch Nullwerte verdecken.
        group = ("minute" if end - start <= 1800 else "quarter" if end - start <= 3 * 86400
                 else "day" if end - start <= 400 * 86400 else "month")
        step = 60 if group == "minute" else 900
        groups = {}
        for row in self.store.bucket_rows(start, end, step):
            local = datetime.fromtimestamp(row["ts"], ZoneInfo(self.zone))
            key = str(row["ts"]) if group in ("minute", "quarter") else local.strftime("%Y-%m-%d" if group == "day" else "%Y-%m")
            if key not in groups:
                stamp = row["ts"] if group in ("minute", "quarter") else midnight(local.date().replace(day=1) if group == "month" else local.date(), self.zone)
                groups[key] = {"ts": stamp, "label": iso(stamp, self.zone), "import_kwh": 0,
                               "export_kwh": 0, "import_s": 0, "export_s": 0, "power_ws": 0, "power_s": 0, "peak_w": None}
            item = groups[key]
            for field in ["import_kwh", "export_kwh", "import_s", "export_s", "power_ws", "power_s"]:
                item[field] += row[field]
            if row["max_w"] is not None:
                item["peak_w"] = row["max_w"] if item["peak_w"] is None else max(item["peak_w"], row["max_w"])
        # Auch vollständig fehlende Zeitabschnitte behalten einen Platz auf der
        # Achse. Eine Lücke ist kein Nullverbrauch.
        if group in ("minute", "quarter"):
            stamps = list(range(int(start // step) * step, math.ceil(end), step))
        else:
            stamps = []
            day = local_day(start, self.zone)
            if group == "month":
                day = day.replace(day=1)
            while midnight(day, self.zone) < end:
                stamps.append(midnight(day, self.zone))
                day = day + timedelta(days=1) if group == "day" else (day.replace(day=28) + timedelta(days=4)).replace(day=1)
        for stamp in stamps:
            local = datetime.fromtimestamp(stamp, ZoneInfo(self.zone))
            key = str(stamp) if group in ("minute", "quarter") else local.strftime("%Y-%m-%d" if group == "day" else "%Y-%m")
            groups.setdefault(key, {"ts": stamp, "label": iso(stamp, self.zone), "import_kwh": 0,
                                   "export_kwh": 0, "import_s": 0, "export_s": 0, "power_ws": 0,
                                   "power_s": 0, "peak_w": None})
        for item in groups.values():
            item["power_w"] = item.pop("power_ws") / item["power_s"] if item["power_s"] else None
            if not item["import_s"]:
                item["import_kwh"] = None
            if not item["export_s"]:
                item["export_kwh"] = None
        power = []
        # Bis zwei Stunden einzelne Messwerte (Abstand = Abrufintervall), bis drei Tage Minuten, sonst Viertelstunden.
        resolution = 0 if end - start <= 2 * 3600 else 60 if end - start <= 3 * 86400 else 900
        if resolution == 0:
            samples = self.store.sample_rows(start, end)
            for row, following in zip(samples, samples[1:] + [None]):
                seconds = min(60, (following["ts"] if following else end) - row["ts"])
                power.append({"ts": row["ts"], "power_w": row["power_w"], "seconds": max(seconds, 1)})
            if not power:
                resolution = 60
        if resolution:
            power_rows = self.store.bucket_rows(start, end, resolution)
            if not power_rows and resolution == 60:
                resolution = 900
                power_rows = self.store.bucket_rows(start, end, resolution)
            for row in power_rows:
                if row["power_s"]:
                    power.append({"ts": row["ts"], "power_w": row["power_ws"] / row["power_s"], "seconds": row["power_s"]})
        # Begrenzte Antwortgröße: zeitgewichtete Mittel gleich großer Gruppen.
        # Kurze Spitzen werden dabei geglättet; peak_w der Energiegruppen bleibt exakt.
        if len(power) > 1800:
            size = math.ceil(len(power) / 1800)
            reduced = []
            for index in range(0, len(power), size):
                chunk = power[index:index + size]
                duration = sum(p["seconds"] for p in chunk)
                reduced.append({"ts": chunk[0]["ts"], "seconds": duration,
                                "power_w": sum(p["power_w"] * p["seconds"] for p in chunk) / duration})
            power = reduced
        return {"group": group, "energy": sorted(groups.values(), key=lambda v: v["ts"]), "power": power,
                "power_resolution_seconds": resolution}

    def patterns(self, start, end):
        rows = self.store.bucket_rows(start, end)
        heat = defaultdict(lambda: {"kwh": 0.0, "seconds": 0.0})
        profile = defaultdict(lambda: {"kwh": 0.0, "seconds": 0.0})
        night, loads = [], []
        for row in rows:
            local = datetime.fromtimestamp(row["ts"], ZoneInfo(self.zone))
            cell = heat[(local.date().isoformat(), local.hour)]
            cell["kwh"] += row["import_kwh"]
            cell["seconds"] += row["import_s"]
            key = ("weekend" if local.weekday() >= 5 else "weekday", local.hour)
            profile[key]["kwh"] += row["import_kwh"]
            profile[key]["seconds"] += row["import_s"]
            if row["power_s"] >= 720:
                power = row["power_ws"] / row["power_s"]
                loads.append({"power_w": power, "seconds": row["power_s"]})
                if 0 <= local.hour < 5 and power >= 0:
                    night.append(power)
        night.sort()
        baseline = night[int((len(night) - 1) * .1)] if len(night) >= 12 else None
        loads.sort(key=lambda item: item["power_w"], reverse=True)
        duration, curve = 0.0, []
        stride = max(1, len(loads) // 160)
        for index, item in enumerate(loads):
            duration += item["seconds"] / 3600
            if index % stride == 0 or index == len(loads) - 1:
                curve.append({"hours": duration, "power_w": item["power_w"]})
        anomalies = []
        recent = [r["power_ws"] / r["power_s"] for r in rows if r["power_s"] >= 720 and r["ts"] >= end - 7 * 86400 and 0 <= datetime.fromtimestamp(r["ts"], ZoneInfo(self.zone)).hour < 5]
        prior = [r["power_ws"] / r["power_s"] for r in rows if r["power_s"] >= 720 and end - 14 * 86400 <= r["ts"] < end - 7 * 86400 and 0 <= datetime.fromtimestamp(r["ts"], ZoneInfo(self.zone)).hour < 5]
        if len(recent) >= 24 and len(prior) >= 24:
            delta = statistics.median(recent) - statistics.median(prior)
            if delta > max(80, abs(statistics.median(prior)) * .3):
                anomalies.append({"title": "Nachtverbrauch gestiegen", "text": "Median der letzten 7 Nächte liegt {delta} W über dem vorigen Vergleichsfenster. Ursache prüfen; keine Geräteerkennung.", "params": {"delta": round(delta)}})
        if not anomalies:
            anomalies.append({"title": "Keine belastbare Auffälligkeit", "text": "Die Regel benötigt je 24 ausreichend erfasste Viertelstunden in beiden Nachtfenstern. Fehlende Daten sind kein Nachweis für normalen Verbrauch."})
        return {
            "heatmap": [{"day": d, "hour": h, **v} for (d, h), v in sorted(heat.items())],
            "profile": [{"type": t, "hour": h, "average_kw": v["kwh"] * 3600 / v["seconds"] if v["seconds"] else None} for (t, h), v in sorted(profile.items())],
            "baseline_w": baseline, "night_quarters": len(night), "duration_curve": curve,
            "anomalies": anomalies,
        }

    def forecast(self, now):
        today = local_day(now, self.zone)
        month_start = today.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        history_start = today - timedelta(days=28)
        # Eine Abfrage, statt 28 vollständiger Summenabfragen.
        day_energy = defaultdict(lambda: [0.0, 0.0])
        for row in self.store.bucket_rows(midnight(history_start, self.zone), midnight(today, self.zone)):
            day = local_day(row["ts"], self.zone)
            day_energy[day][0] += row["import_kwh"]
            day_energy[day][1] += row["import_s"]
        valid = {}
        for day, (energy, coverage) in day_energy.items():
            duration = midnight(day + timedelta(days=1), self.zone) - midnight(day, self.zone)
            if coverage / duration >= .98:
                valid[day] = energy
        if len(valid) < 7:
            return {"available": False, "reason": "Mindestens sieben Tage mit jeweils 98 % Datenabdeckung erforderlich.", "valid_days": len(valid)}
        observed = self.summary(midnight(month_start, self.zone), now)
        # Wenn der Monatsanfang fehlt, wäre eine Hochrechnung des Rests irreführend.
        if observed["coverage"] < .98:
            return {"available": False, "reason": "Für diesen Monat fehlen noch zu viele Messdaten.", "valid_days": len(valid)}
        predictions = []
        day = today
        while day < next_month:
            matches = [energy for old, energy in valid.items() if old.weekday() == day.weekday()]
            estimate = statistics.mean(matches or list(valid.values()))
            fraction = 1.0
            if day == today:
                fraction = (midnight(day + timedelta(days=1), self.zone) - now) / (midnight(day + timedelta(days=1), self.zone) - midnight(day, self.zone))
            predictions.append(estimate * fraction)
            day += timedelta(days=1)
        expected = (observed["import_kwh"] or 0) + sum(predictions)
        margin = (statistics.stdev(valid.values()) if len(valid) > 1 else 0) * math.sqrt(len(predictions)) * 1.96
        return {"available": True, "expected_kwh": expected, "low_kwh": max(observed["import_kwh"] or 0, expected - margin),
                "high_kwh": expected + margin, "valid_days": len(valid),
                "method": "Mittel gleicher Wochentage aus 28 Tagen; heuristisches Band ±1,96·Tagesstreuung·√Resttage. Keine garantierte statistische Abdeckung."}
