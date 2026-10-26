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


class Tokens:
    """API-Tokens für Skripte: 32 Byte Zufall, gespeichert wird nur der SHA-256-Hash.

    Ein Hash genügt, weil das Token selbst nicht erratbar ist (anders als ein Passwort). Tokens überleben
    Neustarts; `read` erlaubt nur lesende Anfragen, `full` alles außer Token- und Passwortverwaltung.
    """
    ROLES = ("read", "full")
    LIMIT = 10
    PREFIX = "kw_"
    # Zuletzt benutzt höchstens einmal je Minute schreiben.
    TOUCH_INTERVAL = 60

    def __init__(self, store):
        self.store = store

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def list(self):
        return self.store.rows("SELECT id,name,role,created,last_used FROM api_tokens ORDER BY created")

    def create(self, name, role, now):
        if role not in self.ROLES:
            raise ValueError("Rolle muss read oder full sein.")
        token = self.PREFIX + secrets.token_urlsafe(32)
        with self.store.transaction():
            if self.store.rows("SELECT COUNT(*) AS n FROM api_tokens")[0]["n"] >= self.LIMIT:
                raise ValueError("Höchstens 10 API-Tokens. Zuerst ein Token löschen.")
            cursor = self.store.conn.execute("INSERT INTO api_tokens(name,hash,role,created) VALUES(?,?,?,?)",
                                             (name, self.digest(token), role, now))
        return dict(id=cursor.lastrowid, name=name, role=role, created=now, last_used=None, token=token)

    def delete(self, token_id):
        with self.store.transaction():
            return self.store.conn.execute("DELETE FROM api_tokens WHERE id=?", (token_id,)).rowcount > 0

    def verify(self, token, now):
        """Gespeichertes Token zum Klartext oder None; vergleicht alle Hashes in konstanter Zeit."""
        if not token.startswith(self.PREFIX) or len(token) > 200:
            return None
        wanted, found = self.digest(token), None
        for row in self.store.rows("SELECT id,hash,role,last_used FROM api_tokens"):
            if secrets.compare_digest(row["hash"], wanted):
                found = row
        if found and (found["last_used"] is None or now - found["last_used"] >= self.TOUCH_INTERVAL):
            with self.store.transaction():
                self.store.conn.execute("UPDATE api_tokens SET last_used=? WHERE id=?", (now, found["id"]))
        return found
