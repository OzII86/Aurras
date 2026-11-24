# core/auth_manager.py
import os
import sqlite3
import hashlib
import hmac
from datetime import datetime
from typing import Optional, Set, Tuple, Dict, Any

DB_PATH = os.path.join("config", "aurras_vault.db")
ADMIN_MASTER_KEY = "AURRAS-ADMIN-MASTER-2026"
_KEY_SIGNING_SECRET = b"Aurras-Studio-Offline-Entitlement-Salt-2026"


class AuthManager:
    """
    Standalone HIVE-ready local User Authentication & Pack Entitlement Engine.
    Persists user accounts, salted password hashes, admin flags, and redeemed
    pack product keys in a local SQLite database (`config/aurras_vault.db`).
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.current_user: Optional[str] = None
        self.is_admin: bool = False
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_entitlements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE,
                    pack_name TEXT NOT NULL,
                    product_key TEXT NOT NULL,
                    unlocked_at TEXT NOT NULL,
                    UNIQUE(username, pack_name),
                    FOREIGN KEY(username) REFERENCES users(username) ON DELETE CASCADE
                )
            """)
            conn.commit()

    @staticmethod
    def _hash_password(password: str, salt_hex: str) -> str:
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            120_000
        )
        return dk.hex()

    @staticmethod
    def generate_product_key_for_pack(pack_name: str) -> str:
        """
        Admin helper: generates the valid deterministic product key for any pack plugin.
        Format: AURRAS-<PACKPREFIX>-<8-CHAR-SIG>
        """
        clean_tag = "".join(ch for ch in pack_name.upper() if ch.isalnum())[:8]
        digest = hmac.new(_KEY_SIGNING_SECRET, pack_name.encode("utf-8"), hashlib.sha256).hexdigest()[:8].upper()
        return f"AURRAS-{clean_tag}-{digest[:4]}-{digest[4:]}"

    def register_user(self, username: str, password: str) -> Tuple[bool, str]:
        clean_user = username.strip()
        if len(clean_user) < 3 or len(password) < 4:
            return False, "Username must be 3+ chars and password 4+ chars."

        salt_hex = os.urandom(16).hex()
        pw_hash = self._hash_password(password, salt_hex)
        now = datetime.now().isoformat(timespec="seconds")

        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO users (username, password_hash, salt, is_admin, created_at) VALUES (?, ?, ?, 0, ?)",
                    (clean_user, pw_hash, salt_hex, now)
                )
                # Automatically grant Starter_Pack entitlement on account creation
                conn.execute(
                    "INSERT OR IGNORE INTO user_entitlements (username, pack_name, product_key, unlocked_at) VALUES (?, ?, ?, ?)",
                    (clean_user, "Starter_Pack", "FREE-STARTER-DEFAULT", now)
                )
                conn.commit()
            self.current_user = clean_user
            self.is_admin = False
            return True, f"Account '{clean_user}' created and signed in."
        except sqlite3.IntegrityError:
            return False, f"Username '{clean_user}' already exists."

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        clean_user = username.strip()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT username, password_hash, salt, is_admin FROM users WHERE username = ?",
                (clean_user,)
            ).fetchone()

        if not row:
            return False, "Account not found."

        db_user, db_hash, salt_hex, is_admin_int = row
        if self._hash_password(password, salt_hex) != db_hash:
            return False, "Incorrect password."

        self.current_user = db_user
        self.is_admin = bool(is_admin_int)
        return True, f"Welcome back, {db_user}!"

    def logout(self):
        self.current_user = None
        self.is_admin = False

    def get_unlocked_packs(self) -> Set[str]:
        """Returns all pack names owned by the currently logged-in user (always includes Starter_Pack)."""
        unlocked = {"Starter_Pack"}
        if not self.current_user:
            return unlocked

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT pack_name FROM user_entitlements WHERE username = ?",
                (self.current_user,)
            ).fetchall()
        for (pack_name,) in rows:
            unlocked.add(pack_name)
        return unlocked

    def redeem_product_key(self, raw_key: str, available_pack_names: list[str]) -> Tuple[bool, str]:
        """
        Validates a product key or the Admin Master Key against the logged-in user's account
        and persists the unlock permanently in SQLite.
        """
        if not self.current_user:
            return False, "Please sign in first so your redeemed key can be saved to your account."

        key = raw_key.strip().upper()
        now = datetime.now().isoformat(timespec="seconds")

        # 1. Check Admin Master Key
        if key == ADMIN_MASTER_KEY:
            with self._connect() as conn:
                conn.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (self.current_user,))
                conn.commit()
            self.is_admin = True
            return True, "Admin Master Key activated! All Sound Packs are permanently unlocked on this account."

        # 2. Match against deterministic pack keys
        for pack_name in available_pack_names:
            expected_key = self.generate_product_key_for_pack(pack_name)
            if hmac.compare_digest(key, expected_key):
                with self._connect() as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO user_entitlements (username, pack_name, product_key, unlocked_at) VALUES (?, ?, ?, ?)",
                        (self.current_user, pack_name, key, now)
                    )
                    conn.commit()
                return True, f"Unlocked '{pack_name}' and saved to {self.current_user}'s account!"

        return False, "Invalid Product Key."

    def get_session_summary(self) -> Dict[str, Any]:
        return {
            "username": self.current_user,
            "is_admin": self.is_admin,
            "unlocked_packs": sorted(self.get_unlocked_packs())
        }