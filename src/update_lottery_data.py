import argparse
import csv
import io
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from gerador_loterias import LOTTERY_CONFIGS, PROJECT_ROOT


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)
DOWNLOAD_ENDPOINT = "https://asloterias.com.br/download_excel.php"
BACKUP_DIR = Path(PROJECT_ROOT) / "backups_loterias"
ORDER_CODES = {
    "sorteio": "s",
    "crescente": "c",
}
DOWNLOAD_CONFIGS = {
    "megasena": {
        "name": "Mega Sena",
        "page_url": "https://asloterias.com.br/download-todos-resultados-mega-sena",
        "fallback_payload": {"l": "ms", "t": "t", "o": "s", "f1": "", "f2": ""},
        "override_env": "ASLOTERIAS_MEGASENA_URL",
    },
    "lotofacil": {
        "name": "Lotofacil",
        "page_url": "https://asloterias.com.br/download-todos-resultados-lotofacil",
        "fallback_payload": {"l": "lf", "t": "t", "o": "s", "f1": "", "f2": ""},
        "override_env": "ASLOTERIAS_LOTOFACIL_URL",
    },
    "quina": {
        "name": "Quina",
        "page_url": "https://asloterias.com.br/download-todos-resultados-quina",
        "fallback_payload": {"l": "qi", "t": "t", "o": "s", "f1": "", "f2": ""},
        "override_env": "ASLOTERIAS_QUINA_URL",
    },
    "diadesorte": {
        "name": "Dia de Sorte",
        "page_url": "https://asloterias.com.br/download-todos-resultados-dia-de-sorte",
        "fallback_payload": {"l": "dd", "t": "t", "o": "s", "f1": "", "f2": ""},
        "override_env": "ASLOTERIAS_DIADESORTE_URL",
    },
}


def env_flag(name, default=False):
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = os.environ.get(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


@dataclass
class DownloadResult:
    lottery_type: str
    source_url: str
    filename: str
    content_type: str
    data: bytes
    remote_contest: int = None
    skipped: bool = False
    skip_reason: str = ""


class DownloadFormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self._current_form = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag.lower() == "form":
            self._current_form = {
                "action": attrs.get("action", ""),
                "method": attrs.get("method", "get").lower(),
                "inputs": {},
            }
            return

        if tag.lower() == "input" and self._current_form is not None:
            name = attrs.get("name")
            if name:
                self._current_form["inputs"][name] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag.lower() == "form" and self._current_form is not None:
            self.forms.append(self._current_form)
            self._current_form = None


def build_request(url, data=None, referer=None):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
    }

    if referer:
        headers["Referer"] = referer

    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    return urllib.request.Request(url, data=data, headers=headers)


def fetch_bytes(url, timeout, data=None, referer=None):
    request = build_request(url, data=data, referer=referer)

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return (
            response.read(),
            response.headers.get("content-type", ""),
            response.headers.get("content-disposition", ""),
            response.geturl(),
        )


def fetch_download(
    lottery_type,
    url,
    timeout,
    data=None,
    referer=None,
    fallback_filename=None,
    local_contest=None,
    skip_current=True,
):
    request = build_request(url, data=data, referer=referer)

    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        disposition = response.headers.get("content-disposition", "")
        final_url = response.geturl()
        fallback = (
            fallback_filename
            or Path(urllib.parse.urlparse(final_url).path).name
            or f"{lottery_type}.xlsx"
        )
        filename = filename_from_disposition(disposition, fallback)
        remote_contest = contest_from_filename(filename)

        if (
            skip_current
            and local_contest is not None
            and remote_contest is not None
            and int(local_contest) >= remote_contest
        ):
            return DownloadResult(
                lottery_type=lottery_type,
                source_url=final_url,
                filename=filename,
                content_type=content_type,
                data=b"",
                remote_contest=remote_contest,
                skipped=True,
                skip_reason=(
                    f"local no concurso {local_contest}; "
                    f"site informa concurso {remote_contest}"
                ),
            )

        return DownloadResult(
            lottery_type=lottery_type,
            source_url=final_url,
            filename=filename,
            content_type=content_type,
            data=response.read(),
            remote_contest=remote_contest,
        )


def filename_from_disposition(content_disposition, fallback):
    match = re.search(r'filename="?([^";]+)"?', content_disposition or "", re.I)
    if match:
        return match.group(1).strip()

    return fallback


def contest_from_filename(filename):
    match = re.search(r"_ate_concurso_(\d+)", filename or "", re.I)

    if not match:
        return None

    return int(match.group(1))


def latest_contest_from_rows(rows, skip_rows):
    if len(rows) <= skip_rows + 1:
        return None

    header = rows[skip_rows]
    if "Concurso" not in header:
        return None

    contest_index = header.index("Concurso")
    date_index = header.index("Data") if "Data" in header else None
    latest = None

    for row in rows[skip_rows + 1:]:
        if contest_index >= len(row):
            continue

        contest = str(row[contest_index]).strip()
        if not contest.isdigit():
            continue

        contest_number = int(contest)
        date_value = ""

        if date_index is not None and date_index < len(row):
            date_value = str(row[date_index]).strip()

        if latest is None or contest_number > latest["contest"]:
            latest = {
                "contest": contest_number,
                "date": date_value,
            }

    return latest


def local_latest_contest(lottery_type):
    target_path = Path(LOTTERY_CONFIGS[lottery_type]["FILE_PATH"])

    if not target_path.exists():
        return None

    rows = csv_to_rows(target_path.read_bytes())

    return latest_contest_from_rows(
        rows,
        int(LOTTERY_CONFIGS[lottery_type]["SKIP_ROWS"])
    )


def find_download_form(page_url, order_code, timeout):
    html_bytes, _, _, _ = fetch_bytes(page_url, timeout)
    html = html_bytes.decode("utf-8", errors="replace")

    parser = DownloadFormParser()
    parser.feed(html)

    for form in parser.forms:
        inputs = form.get("inputs", {})
        action = form.get("action", "")

        if "download_excel.php" in action and inputs.get("o") == order_code:
            return {
                "action": urllib.parse.urljoin(page_url, action),
                "inputs": inputs,
            }

    return None


def download_lottery_file(
    lottery_type,
    order,
    timeout,
    local_contest=None,
    skip_current=True,
):
    download_config = DOWNLOAD_CONFIGS[lottery_type]
    override_url = os.environ.get(download_config["override_env"])

    if override_url:
        return fetch_download(
            lottery_type,
            override_url,
            timeout,
            local_contest=local_contest,
            skip_current=skip_current,
            fallback_filename=f"{lottery_type}.xlsx",
        )

    order_code = ORDER_CODES[order]
    page_url = download_config["page_url"]
    form = find_download_form(page_url, order_code, timeout)

    if form:
        action = form["action"]
        payload = dict(form["inputs"])
    else:
        action = DOWNLOAD_ENDPOINT
        payload = dict(download_config["fallback_payload"])
        payload["o"] = order_code

    encoded_payload = urllib.parse.urlencode(payload).encode("utf-8")
    return fetch_download(
        lottery_type,
        action,
        timeout,
        data=encoded_payload,
        referer=page_url,
        fallback_filename=f"{lottery_type}.xlsx",
        local_contest=local_contest,
        skip_current=skip_current,
    )


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def column_index(cell_ref):
    letters = "".join(char for char in cell_ref if char.isalpha())
    index = 0

    for letter in letters:
        index = index * 26 + (ord(letter.upper()) - ord("A") + 1)

    return index - 1


def xml_text(element):
    texts = []

    for child in element.iter():
        if local_name(child.tag) == "t" and child.text:
            texts.append(child.text)

    return "".join(texts)


def read_shared_strings(zip_file):
    try:
        root = ElementTree.fromstring(zip_file.read("xl/sharedStrings.xml"))
    except KeyError:
        return []

    shared_strings = []

    for item in root:
        shared_strings.append(xml_text(item))

    return shared_strings


def read_cell_value(cell, shared_strings):
    cell_type = cell.attrib.get("t")

    if cell_type == "inlineStr":
        return xml_text(cell)

    value = ""
    for child in cell:
        if local_name(child.tag) == "v":
            value = child.text or ""
            break

    if cell_type == "s" and value:
        index = int(value)
        if 0 <= index < len(shared_strings):
            return shared_strings[index]

    return value


def xlsx_to_rows(data):
    with zipfile.ZipFile(io.BytesIO(data)) as zip_file:
        shared_strings = read_shared_strings(zip_file)
        root = ElementTree.fromstring(zip_file.read("xl/worksheets/sheet1.xml"))

    rows_by_number = {}
    max_row_number = 0

    for row in root.iter():
        if local_name(row.tag) != "row":
            continue

        row_number = int(row.attrib.get("r", max_row_number + 1))
        max_row_number = max(max_row_number, row_number)
        values = []

        for cell in row:
            if local_name(cell.tag) != "c":
                continue

            ref = cell.attrib.get("r", "")
            col_index = column_index(ref) if ref else len(values)

            while len(values) <= col_index:
                values.append("")

            values[col_index] = read_cell_value(cell, shared_strings)

        rows_by_number[row_number] = values

    return [rows_by_number.get(row_number, []) for row_number in range(1, max_row_number + 1)]


def csv_to_rows(data):
    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("utf-8", errors="replace")

    return list(csv.reader(io.StringIO(text)))


def downloaded_data_to_rows(download):
    content_type = (download.content_type or "").lower()
    filename = download.filename.lower()

    if download.data.startswith(b"PK\x03\x04") or filename.endswith(".xlsx"):
        return xlsx_to_rows(download.data)

    if "csv" in content_type or filename.endswith(".csv"):
        return csv_to_rows(download.data)

    raise ValueError(
        f"Formato nao reconhecido em {download.filename or download.source_url} "
        f"({download.content_type or 'sem content-type'})."
    )


def write_rows_as_csv(rows, target_path):
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with target_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerows(rows)


def validate_rows(lottery_type, rows):
    config = LOTTERY_CONFIGS[lottery_type]
    skip_rows = int(config["SKIP_ROWS"])

    if len(rows) <= skip_rows + 1:
        raise ValueError("Arquivo baixado tem poucas linhas.")

    header = rows[skip_rows]
    expected_ball_count = int(config["NUM_BALLS_TO_DRAW"])
    ball_columns = [
        column for column in header if column.startswith(config["CSV_COLUMNS_PREFIX"])
    ]

    if "Concurso" not in header or "Data" not in header:
        raise ValueError("Cabecalho esperado nao foi encontrado.")

    if len(ball_columns) != expected_ball_count:
        raise ValueError(
            f"Foram encontradas {len(ball_columns)} colunas de bolas, "
            f"mas eram esperadas {expected_ball_count}."
        )

    first_result = next(
        (row for row in rows[skip_rows + 1:] if any(str(cell).strip() for cell in row)),
        None,
    )
    if not first_result:
        raise ValueError("Nenhum resultado foi encontrado apos o cabecalho.")

    indexes = {name: index for index, name in enumerate(header)}
    contest = first_result[indexes["Concurso"]].strip()
    if not contest.isdigit():
        raise ValueError("Numero do concurso invalido no primeiro resultado.")

    min_number = int(config["MIN_NUMBER"])
    max_number = int(config["MAX_NUMBER"])

    for column in ball_columns:
        value = first_result[indexes[column]].strip()
        if not value.isdigit():
            raise ValueError(f"Valor invalido em {column}: {value!r}")

        number = int(value)
        if number < min_number or number > max_number:
            raise ValueError(
                f"Valor fora da faixa em {column}: {number} "
                f"(esperado {min_number}-{max_number})."
            )

    return {
        "contest": contest,
        "date": first_result[indexes["Data"]].strip(),
        "ball_count": len(ball_columns),
    }


def backup_existing_file(target_path, backup_root):
    if not target_path.exists():
        return None

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = backup_root / timestamp / target_path.name
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target_path, backup_path)
    return backup_path


def replace_csv(lottery_type, rows, make_backup):
    target_path = Path(LOTTERY_CONFIGS[lottery_type]["FILE_PATH"])
    backup_path = None

    if make_backup:
        backup_path = backup_existing_file(target_path, BACKUP_DIR)

    temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    write_rows_as_csv(rows, temp_path)
    os.replace(temp_path, target_path)

    return target_path, backup_path


def cleanup_old_backups(retention_count):
    if retention_count < 0 or not BACKUP_DIR.exists():
        return 0

    backup_dirs = [
        path for path in BACKUP_DIR.iterdir()
        if path.is_dir()
    ]
    backup_dirs.sort(
        key=lambda path: path.stat().st_mtime,
        reverse=True
    )
    deleted_count = 0

    for old_dir in backup_dirs[retention_count:]:
        shutil.rmtree(old_dir)
        deleted_count += 1

    return deleted_count


def update_lottery(lottery_type, args):
    name = DOWNLOAD_CONFIGS[lottery_type]["name"]
    print(f"\n== {name} ==")
    local_summary = local_latest_contest(lottery_type)

    if local_summary:
        print(
            "Local atual: concurso "
            f"{local_summary['contest']} em {local_summary['date'] or 'data nao informada'}."
        )

    print("Verificando dados no site...")

    download = download_lottery_file(
        lottery_type,
        args.order,
        args.timeout,
        local_contest=local_summary["contest"] if local_summary else None,
        skip_current=not args.force,
    )
    print(f"Arquivo recebido: {download.filename}")

    if download.skipped:
        print(f"Sem atualizacao necessaria: {download.skip_reason}.")
        return None

    rows = downloaded_data_to_rows(download)
    summary = validate_rows(lottery_type, rows)
    print(
        "Validado: concurso "
        f"{summary['contest']} em {summary['date']} "
        f"({summary['ball_count']} dezenas)."
    )

    if (
        not args.force
        and local_summary
        and int(summary["contest"]) <= int(local_summary["contest"])
    ):
        print(
            "Sem atualizacao necessaria: "
            f"CSV local ja esta no concurso {local_summary['contest']}."
        )
        return None

    if args.dry_run:
        print("Simulacao concluida. Nenhum CSV foi alterado.")
        return None

    target_path, backup_path = replace_csv(
        lottery_type,
        rows,
        make_backup=not args.no_backup,
    )

    if backup_path:
        print(f"Backup criado: {backup_path}")

    print(f"CSV atualizado: {target_path}")
    return target_path


def list_config():
    for lottery_type, download_config in DOWNLOAD_CONFIGS.items():
        target = Path(LOTTERY_CONFIGS[lottery_type]["FILE_PATH"])
        print(f"{lottery_type}:")
        print(f"  pagina: {download_config['page_url']}")
        print(f"  destino: {target}")
        print(f"  override: {download_config['override_env']}")


def publish_updated_files(updated_paths, args):
    if not args.publish:
        return

    if args.dry_run:
        print("Publicacao ignorada em modo de simulacao.")
        return

    if not updated_paths:
        print("Nenhum CSV foi alterado. Publicacao no GitHub nao sera acionada.")
        return

    publish_script = Path(__file__).with_name("publish_lottery_data.py")
    command = [
        sys.executable,
        str(publish_script),
        "--message",
        args.publish_message,
    ]

    if args.publish_dry_run:
        command.append("--dry-run")

    command.extend(str(path) for path in updated_paths)

    print("\nChamando publicacao no GitHub...")
    completed = subprocess.run(command, cwd=PROJECT_ROOT)

    if completed.returncode != 0:
        raise RuntimeError("Falha ao publicar atualizacao no GitHub.")


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Atualiza os CSVs de resultados a partir do site As Loterias.",
    )
    parser.add_argument(
        "--lottery",
        nargs="+",
        choices=sorted(DOWNLOAD_CONFIGS.keys()),
        default=sorted(DOWNLOAD_CONFIGS.keys()),
        help="Loterias que serao atualizadas.",
    )
    parser.add_argument(
        "--order",
        choices=sorted(ORDER_CODES.keys()),
        default="sorteio",
        help="Ordem dos numeros no arquivo baixado.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Baixa e valida, mas nao substitui os CSVs.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Substitui os CSVs mesmo quando o concurso local ja parece atualizado.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Substitui os CSVs sem salvar copia anterior.",
    )
    parser.add_argument(
        "--backup-retention",
        type=int,
        default=env_int("LOTTERY_BACKUP_RETENTION", 5),
        help="Quantidade de pastas de backup que devem ser mantidas.",
    )
    parser.add_argument(
        "--no-clean-backups",
        action="store_true",
        help="Nao remove backups antigos ao final da atualizacao.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Tempo maximo de cada conexao, em segundos.",
    )
    parser.add_argument(
        "--list-config",
        action="store_true",
        help="Mostra as paginas e os arquivos de destino, sem baixar nada.",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        default=env_flag("LOTTERY_PUBLISH_AFTER_UPDATE", default=False),
        help="Depois de atualizar CSVs, chama o script de publicacao no GitHub.",
    )
    parser.add_argument(
        "--no-publish",
        action="store_false",
        dest="publish",
        help="Desativa publicacao no GitHub mesmo se LOTTERY_PUBLISH_AFTER_UPDATE=1.",
    )
    parser.add_argument(
        "--publish-dry-run",
        action="store_true",
        help="Simula a publicacao no GitHub sem commit nem push.",
    )
    parser.add_argument(
        "--publish-message",
        default=f"Atualiza dados das loterias {time.strftime('%Y-%m-%d')}",
        help="Mensagem de commit usada quando --publish estiver ativo.",
    )

    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])

    if args.list_config:
        list_config()
        return 0

    failed = []
    updated_paths = []
    for lottery_type in args.lottery:
        try:
            updated_path = update_lottery(lottery_type, args)

            if updated_path is not None:
                updated_paths.append(updated_path)
        except Exception as exc:
            failed.append(lottery_type)
            print(f"Erro ao atualizar {lottery_type}: {exc}")

    if failed:
        print("\nAlgumas loterias nao foram atualizadas:", ", ".join(failed))
        return 1

    if not args.dry_run and not args.no_clean_backups:
        deleted_backups = cleanup_old_backups(args.backup_retention)

        if deleted_backups:
            print(f"\nBackups antigos removidos: {deleted_backups}.")

    publish_updated_files(updated_paths, args)

    if not updated_paths and args.dry_run:
        print("\nSimulacao finalizada. Nenhum CSV foi alterado.")
    elif not updated_paths:
        print("\nTodos os CSVs ja estavam atualizados.")

    print("\nAtualizacao finalizada com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
