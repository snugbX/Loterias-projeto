import os
import re
from pathlib import Path

import pandas as pd

import gerador_loterias


HISTORY_FILENAME_PATTERN = re.compile(
    r"^(megasena|lotofacil|quina)_resultados_"
    r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.csv$",
    re.IGNORECASE
)


def history_file_path(filename):
    if os.path.basename(filename) != filename:
        return None

    if not HISTORY_FILENAME_PATTERN.match(filename):
        return None

    history_dir = Path(gerador_loterias.OUTPUT_DIR).resolve()
    file_path = (history_dir / filename).resolve()

    try:
        file_path.relative_to(history_dir)
    except ValueError:
        return None

    return file_path


def list_history_files(lottery_type):
    history_dir = Path(gerador_loterias.OUTPUT_DIR)

    if not history_dir.exists():
        gerador_loterias.logging.warning(
            f"Diretorio de historico nao encontrado: {history_dir}"
        )
        return []

    files = []

    for filename in os.listdir(history_dir):
        match = HISTORY_FILENAME_PATTERN.match(filename)

        if match and match.group(1).lower() == lottery_type:
            files.append(filename)

    return sorted(files, reverse=True)


def read_history_file(filename):
    file_path = history_file_path(filename)

    if file_path is None or not file_path.exists() or not file_path.is_file():
        gerador_loterias.logging.warning(
            f"Tentativa de acesso nao autorizado ou arquivo nao encontrado: {filename}"
        )
        return None

    df = pd.read_csv(file_path)
    return df.apply(lambda x: x.astype(int)).values.tolist()


def clear_history(lottery_type):
    history_dir = Path(gerador_loterias.OUTPUT_DIR)

    if not history_dir.exists():
        return 0

    deleted_files_count = 0

    for filename in os.listdir(history_dir):
        match = HISTORY_FILENAME_PATTERN.match(filename)
        file_path = history_file_path(filename)

        if match and match.group(1).lower() == lottery_type and file_path is not None:
            file_path.unlink()
            deleted_files_count += 1
            gerador_loterias.logging.info(
                f"Arquivo de historico deletado: {file_path}"
            )

    return deleted_files_count


def delete_history_file(filename):
    file_path = history_file_path(filename)

    if file_path is None:
        gerador_loterias.logging.warning(
            f"Tentativa de exclusao de arquivo invalido ou fora do diretorio permitido: {filename}"
        )
        return "invalid"

    if not file_path.exists() or not file_path.is_file():
        return "missing"

    file_path.unlink()
    gerador_loterias.logging.info(f"Arquivo deletado: {file_path}")

    return "deleted"
