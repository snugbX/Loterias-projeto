import os
import re
from pathlib import Path

import pandas as pd

import gerador_loterias
import history_database


LOTTERY_TYPES_PATTERN = "|".join(
    re.escape(lottery_type)
    for lottery_type in gerador_loterias.LOTTERY_CONFIGS
)
HISTORY_FILENAME_PATTERN = re.compile(
    rf"^({LOTTERY_TYPES_PATTERN})_resultados_"
    r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:_\d{6})?\.csv$",
    re.IGNORECASE
)
OWNER_SEGMENT_PATTERN = re.compile(r"[^a-zA-Z0-9_.-]+")


def owner_directory_segment(owner_key):
    segment = OWNER_SEGMENT_PATTERN.sub("_", str(owner_key or "legacy")).strip("._-")
    return segment[:80] or "legacy"


def owner_history_dir(owner_key):
    base_dir = Path(gerador_loterias.OUTPUT_DIR).resolve()
    return (base_dir / owner_directory_segment(owner_key)).resolve()


def parse_history_value(value):
    if pd.isna(value):
        return ""

    value = str(value).strip()

    if value.isdigit():
        return int(value)

    return value


def history_file_path(filename, owner_key):
    if os.path.basename(filename) != filename:
        return None

    if not HISTORY_FILENAME_PATTERN.match(filename):
        return None

    history_dir = owner_history_dir(owner_key)
    file_path = (history_dir / filename).resolve()

    try:
        file_path.relative_to(history_dir)
    except ValueError:
        return None

    return file_path


def list_history_files(lottery_type, owner_key):
    history_dir = owner_history_dir(owner_key)
    files = set(history_database.list_history_files(lottery_type, owner_key))

    if not history_dir.exists():
        gerador_loterias.logging.warning(
            f"Diretório de histórico não encontrado: {history_dir}"
        )
        return sorted(files, reverse=True)

    for filename in os.listdir(history_dir):
        match = HISTORY_FILENAME_PATTERN.match(filename)

        if match and match.group(1).lower() == lottery_type:
            files.add(filename)

    return sorted(files, reverse=True)


def read_history_file(filename, owner_key):
    if history_file_path(filename, owner_key) is None:
        gerador_loterias.logging.warning(
            f"Tentativa de acesso não autorizado ou arquivo inválido: {filename}"
        )
        return None

    db_data = history_database.read_history_file(filename, owner_key)

    if db_data is not None:
        return db_data

    file_path = history_file_path(filename, owner_key)

    if file_path is None or not file_path.exists() or not file_path.is_file():
        gerador_loterias.logging.warning(
            f"Tentativa de acesso não autorizado ou arquivo não encontrado: {filename}"
        )
        return None

    df = pd.read_csv(file_path)
    return [
        [parse_history_value(value) for value in row]
        for row in df.itertuples(index=False, name=None)
    ]


def clear_history(lottery_type, owner_key):
    history_dir = owner_history_dir(owner_key)
    deleted_filenames = set(history_database.clear_history(lottery_type, owner_key))

    if not history_dir.exists():
        return len(deleted_filenames)

    for filename in os.listdir(history_dir):
        match = HISTORY_FILENAME_PATTERN.match(filename)
        file_path = history_file_path(filename, owner_key)

        if match and match.group(1).lower() == lottery_type and file_path is not None:
            file_path.unlink()
            deleted_filenames.add(filename)
            gerador_loterias.logging.info(
                f"Arquivo de histórico deletado: {file_path}"
            )

    return len(deleted_filenames)


def delete_history_file(filename, owner_key):
    file_path = history_file_path(filename, owner_key)

    if file_path is None:
        gerador_loterias.logging.warning(
            f"Tentativa de exclusão de arquivo inválido ou fora do diretório permitido: {filename}"
        )
        return "invalid"

    deleted_from_db = history_database.delete_history_file(filename, owner_key)
    file_exists = file_path.exists() and file_path.is_file()

    if not deleted_from_db and not file_exists:
        return "missing"

    if file_exists:
        file_path.unlink()
        gerador_loterias.logging.info(f"Arquivo deletado: {file_path}")

    return "deleted"
