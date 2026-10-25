from dataclasses import dataclass
from pathlib import Path
import os


@dataclass
class Config:
    data_dir: Path
    # Zugangsdaten getrennt von den Messdaten, damit Datensicherungen nie
    # Schlüssel und verschlüsselte Geheimnisse zusammen enthalten.
    secrets_dir: Path | None = None
    secure_cookie: bool = False
    demo: bool = False
    testing: bool = False

    @property
    def mode(self):
        return "demo" if self.demo else "live"

    @property
    def data_folder(self):
        return Path(self.data_dir) / self.mode

    @property
    def secrets_folder(self):
        return Path(self.secrets_dir or Path(self.data_dir) / "secrets") / self.mode

    @classmethod
    def from_env(cls):
        return cls(
            data_dir=Path(os.getenv("DATA_DIR", "/data")),
            secrets_dir=Path(os.getenv("SECRETS_DIR", "/secrets")),
            secure_cookie=os.getenv("COOKIE_SECURE", "false").lower() == "true",
            demo=os.getenv("DEMO_MODE", "false").lower() == "true",
        )
