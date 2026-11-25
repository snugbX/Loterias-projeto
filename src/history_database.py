import datetime
import json
import os
import sqlite3
from pathlib import Path

import gerador_loterias
import database


HISTORY_DB_PATH = gerador_loterias.resolve_project_path(
    os.environ.get(
        "LOTTERY_HISTORY_DB",
        os.path.join(gerador_loterias.OUTPUT_DIR, "loterias_history.sqlite3")
    )
)


def _connect():
    if database.postgres_enabled():
        return database.open_postgres()
    db_path = Path(HISTORY_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    _ensure_schema(connection)
    return connection


def _ensure_schema(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS generated_games (
            owner_key TEXT NOT NULL,
            filename TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            games_json TEXT NOT NULL,
            PRIMARY KEY (owner_key, filename)
        )
        """
    )

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(generated_games)").fetchall()
    }

    if "owner_key" not in columns:
        connection.execute("ALTER TABLE generated_games RENAME TO generated_games_legacy")
        connection.execute(
            """
            CREATE TABLE generated_games (
                owner_key TEXT NOT NULL,
                filename TEXT NOT NULL,
                lottery_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                games_json TEXT NOT NULL,
                PRIMARY KEY (owner_key, filename)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO generated_games
                (owner_key, filename, lottery_type, created_at, games_json)
            SELECT 'legacy', filename, lottery_type, created_at, games_json
            FROM generated_games_legacy
            """
        )
        connection.execute("DROP TABLE generated_games_legacy")

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_generated_games_owner_lottery
        ON generated_games(owner_key, lottery_type, filename)
        """
    )
    connection.execute('''CREATE TABLE IF NOT EXISTS history_tracking (
        owner_key TEXT NOT NULL, filename TEXT NOT NULL, settings_json TEXT NOT NULL,
        PRIMARY KEY(owner_key, filename),
        FOREIGN KEY(owner_key, filename) REFERENCES generated_games(owner_key, filename) ON DELETE CASCADE
    )''')
    connection.commit()


def save_history_record(filename, lottery_type, games, created_at=None, owner_key="legacy"):
    owner_key = owner_key or "legacy"
    created_at = created_at or datetime.datetime.now().isoformat(timespec="seconds")
    games_json = json.dumps(games, ensure_ascii=False)

    connection = _connect()

    try:
        connection.execute(
            """
            INSERT INTO generated_games
                (owner_key, filename, lottery_type, created_at, games_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(owner_key, filename) DO UPDATE SET
                lottery_type = excluded.lottery_type,
                created_at = excluded.created_at,
                games_json = excluded.games_json
            """,
            (owner_key, filename, lottery_type, created_at, games_json)
        )
        connection.commit()
    finally:
        connection.close()


def list_history_files(lottery_type, owner_key):
    connection = _connect()

    try:
        rows = connection.execute(
            """
            SELECT filename
            FROM generated_games
            WHERE owner_key = ? AND lottery_type = ?
            ORDER BY filename DESC
            """,
            (owner_key, lottery_type)
        ).fetchall()
    finally:
        connection.close()

    return [row["filename"] for row in rows]


def read_history_file(filename, owner_key):
    connection = _connect()

    try:
        row = connection.execute(
            """
            SELECT games_json
            FROM generated_games
            WHERE owner_key = ? AND filename = ?
            """,
            (owner_key, filename)
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    return json.loads(row["games_json"])


def delete_history_file(filename, owner_key):
    connection = _connect()

    try:
        cursor = connection.execute(
            "DELETE FROM generated_games WHERE owner_key = ? AND filename = ?",
            (owner_key, filename)
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def clear_history(lottery_type, owner_key):
    filenames = list_history_files(lottery_type, owner_key)

    connection = _connect()

    try:
        connection.execute(
            "DELETE FROM generated_games WHERE owner_key = ? AND lottery_type = ?",
            (owner_key, lottery_type)
        )
        connection.commit()
    finally:
        connection.close()

    return filenames


def tracked_records(lottery_type, owner_key):
    connection = _connect()
    try:
        return [dict(row) for row in connection.execute('''
            SELECT g.filename, g.created_at, g.games_json, t.settings_json
            FROM generated_games g LEFT JOIN history_tracking t
            ON t.owner_key = g.owner_key AND t.filename = g.filename
            WHERE g.owner_key = ? AND g.lottery_type = ?
            ORDER BY g.filename DESC LIMIT 1001''', (owner_key, lottery_type)).fetchall()]
    finally:
        connection.close()


def game_settings(filename, owner_key):
    connection = _connect()
    try:
        row = connection.execute('SELECT settings_json FROM history_tracking WHERE owner_key = ? AND filename = ?', (owner_key, filename)).fetchone()
        return json.loads(row['settings_json']) if row else {}
    finally:
        connection.close()


def update_game_settings(filename, owner_key, index, changes):
    connection = _connect()
    try:
        if database.postgres_enabled():
            row = connection.execute('SELECT games_json FROM generated_games WHERE owner_key = ? AND filename = ? FOR UPDATE', (owner_key, filename)).fetchone()
        else:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT games_json FROM generated_games WHERE owner_key = ? AND filename = ?', (owner_key, filename)).fetchone()
        if row is None or not 0 <= index < len(json.loads(row['games_json'])):
            return False
        saved = connection.execute('SELECT settings_json FROM history_tracking WHERE owner_key = ? AND filename = ?', (owner_key, filename)).fetchone()
        settings = json.loads(saved['settings_json']) if saved else {}
        state = settings.get(str(index), {})
        if state.get('deleted'):
            return False
        settings[str(index)] = {**state, **changes}
        connection.execute('''INSERT INTO history_tracking(owner_key, filename, settings_json) VALUES (?, ?, ?)
            ON CONFLICT(owner_key, filename) DO UPDATE SET settings_json = excluded.settings_json''',
            (owner_key, filename, json.dumps(settings, ensure_ascii=False)))
        connection.commit()
        return True
    finally:
        connection.close()
