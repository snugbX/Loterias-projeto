import datetime
import json
import os
import sqlite3
from pathlib import Path

import gerador_loterias


HISTORY_DB_PATH = gerador_loterias.resolve_project_path(
    os.environ.get(
        "LOTTERY_HISTORY_DB",
        os.path.join(gerador_loterias.OUTPUT_DIR, "loterias_history.sqlite3")
    )
)


def _connect():
    db_path = Path(HISTORY_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    _ensure_schema(connection)
    return connection


def _ensure_schema(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS generated_games (
            filename TEXT PRIMARY KEY,
            lottery_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            games_json TEXT NOT NULL
        )
        """
    )
    connection.commit()


def save_history_record(filename, lottery_type, games, created_at=None):
    created_at = created_at or datetime.datetime.now().isoformat(timespec="seconds")
    games_json = json.dumps(games, ensure_ascii=False)

    connection = _connect()

    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO generated_games
                (filename, lottery_type, created_at, games_json)
            VALUES (?, ?, ?, ?)
            """,
            (filename, lottery_type, created_at, games_json)
        )
        connection.commit()
    finally:
        connection.close()


def list_history_files(lottery_type):
    connection = _connect()

    try:
        rows = connection.execute(
            """
            SELECT filename
            FROM generated_games
            WHERE lottery_type = ?
            ORDER BY filename DESC
            """,
            (lottery_type,)
        ).fetchall()
    finally:
        connection.close()

    return [row["filename"] for row in rows]


def read_history_file(filename):
    connection = _connect()

    try:
        row = connection.execute(
            """
            SELECT games_json
            FROM generated_games
            WHERE filename = ?
            """,
            (filename,)
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    return json.loads(row["games_json"])


def delete_history_file(filename):
    connection = _connect()

    try:
        cursor = connection.execute(
            "DELETE FROM generated_games WHERE filename = ?",
            (filename,)
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def clear_history(lottery_type):
    filenames = list_history_files(lottery_type)

    connection = _connect()

    try:
        connection.execute(
            "DELETE FROM generated_games WHERE lottery_type = ?",
            (lottery_type,)
        )
        connection.commit()
    finally:
        connection.close()

    return filenames
