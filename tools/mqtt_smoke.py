"""MQTT-3.1.1-Verbindung und erlaubtes Publish ohne zusätzliche Bibliothek prüfen."""
import argparse
import socket
import time


def connect_and_publish(host, port):
    with socket.create_connection((host, port), timeout=3) as client:
        client.settimeout(3)
        identifier = b"kilowatch-check"
        variable = b"\x00\x04MQTT\x04\x02\x00\x1e" + len(identifier).to_bytes(2, "big") + identifier
        client.sendall(b"\x10" + bytes([len(variable)]) + variable)
        assert client.recv(4) == b"\x20\x02\x00\x00", "Broker lehnt MQTT CONNECT ab."
        topic = b"tibber-bridge/data/publish"
        packet = len(topic).to_bytes(2, "big") + topic + b"\x00\x01" + b"synthetic test"
        client.sendall(b"\x32" + bytes([len(packet)]) + packet)
        assert client.recv(4) == b"\x40\x02\x00\x01", "Broker bestaetigt Publish nicht."
        client.sendall(b"\xe0\x00")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    args = parser.parse_args()
    for attempt in range(20):
        try:
            connect_and_publish(args.host, args.port)
            print("MQTT CONNECT und erlaubtes Publish: OK")
            return
        except (OSError, AssertionError):
            if attempt == 19:
                raise
            time.sleep(.5)


if __name__ == "__main__":
    main()
