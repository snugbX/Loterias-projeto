import datetime
import json
import os
import re
import sqlite3
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

import gerador_loterias


ROLE_ADMIN = "admin"
ROLE_USER = "user"
PLAN_FREE = "free"
PLAN_PREMIUM = "premium"

VALID_ROLES = {ROLE_ADMIN, ROLE_USER}
VALID_PLANS = {PLAN_FREE, PLAN_PREMIUM}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

AUTH_DB_PATH = gerador_loterias.resolve_project_path(
    os.environ.get(
        "AUTH_DB_PATH",
        os.path.join(gerador_loterias.PROJECT_ROOT, "data", "loterias_auth.sqlite3")
    )
)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def today_key():
    return datetime.date.today().isoformat()


def normalize_email(email):
    return (email or "").strip().lower()


def validate_email(email):
    email = normalize_email(email)
    return bool(email and len(email) <= 254 and EMAIL_PATTERN.match(email))


def validate_password(password):
    password = password or ""

    if len(password) < 10:
        return False, "A senha precisa ter pelo menos 10 caracteres."

    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return False, "Use letras e numeros na senha."

    return True, ""


def _connect():
    db_path = Path(AUTH_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    _ensure_schema(connection)
    return connection


def _ensure_schema(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            plan TEXT NOT NULL DEFAULT 'free',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_login_at TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_days (
            user_id INTEGER NOT NULL,
            usage_date TEXT NOT NULL,
            generated_games INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, usage_date),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER,
            action TEXT NOT NULL,
            target_user_id INTEGER,
            details_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (target_user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at)"
    )
    connection.commit()


def serialize_user(row, include_email=True):
    if row is None:
        return None

    user = {
        "id": row["id"],
        "name": row["name"],
        "role": row["role"],
        "plan": row["plan"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
        "is_admin": row["role"] == ROLE_ADMIN,
        "is_premium": row["role"] == ROLE_ADMIN or row["plan"] == PLAN_PREMIUM,
    }

    if include_email:
        user["email"] = row["email"]

    return user


def get_user_by_id(user_id):
    if not user_id:
        return None

    connection = _connect()

    try:
        row = connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
    finally:
        connection.close()

    return serialize_user(row)


def get_user_by_email(email):
    email = normalize_email(email)
    connection = _connect()

    try:
        row = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()
    finally:
        connection.close()

    return row


def admin_exists():
    connection = _connect()

    try:
        row = connection.execute(
            "SELECT 1 FROM users WHERE role = ? LIMIT 1",
            (ROLE_ADMIN,)
        ).fetchone()
    finally:
        connection.close()

    return row is not None


def create_user(name, email, password, role=ROLE_USER, plan=PLAN_FREE):
    name = (name or "").strip()
    email = normalize_email(email)
    role = role if role in VALID_ROLES else ROLE_USER
    plan = plan if plan in VALID_PLANS else PLAN_FREE

    if not name or len(name) > 120:
        raise ValueError("Informe um nome valido.")

    if not validate_email(email):
        raise ValueError("Informe um e-mail valido.")

    valid_password, password_message = validate_password(password)

    if not valid_password:
        raise ValueError(password_message)

    created_at = now_iso()
    password_hash = generate_password_hash(
        password,
        method="pbkdf2:sha256:600000",
        salt_length=16,
    )
    connection = _connect()

    try:
        cursor = connection.execute(
            """
            INSERT INTO users
                (name, email, password_hash, role, plan, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (name, email, password_hash, role, plan, created_at, created_at)
        )
        connection.commit()
        user_id = cursor.lastrowid
        row = connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
    except sqlite3.IntegrityError:
        raise ValueError("Ja existe uma conta com este e-mail.")
    finally:
        connection.close()

    log_audit(user_id, "user.created", user_id, {"role": role, "plan": plan})
    return serialize_user(row)


def verify_user_credentials(email, password):
    row = get_user_by_email(email)

    if row is None:
        return None

    if not row["is_active"]:
        return None

    if not check_password_hash(row["password_hash"], password or ""):
        return None

    user_id = row["id"]
    login_at = now_iso()
    connection = _connect()

    try:
        connection.execute(
            "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
            (login_at, login_at, user_id)
        )
        connection.commit()
        refreshed = connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
    finally:
        connection.close()

    log_audit(user_id, "user.login", user_id)
    return serialize_user(refreshed)


def get_daily_usage(user_id, usage_date=None):
    usage_date = usage_date or today_key()
    connection = _connect()

    try:
        row = connection.execute(
            """
            SELECT generated_games
            FROM usage_days
            WHERE user_id = ? AND usage_date = ?
            """,
            (user_id, usage_date)
        ).fetchone()
    finally:
        connection.close()

    return int(row["generated_games"]) if row else 0


def usage_summary(user, free_limit):
    if user is None:
        return None

    used = get_daily_usage(user["id"])
    is_unlimited = user["is_premium"]

    return {
        "used_today": used,
        "free_daily_limit": free_limit,
        "remaining_today": None if is_unlimited else max(free_limit - used, 0),
        "is_unlimited": is_unlimited,
    }


def can_generate_games(user, requested_games, free_limit):
    if user is None:
        return False, "Entre na sua conta para gerar jogos."

    if user["is_premium"]:
        return True, ""

    used = get_daily_usage(user["id"])

    if used + requested_games > free_limit:
        remaining = max(free_limit - used, 0)
        return (
            False,
            f"Plano gratuito: voce ainda pode gerar {remaining} jogo(s) hoje."
        )

    return True, ""


def record_generated_games(user_id, generated_games):
    if not user_id or generated_games <= 0:
        return

    usage_date = today_key()
    connection = _connect()

    try:
        connection.execute(
            """
            INSERT INTO usage_days (user_id, usage_date, generated_games)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, usage_date)
            DO UPDATE SET generated_games = generated_games + excluded.generated_games
            """,
            (user_id, usage_date, generated_games)
        )
        connection.commit()
    finally:
        connection.close()


def list_users():
    connection = _connect()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM users
            ORDER BY role = 'admin' DESC, created_at DESC
            """
        ).fetchall()
    finally:
        connection.close()

    return [serialize_user(row) for row in rows]


def update_user_plan(user_id, plan):
    if plan not in VALID_PLANS:
        raise ValueError("Plano invalido.")

    updated_at = now_iso()
    connection = _connect()

    try:
        cursor = connection.execute(
            """
            UPDATE users
            SET plan = ?, updated_at = ?
            WHERE id = ? AND role != 'admin'
            """,
            (plan, updated_at, user_id)
        )
        connection.commit()

        if cursor.rowcount == 0:
            return None

        row = connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
    finally:
        connection.close()

    return serialize_user(row)


def log_audit(actor_user_id, action, target_user_id=None, details=None):
    details_json = json.dumps(details or {}, ensure_ascii=False)
    connection = _connect()

    try:
        connection.execute(
            """
            INSERT INTO audit_logs
                (actor_user_id, action, target_user_id, details_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (actor_user_id, action, target_user_id, details_json, now_iso())
        )
        connection.commit()
    finally:
        connection.close()
