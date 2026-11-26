# core/auth_manager.py
import os
import sqlite3
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Set, Tuple, Dict, Any, List

DB_PATH = os.path.join("config", "aurras_vault.db")
ADMIN_MASTER_KEY = "AURRAS-ADMIN-MASTER-2026"
_KEY_SIGNING_SECRET = b"Aurras-Studio-Offline-Entitlement-Salt-2026"

ALL_GRID_MODES = ["3x3", "3x6", "3x9", "Full (36)"]

DEMO_INCLUDED_PACKS = {
    "Starter_Pack",
    "Pure_Acoustic_Drums",
    "Pure_Grand_Piano",
    "Pure_Cello_Ensemble",
    "Pure_Brass_Section",
}


class AuthManager:
    """
    Standalone HIVE-ready local User Authentication & Tiered Entitlement Engine.
    Supports:
      - Free Baseline (3x3, Starter_Pack)
      - 30-Day Demo Trial (Auto-activated on registration: 3x3..3x9 + Core Instruments)
      - Individual Pack Purchases (Perpetual per-pack unlock across all grid sizes)
      - Monthly Subscription (30-day full catalog + Full 36 grid unlock, stackable)
      - Lifetime Pro License (Perpetual full catalog + Full 36 grid unlock)
      - Admin Master Key (Full catalog + Keygen tools)
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
                    tier TEXT NOT NULL DEFAULT 'DEMO_30D',
                    tier_expires_at TEXT,
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
            # Migrate older users table if tier columns do not exist yet
            cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
            if "tier" not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN tier TEXT NOT NULL DEFAULT 'DEMO_30D'")
            if "tier_expires_at" not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN tier_expires_at TEXT")
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

    # =========================================================================
    # DETERMINISTIC PRODUCT KEY GENERATORS (FOR STOREFRONT & ADMIN TESTING)
    # =========================================================================

    @staticmethod
    def generate_pack_key(pack_name: str) -> str:
        """Perpetual Individual Pack Key: AURRAS-PACK-<TAG>-<SIG>"""
        tag = "".join(ch for ch in pack_name.upper() if ch.isalnum())[:8]
        sig = hmac.new(_KEY_SIGNING_SECRET, f"PACK:{pack_name}".encode("utf-8"), hashlib.sha256).hexdigest()[:8].upper()
        return f"AURRAS-PACK-{tag}-{sig}"

    @staticmethod
    def generate_subscription_key(username: str, nonce: str = "M01") -> str:
        """30-Day Monthly Subscription Key bound to username + nonce: AURRAS-SUB30-<NONCE>-<SIG>"""
        clean_u = username.strip().upper()
        clean_n = "".join(ch for ch in nonce.upper() if ch.isalnum())[:6] or "M01"
        sig = hmac.new(_KEY_SIGNING_SECRET, f"SUB30:{clean_u}:{clean_n}".encode("utf-8"), hashlib.sha256).hexdigest()[:8].upper()
        return f"AURRAS-SUB30-{clean_n}-{sig}"

    @staticmethod
    def generate_lifetime_key(username: str) -> str:
        """Perpetual Lifetime Pro Key bound to username: AURRAS-LIFE-<USER4>-<SIG>"""
        clean_u = username.strip().upper()
        u_tag = "".join(ch for ch in clean_u if ch.isalnum())[:4] or "USER"
        sig = hmac.new(_KEY_SIGNING_SECRET, f"LIFETIME:{clean_u}".encode("utf-8"), hashlib.sha256).hexdigest()[:8].upper()
        return f"AURRAS-LIFE-{u_tag}-{sig}"

    # =========================================================================
    # ACCOUNT AUTHENTICATION & TIER EVALUATION
    # =========================================================================

    def register_user(self, username: str, password: str) -> Tuple[bool, str]:
        clean_user = username.strip()
        if len(clean_user) < 3 or len(password) < 4:
            return False, "Username must be 3+ chars and password 4+ chars."

        salt_hex = os.urandom(16).hex()
        pw_hash = self._hash_password(password, salt_hex)
        now_dt = datetime.now()
        demo_exp = (now_dt + timedelta(days=30)).isoformat(timespec="seconds")

        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO users (username, password_hash, salt, tier, tier_expires_at, is_admin, created_at) "
                    "VALUES (?, ?, ?, 'DEMO_30D', ?, 0, ?)",
                    (clean_user, pw_hash, salt_hex, demo_exp, now_dt.isoformat(timespec="seconds"))
                )
                conn.execute(
                    "INSERT OR IGNORE INTO user_entitlements (username, pack_name, product_key, unlocked_at) "
                    "VALUES (?, 'Starter_Pack', 'FREE-STARTER-DEFAULT', ?)",
                    (clean_user, now_dt.isoformat(timespec="seconds"))
                )
                conn.commit()
            self.current_user = clean_user
            self.is_admin = False
            return True, f"Account '{clean_user}' created! Your 30-Day Pro Demo is now active."
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
        status = self.get_tier_status()
        return True, f"Welcome back, {db_user}!\nActive Tier: {status['display_name']}"

    def logout(self):
        self.current_user = None
        self.is_admin = False

    def get_tier_status(self) -> Dict[str, Any]:
        """
        Evaluates the active user's tier, checks 30-day expiration timestamps,
        and returns allowed grid modes, full-catalog flags, and remaining days.
        """
        if not self.current_user:
            return {
                "tier": "FREE",
                "display_name": "Free Guest (Starter Pack)",
                "full_catalog": False,
                "allowed_grids": ALL_GRID_MODES,
                "days_left": None,
            }

        with self._connect() as conn:
            row = conn.execute(
                "SELECT tier, tier_expires_at, is_admin FROM users WHERE username = ?",
                (self.current_user,)
            ).fetchone()

        if not row:
            return {"tier": "FREE", "display_name": "Free", "full_catalog": False, "allowed_grids": ALL_GRID_MODES, "days_left": None}

        tier, expires_at_str, is_admin_int = row
        self.is_admin = bool(is_admin_int)

        if self.is_admin or tier == "ADMIN":
            return {
                "tier": "ADMIN",
                "display_name": "Admin Master (Full Access)",
                "full_catalog": True,
                "allowed_grids": ALL_GRID_MODES,
                "days_left": None,
            }

        if tier == "LIFETIME":
            return {
                "tier": "LIFETIME",
                "display_name": "Lifetime Pro (All Packs)",
                "full_catalog": True,
                "allowed_grids": ALL_GRID_MODES,
                "days_left": None,
            }

        # Check time-limited tiers (SUBSCRIPTION or DEMO_30D)
        now = datetime.now()
        days_left = 0
        is_active = False
        if expires_at_str:
            try:
                exp_dt = datetime.fromisoformat(expires_at_str)
                if exp_dt > now:
                    is_active = True
                    days_left = max(1, (exp_dt - now).days)
            except ValueError:
                pass

        if tier == "SUBSCRIPTION" and is_active:
            return {
                "tier": "SUBSCRIPTION",
                "display_name": f"Monthly Pro Sub ({days_left}d left)",
                "full_catalog": True,
                "allowed_grids": ALL_GRID_MODES,
                "days_left": days_left,
            }

        if tier == "DEMO_30D" and is_active:
            return {
                "tier": "DEMO_30D",
                "display_name": f"30-Day Demo ({days_left}d left)",
                "full_catalog": False,
                "allowed_grids": ALL_GRID_MODES,
                "days_left": days_left,
            }

        # Downgrade expired Demo/Sub to FREE while preserving any individually purchased packs
        with self._connect() as conn:
            conn.execute("UPDATE users SET tier = 'FREE' WHERE username = ?", (self.current_user,))
            conn.commit()

        owned_individual = self.get_individual_packs()
        has_paid_packs = len(owned_individual - {"Starter_Pack"}) > 0
        return {
            "tier": "INDIVIDUAL" if has_paid_packs else "FREE",
            "display_name": "Individual Pack Owner" if has_paid_packs else "Free Tier (Starter Pack)",
            "full_catalog": False,
            "allowed_grids": ALL_GRID_MODES,
            "days_left": 0,
        }

    def get_individual_packs(self) -> Set[str]:
        packs = {"Starter_Pack"}
        if not self.current_user:
            return packs
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT pack_name FROM user_entitlements WHERE username = ?",
                (self.current_user,)
            ).fetchall()
        for (p,) in rows:
            packs.add(p)
        return packs

    def get_unlocked_packs(self) -> Set[str]:
        """Returns the exact set of packs unlocked by the user's active tier + individual purchases."""
        status = self.get_tier_status()
        unlocked = self.get_individual_packs()
        if status["tier"] == "DEMO_30D":
            unlocked.update(DEMO_INCLUDED_PACKS)
        return unlocked

    # =========================================================================
    # PRODUCT KEY & TIER REDEMPTION
    # =========================================================================

    def redeem_product_key(self, raw_key: str, available_pack_names: List[str]) -> Tuple[bool, str]:
        if not self.current_user:
            return False, "Please sign in first so your key/tier is saved to your account."

        key = raw_key.strip().upper()
        now = datetime.now()
        now_iso = now.isoformat(timespec="seconds")

        # 1. Admin Master Key
        if key == ADMIN_MASTER_KEY:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE users SET tier = 'ADMIN', tier_expires_at = NULL, is_admin = 1 WHERE username = ?",
                    (self.current_user,)
                )
                conn.commit()
            self.is_admin = True
            return True, "Admin Master Key activated! Full catalog and Admin privileges unlocked."

        # 2. Lifetime Pro Key: AURRAS-LIFE-<USER4>-<SIG>
        if hmac.compare_digest(key, self.generate_lifetime_key(self.current_user)):
            with self._connect() as conn:
                conn.execute(
                    "UPDATE users SET tier = 'LIFETIME', tier_expires_at = NULL WHERE username = ?",
                    (self.current_user,)
                )
                conn.commit()
            return True, f"Lifetime Pro License activated for {self.current_user}! All packs & Full (36) unlocked forever."

        # 3. Monthly Subscription Key: AURRAS-SUB30-<NONCE>-<SIG>
        parts = key.split("-")
        if len(parts) == 4 and parts[0] == "AURRAS" and parts[1] == "SUB30":
            nonce = parts[2]
            expected_sub = self.generate_subscription_key(self.current_user, nonce)
            if hmac.compare_digest(key, expected_sub):
                with self._connect() as conn:
                    row = conn.execute(
                        "SELECT tier, tier_expires_at FROM users WHERE username = ?",
                        (self.current_user,)
                    ).fetchone()
                    base_dt = now
                    if row and row[0] == "SUBSCRIPTION" and row[1]:
                        try:
                            existing_exp = datetime.fromisoformat(row[1])
                            if existing_exp > now:
                                base_dt = existing_exp  # Stack 30 days onto remaining subscription
                        except ValueError:
                            pass
                    new_exp = (base_dt + timedelta(days=30)).isoformat(timespec="seconds")
                    conn.execute(
                        "UPDATE users SET tier = 'SUBSCRIPTION', tier_expires_at = ? WHERE username = ?",
                        (new_exp, self.current_user)
                    )
                    conn.commit()
                return True, f"Monthly Pro Subscription activated! Active through {new_exp[:10]}."

        # 4. Individual Pack Key: AURRAS-PACK-<TAG>-<SIG>
        for pack_name in available_pack_names:
            if hmac.compare_digest(key, self.generate_pack_key(pack_name)):
                with self._connect() as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO user_entitlements (username, pack_name, product_key, unlocked_at) "
                        "VALUES (?, ?, ?, ?)",
                        (self.current_user, pack_name, key, now_iso)
                    )
                    conn.commit()
                return True, f"Individual Pack '{pack_name}' unlocked permanently on {self.current_user}'s account!"

        return False, "Invalid Product Key (or key is bound to a different username)."