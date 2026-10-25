import pytest
from smllib.crc.x25 import get_crc

from app.decoder import DecodeError, decode, normalize


def tl(value):
    if value is None:
        return b"\x01"
    if isinstance(value, list):
        size = len(value)
        tag = bytes([0x70 + size]) if size < 16 else bytes([0xF0 | size >> 4, size & 15])
        return tag + b"".join(tl(item) for item in value)
    if isinstance(value, bytes):
        assert len(value) < 15
        return bytes([len(value) + 1]) + value
    if isinstance(value, tuple):
        raw = value[0].to_bytes(value[1], "big", signed=True)
        return bytes([0x50 | len(raw) + 1]) + raw
    raw = value.to_bytes(max(1, (value.bit_length()+7)//8), "big")
    return bytes([0x60 | len(raw) + 1]) + raw


def sml_frame():
    entries = [
        [bytes.fromhex("0100010800ff"), None, None, 30, (-1, 1), 123456789, None],
        [bytes.fromhex("0100020800ff"), None, None, 30, (-1, 1), 1000, None],
        [bytes.fromhex("0100100700ff"), None, None, 27, (0, 1), (-450, 2), None],
    ]
    body = [None, b"TESTMETER1", None, None, entries, None, None]
    # SmlMessage hat ein spezielles Ende-Byte statt eines optionalen Werts.
    message = b"\x76" + b"".join(tl(item) for item in [b"0001", 0, 0, [0x0701, body], 0]) + b"\x00"
    padding = (-len(message)) % 4
    prefix = b"\x1b"*4 + b"\x01"*4 + message + b"\x00"*padding + b"\x1b"*4 + b"\x1a" + bytes([padding])
    return prefix + get_crc(prefix).to_bytes(2, "big")


def test_sml_units_scaler_and_signed_power():
    reading = decode(sml_frame())
    assert reading.import_kwh == pytest.approx(12345.6789)
    assert reading.export_kwh == pytest.approx(.1)
    assert reading.power_w == -450
    assert "CRC" in reading.protocol


def test_crc_corruption_rejected():
    payload = bytearray(sml_frame())
    payload[20] ^= 1
    with pytest.raises(DecodeError, match="CRC"):
        decode(bytes(payload))


def test_missing_bytes_rejected():
    with pytest.raises(DecodeError):
        decode(sml_frame()[:-4])


def test_plain_obis_units():
    reading = decode(b"/METER\r\n1-0:1.8.0(01234.567*kWh)\r\n1-0:16.7.0(-0.123*kW)\r\n!")
    assert reading.import_kwh == pytest.approx(1234.567)
    assert reading.power_w == -123


def test_no_double_counting_tariff_registers():
    r = normalize({"1.8.0": (1000,"Wh"), "1.8.1": (600,"Wh"), "1.8.2": (400,"Wh")}, "", "test")
    assert r.import_kwh == 1
    r = normalize({"1.8.1": (600,"Wh"), "1.8.2": (400,"Wh")}, "", "test")
    assert r.import_kwh == 1


@pytest.mark.parametrize("payload", [b"<html></html>", b"{}", b"nonsense", b"x"*65537], ids=["html", "json", "unknown", "oversize"])
def test_unsupported_payload(payload):
    with pytest.raises(DecodeError):
        decode(payload)
