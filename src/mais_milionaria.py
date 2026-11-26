"""Rules and incremental public-result import for a simple +Milionaria bet."""

import csv
from datetime import datetime
import io
import json
import re
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

SOURCE = 'https://servicebus2.caixa.gov.br/portaldeloterias/api/maismilionaria'
COLUMNS = ['Concurso', 'Data', *[f'bola {i}' for i in range(1, 7)], 'Trevo 1', 'Trevo 2']
TIERS = [(6, (2,)), (6, (0, 1)), (5, (2,)), (5, (0, 1)), (4, (2,)),
         (4, (0, 1)), (3, (2,)), (3, (1,)), (2, (2,)), (2, (1,))]


class OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if (parsed.scheme != 'https' or parsed.netloc != urlsplit(SOURCE).netloc
                or not re.fullmatch(r'/portaldeloterias/api/maismilionaria(?:/[1-9]\d{0,4})?/?', parsed.path)):
            raise ValueError('Redirecionamento fora da fonte oficial da +Milionária.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_trevos(values):
    if (not isinstance(values, (list, tuple)) or len(values) != 2
            or any(type(n) is not int or not 1 <= n <= 6 for n in values)
            or len(set(values)) != 2):
        raise ValueError('Escolha dois trevos diferentes, de 1 a 6.')
    return tuple(sorted(values))


def tier_label(hits, trevos):
    return f'{hits} acertos + ' + ('1 ou nenhum trevo' if len(trevos) == 2 else f'{trevos[0]} ' + ('trevo' if trevos[0] == 1 else 'trevos'))


def prize_label(hits, trevo_hits):
    return next((tier_label(h, t) for h, t in TIERS if h == hits and trevo_hits in t), None)


def validated_result(payload, expected=None):
    if not isinstance(payload, dict) or payload.get('tipoJogo') != 'MAIS_MILIONARIA':
        raise ValueError('A fonte não retornou um resultado da +Milionária.')
    contest = payload.get('numero')
    if type(contest) is not int or not 1 <= contest <= 10000 or expected is not None and contest != expected:
        raise ValueError('Concurso divergente na fonte da +Milionária.')
    try:
        date = datetime.strptime(payload.get('dataApuracao'), '%d/%m/%Y').strftime('%d/%m/%Y')
    except (ValueError, TypeError) as error:
        raise ValueError('Data inválida no resultado da +Milionária.') from error
    def integers(values, count, maximum):
        if not isinstance(values, list) or len(values) != count or any(not isinstance(v, str) or not v.isdigit() for v in values):
            raise ValueError('Formato das dezenas/trevos alterado na fonte.')
        numbers = [int(v) for v in values]
        if len(set(numbers)) != count or any(not 1 <= n <= maximum for n in numbers):
            raise ValueError('Dezenas/trevos inválidos na fonte.')
        return sorted(numbers)
    numbers = integers(payload.get('listaDezenas'), 6, 50)
    trevos = integers(payload.get('trevosSorteados'), 2, 6)
    return [str(contest), date, *map(str, numbers), *map(str, trevos)]


def fetch_result(contest, timeout):
    url = SOURCE + (f'/{contest}' if contest else '')
    opener = build_opener(OfficialRedirects())
    for attempt in range(3):
        try:
            with opener.open(Request(url, headers={'Accept': 'application/json', 'User-Agent': 'SnugbX-Loterias/1.0 (public results updater)'}), timeout=timeout) as response:
                data = response.read(250001)
                if len(data) > 250000:
                    raise ValueError('Resposta pública acima do limite permitido.')
                payload = json.loads(data)
            return validated_result(payload, contest)
        except (HTTPError, URLError, TimeoutError) as error:
            if isinstance(error, HTTPError) and error.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 2:
                raise
            delay = 2 ** (attempt + 1)
            if isinstance(error, HTTPError):
                retry_after = error.headers.get('Retry-After', '') if error.headers else ''
                if retry_after.isdigit():
                    delay = max(delay, int(retry_after))
                if delay > 60:
                    raise
            time.sleep(delay)


def validate_csv_row(row):
    if not isinstance(row, list) or len(row) != len(COLUMNS) or any(not isinstance(value, str) for value in row):
        raise ValueError('Linha incompleta da +Milionária.')
    contest = int(row[0])
    if contest < 1:
        raise ValueError('Concurso inválido.')
    datetime.strptime(row[1], '%d/%m/%Y')
    numbers = [int(n) for n in row[2:8]]
    if len(set(numbers)) != 6 or any(not 1 <= n <= 50 for n in numbers):
        raise ValueError('Dezenas inválidas.')
    validate_trevos([int(n) for n in row[8:10]])
    return contest


def collect_rows(path, timeout=30, force=False):
    """Never replace the CSV with a partial import; cache permits safe resumption."""
    path = Path(path)
    latest = fetch_result(None, timeout)
    maximum = int(latest[0])
    records = {}
    if path.exists():
        old = list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig', errors='replace' if force else 'strict'))))
        valid_header = len(old) >= 8 and old[6] == COLUMNS
        if not valid_header and not force:
            raise ValueError('Cabeçalho local da +Milionária precisa de revisão.')
        for row in old[7:] if valid_header else []:
            if not row:
                continue
            try:
                contest = validate_csv_row(row)
            except ValueError:
                if force:
                    continue
                raise
            if contest in records and records[contest] != row:
                if not force:
                    raise ValueError('Concursos conflitantes na base local.')
            records[contest] = row
    if records and max(records) > maximum:
        raise ValueError('A fonte retornou um concurso anterior à base local; atualização cancelada.')
    if not force and maximum in records and records[maximum] != latest:
        raise ValueError('O último concurso diverge da fonte oficial. Revise antes de usar --force.')
    if not force and set(range(1, maximum + 1)).issubset(records):
        return None
    records[maximum] = latest
    cache = path.parent / '.lottery-cache' / 'maismilionaria'
    cache.mkdir(parents=True, exist_ok=True)
    for contest in range(1, maximum):
        if contest in records and not force:
            continue
        cached = cache / f'{contest}.json'
        row = None
        if cached.exists() and not force:
            try:
                candidate = json.loads(cached.read_text(encoding='utf-8'))
                if validate_csv_row(candidate) == contest:
                    row = candidate
            except (ValueError, TypeError, OSError):
                pass
        if row is None:
            row = fetch_result(contest, timeout)
            temporary = cached.with_suffix('.tmp')
            temporary.write_text(json.dumps(row), encoding='utf-8')
            temporary.replace(cached)
            time.sleep(.15)
        records[contest] = row
    return [['Resultados públicos +Milionária'], [f'Fonte: {SOURCE}'],
            ['Dezenas e trevos em ordem crescente'], [], [], [], COLUMNS,
            *[records[n] for n in sorted(records, reverse=True)]]
