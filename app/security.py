"""Lokale Anmeldung und verschlüsselte, atomar gespeicherte Zugangsdaten."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading

from cryptography.fernet import Fernet, InvalidToken


def private_write(path: Path, data: bytes):
    # Eindeutige Zwischendatei (Modus 0600), damit gleichzeitige Schreibvorgänge sich nicht überschreiben.
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        temporary.chmod(0o600)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


class Vault:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "secrets.enc"
        self.key_path = self.directory / "secrets.key"
        self.lock = threading.RLock()
        if not self.key_path.exists():
            if self.path.exists():
                raise ValueError("Schlüssel der lokalen Zugangsdaten fehlt. secrets.key aus der Sicherung wiederherstellen.")
            private_write(self.key_path, Fernet.generate_key())
        self.cipher = Fernet(self.key_path.read_bytes())
        self.values = {}
        if self.path.exists():
            try:
                self.values = json.loads(self.cipher.decrypt(self.path.read_bytes()))
                if not isinstance(self.values, dict):
                    raise ValueError()
            except (InvalidToken, ValueError):
                raise ValueError("Lokale Zugangsdaten sind nicht lesbar. Sicherung von secrets.enc und secrets.key prüfen.") from None

    def get(self, name, default=""):
        with self.lock:
            return self.values.get(name, default)

    def update(self, values):
        with self.lock:
            updated = dict(self.values)
            for name, value in values.items():
                if value is None:
                    updated.pop(name, None)
                else:
                    updated[name] = value
            private_write(self.path, self.cipher.encrypt(json.dumps(updated).encode()))
            self.values = updated


class Auth:
    def __init__(self, directory):
        Path(directory).mkdir(parents=True, exist_ok=True)
        self.path = Path(directory) / "app-auth.json"
        self.lock = threading.RLock()
        self.record = json.loads(self.path.read_text()) if self.path.exists() else None
        self.setup_code = secrets.token_urlsafe(18) if not self.record else ""

    @property
    def configured(self):
        return self.record is not None

    @staticmethod
    def derive(password, salt):
        return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)

    def initialize(self, password, code):
        with self.lock:
            if self.configured:
                raise ValueError("Die Ersteinrichtung ist bereits abgeschlossen.")
            if not secrets.compare_digest(code, self.setup_code):
                raise ValueError("Setup-Code stimmt nicht. Code im Container-Protokoll nachsehen.")
            self.set_password(password)
            self.setup_code = ""

    def set_password(self, password):
        if not 12 <= len(password) <= 500:
            raise ValueError("App-Passwort muss 12 bis 500 Zeichen lang sein.")
        salt = secrets.token_bytes(16)
        record = {"scheme": "scrypt-16384-8-1", "salt": base64.b64encode(salt).decode(),
                  "digest": base64.b64encode(self.derive(password, salt)).decode()}
        with self.lock:
            private_write(self.path, json.dumps(record).encode())
            self.record = record

    def verify(self, password):
        with self.lock:
            if not self.record:
                return False
            salt = base64.b64decode(self.record["salt"])
            return secrets.compare_digest(self.derive(password, salt), base64.b64decode(self.record["digest"]))
