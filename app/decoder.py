"""CRC-geprüfte SML-Telegramme und lesbare OBIS-Telegramme.

Keine Modellannahme aus dem Herstellernamen. Kein Überspringen der SML-CRC.
"""
from dataclasses import dataclass, field
import math
import re

from smllib import SmlStreamReader


class DecodeError(ValueError):
    pass


@dataclass
class Reading:
    power_w: float | None = None
    import_kwh: float | None = None
    export_kwh: float | None = None
    meter_id: str = ""
    protocol: str = "SML"
    obis: dict = field(default_factory=dict)


def normalize(values: dict, meter_id: str, protocol: str) -> Reading:
    def value(code, unit=None):
        item = values.get(code)
        if not item:
            return None
        number, actual_unit = item
        if not isinstance(number, (float, int)) or not math.isfinite(number):
            return None
        if unit is not None and actual_unit != unit:
            return None
        return float(number)

    def energy(code):
        number = value(code, "Wh")
        if number is not None:
            return number / 1000
        return value(code, "kWh")

    def total(code):
        number = energy(code + ".0")
        if number is not None:
            return number
        # Nur zusammengehörige T1/T2-Register; niemals Total und Tarife addieren.
        t1, t2 = energy(code + ".1"), energy(code + ".2")
        return t1 + t2 if t1 is not None and t2 is not None else None

    power = value("16.7.0", "W")
    if power is None:
        ip, ep = value("1.7.0", "W"), value("2.7.0", "W")
        if ip is not None or ep is not None:
            power = (ip or 0) - (ep or 0)
    if power is None:
        kw = value("16.7.0", "kW")
        if kw is not None:
            power = kw * 1000
    reading = Reading(power, total("1.8"), total("2.8"), meter_id, protocol,
                      {k: {"value": v[0], "unit": v[1]} for k, v in values.items()})
    if all(v is None for v in (reading.power_w, reading.import_kwh, reading.export_kwh)):
        raise DecodeError("Kein unterstütztes Leistungs- oder Energieregister gefunden.")
    if any(v is not None and v < 0 for v in (reading.import_kwh, reading.export_kwh)):
        raise DecodeError("Negativer Zählerstand im Telegramm.")
    return reading


def decode(payload: bytes) -> Reading:
    if len(payload) > 65536:
        raise DecodeError("Telegramm überschreitet 64 KiB.")
    if b"\x1b\x1b\x1b\x1b\x01\x01\x01\x01" in payload:
        try:
            stream = SmlStreamReader()
            stream.add(payload)
            frames = []
            while (frame := stream.get_frame()) is not None:
                frames.append(frame)
            if not frames:
                raise DecodeError("SML-Telegramm unvollständig.")
            frame = frames[-1]
            # Vollständige Struktur verwenden: der schnelle get_obis-Pfad übersieht
            # manche Herstellerregister mit abweichenden OBIS-Gruppen.
            entries = []
            for message in frame.parse_frame():
                entries.extend(getattr(message.message_body, "val_list", []))
            values, meter_id = {}, ""
            for entry in entries:
                code = entry.obis.obis_short
                number = entry.get_value()
                if code in ("0.0.9", "96.1.0"):
                    meter_id = str(number)
                if isinstance(number, (int, float)):
                    units = {27: "W", 30: "Wh"}
                    values[code] = (number, units.get(entry.unit, str(entry.unit)))
            return normalize(values, meter_id, "SML · CRC geprüft")
        except DecodeError:
            raise
        except Exception as exc:
            raise DecodeError("SML-Struktur oder CRC ungültig (" + type(exc).__name__ + ").") from None

    text = payload.decode("ascii", errors="replace")
    # Bewusster Klartext-Fallback, keine beliebige JSON-Interpretation.
    pattern = r"(?:\d+-\d+:)?(\d+\.\d+\.\d+)(?:\*\d+)?\(([-+]?\d+(?:[.,]\d+)?)(?:\*([A-Za-z]+))?\)"
    values = {}
    for match in re.finditer(pattern, text):
        code, number, unit = match.groups()
        values[code] = (float(number.replace(",", ".")), unit or "unknown")
    if values:
        return normalize(values, "", "OBIS-Klartext · ohne CRC-Prüfung")
    if "<html" in text.lower() or "<!doctype" in text.lower():
        raise DecodeError("Bridge liefert HTML statt Zählerdaten. Auslesepfad und Node-ID prüfen.")
    raise DecodeError("Format nicht erkannt. Unterstützt: SML und lesbare OBIS-Werte; kein P1/HAN/KM.")
