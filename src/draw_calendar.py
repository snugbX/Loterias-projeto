"""Date-specific public schedule, refreshed from CAIXA without private data."""

from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from io import BytesIO
import logging
import json
from pathlib import Path
import re
import threading
import time
import unicodedata
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from pypdf import PdfReader

SOURCE = 'https://loterias.caixa.gov.br/Paginas/regras-sorteios.aspx'
TIMEZONE = ZoneInfo('America/Sao_Paulo')
NAMES = {'megasena': 'Mega-Sena', 'lotofacil': 'Lotofácil',
         'quina': 'Quina', 'diadesorte': 'Dia de Sorte'}
MONTHS = ('janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro').split()
LABELS = ('Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo')
_lock = threading.Lock()
_cache = {}
_next_attempt = {}
_jobs_lock = threading.Lock()
_refreshing = set()
_refresh_started = {}
SNAPSHOT_PATH = Path(__file__).with_name('public_draw_calendar.json')
SNAPSHOT_TTL = 36 * 3600


def read_snapshot(path=None):
    path = Path(path or SNAPSHOT_PATH)
    if path.stat().st_size > 300_000:
        raise ValueError('Cópia pública acima do limite.')
    payload = json.loads(path.read_text(encoding='utf-8'))
    if set(payload) != {'schema', 'months'} or payload['schema'] != 1 or not isinstance(payload['months'], list) or not 1 <= len(payload['months']) <= 3:
        raise ValueError('Formato da cópia pública inválido.')
    result = {}
    for item in payload['months']:
        if set(item) != {'year', 'month', 'days', 'source', 'checked_at'}:
            raise ValueError('Campos não permitidos na cópia pública.')
        year, month = item['year'], item['month']
        first = date(year, month, 1)
        last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        expected = {(first + timedelta(days=i)).isoformat() for i in range(last.day)}
        if set(item['days']) != expected or not allowed_url(item['source']):
            raise ValueError('Datas ou fonte inválidas na cópia pública.')
        checked = datetime.fromisoformat(item['checked_at'])
        if checked.tzinfo is None or checked > datetime.now(TIMEZONE) + timedelta(minutes=5):
            raise ValueError('Data de consulta inválida.')
        for draws in item['days'].values():
            if not isinstance(draws, list) or len(draws) > len(NAMES):
                raise ValueError('Modalidades inválidas.')
            seen = set()
            for draw in draws:
                if (set(draw) != {'lottery', 'name', 'contest'} or draw['lottery'] not in NAMES
                        or draw['lottery'] in seen or draw['name'] != NAMES[draw['lottery']]
                        or type(draw['contest']) is not int or draw['contest'] < 1):
                    raise ValueError('Concurso inválido na cópia pública.')
                seen.add(draw['lottery'])
        if (year, month) in result:
            raise ValueError('Mês duplicado.')
        age = max(0, (datetime.now(TIMEZONE) - checked).total_seconds())
        result[(year, month)] = {**item, 'checked_monotonic': time.monotonic() - age, 'ttl': SNAPSHOT_TTL}
    return result


def update_snapshot():
    today = datetime.now(TIMEZONE).date()
    following = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    records = []
    for day in (today, following):
        cached = load_month(day.year, day.month)
        if cached:
            records.append({'year': day.year, 'month': day.month,
                            **{key: cached[key] for key in ('days', 'source', 'checked_at')}})
        elif day == today:
            raise RuntimeError('Não foi possível confirmar o cronograma do mês atual; a cópia anterior foi preservada.')
    payload = {'schema': 1, 'months': records}
    try:
        old = read_snapshot()
        same = len(old) == len(records) and all(
            (item['year'], item['month']) in old
            and old[item['year'], item['month']]['days'] == item['days']
            and old[item['year'], item['month']]['source'] == item['source']
            and (datetime.now(TIMEZONE) - datetime.fromisoformat(old[item['year'], item['month']]['checked_at'])).total_seconds() < 12 * 3600
            for item in records)
        if same:
            print('Cronograma público já atualizado; nenhuma alteração necessária.')
            return False
    except (OSError, ValueError, TypeError, KeyError):
        pass
    temporary = SNAPSHOT_PATH.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    read_snapshot(temporary)
    temporary.replace(SNAPSHOT_PATH)
    print('Cópia pública do cronograma atualizada.')
    return True


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c)).upper()


def allowed_url(url):
    parsed = urlsplit(url)
    return (parsed.scheme == 'https' and parsed.hostname in {'www.caixa.gov.br', 'loterias.caixa.gov.br'}
            and parsed.port in (None, 443) and not parsed.username and not parsed.password)


class OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise ValueError('Redirecionamento fora da fonte oficial.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class ScheduleLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href', '')
            url = urljoin(SOURCE, href)
            if allowed_url(url) and re.search(r'/Downloads/caixa-loterias/Cronograma_[^/]+\.pdf$', urlsplit(url).path, re.I):
                self.links.append(url)


def download(opener, url, limit):
    if not allowed_url(url):
        raise ValueError('Fonte não permitida.')
    with opener.open(Request(url, headers={'User-Agent': 'Mozilla/5.0 SnugbX-Calendar/1.0'}), timeout=6) as response:
        body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError('Cronograma acima do limite de tamanho.')
    return body


def parse_schedule(content, year, month):
    if not content.startswith(b'%PDF-'):
        raise ValueError('A fonte não retornou um PDF.')
    reader = PdfReader(BytesIO(content))
    if not 1 <= len(reader.pages) <= 4:
        raise ValueError('Formato de cronograma não reconhecido.')
    days = {}
    seen_dates = []
    headings = ('LOTECA', 'LOTOFACIL', 'FEDERAL', 'LOTOMANIA', 'QUINA', 'DUPLA SENA',
                'TIMEMANIA', 'MEGA-SENA', 'DIA DE SORTE', 'SUPER SETE', '+ MILIONARIA', 'LOCAL DO SORTEIO')
    keys = {'LOTOFACIL': 'lotofacil', 'QUINA': 'quina', 'MEGA-SENA': 'megasena', 'DIA DE SORTE': 'diadesorte'}
    for page in reader.pages:
        lines = page.extract_text(extraction_mode='layout').splitlines()
        header = next((normalize(line) for line in lines if all(h in normalize(line) for h in headings)), None)
        if header is None:
            continue
        centers = [header.index(h) + len(h) / 2 for h in headings]
        bounds = [(centers[i] + centers[i + 1]) / 2 for i in range(len(centers) - 1)]
        for line in lines:
            match = re.match(r'^\s*(\d{2}/\d{2}/\d{4})(?:\(\d+\))?\s+', line)
            if not match:
                continue
            day = datetime.strptime(match[1], '%d/%m/%Y').date()
            seen_dates.append(day)
            if (day.year, day.month) != (year, month):
                continue
            draws = []
            for heading, key in keys.items():
                i = headings.index(heading)
                cell = line[round(bounds[i - 1]):round(bounds[i])].strip()
                contest = re.fullmatch(r'(\d{1,6})(?:\(\d+\))?', cell)
                if contest:
                    draws.append({'lottery': key, 'name': NAMES[key], 'contest': int(contest[1])})
                elif re.search(r'\d', cell):
                    raise ValueError('Colunas do cronograma não reconhecidas.')
            key = day.isoformat()
            if key in days and days[key] != draws:
                raise ValueError('Datas conflitantes na fonte.')
            days[key] = draws
    if len(days) < 20 or any(not any(d['lottery'] == key for draws in days.values() for d in draws) for key in NAMES):
        raise ValueError('Cronograma incompleto ou formato alterado.')
    # The document is a full monthly calendar; omitted dates have no scheduled draws.
    first = date(year, month, 1)
    last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    if min(seen_dates) > first + timedelta(days=2) or max(seen_dates) < last:
        raise ValueError('O documento não cobre o mês inteiro.')
    return {(first + timedelta(days=i)).isoformat(): days.get((first + timedelta(days=i)).isoformat(), [])
            for i in range(last.day)}


def load_month(year, month):
    key = (year, month)
    now = time.monotonic()
    with _lock:
        if now < _next_attempt.get(key, 0):
            return _cache.get(key)
        # Failed requests are retried after five minutes, not once per visitor.
        _next_attempt[key] = now + 300
        try:
            opener = build_opener(OfficialRedirects(), HTTPCookieProcessor(CookieJar()))
            parser = ScheduleLinks()
            parser.feed(download(opener, SOURCE, 2_000_000).decode('utf-8'))
            pattern = rf'Cronograma_{month:02d}_[^/]*{year}[^/]*\.pdf$'
            url = next(url for url in parser.links if re.search(pattern, urlsplit(url).path, re.I))
            days = parse_schedule(download(opener, url, 3_000_000), year, month)
            _cache[key] = {'days': days, 'source': url, 'checked_at': datetime.now(TIMEZONE).isoformat(),
                           'checked_monotonic': now}
            _next_attempt[key] = now + 3600
            # Keep memory bounded across long-running deployments.
            for old in list(_cache):
                if abs(old[0] * 12 + old[1] - year * 12 - month) > 2:
                    _cache.pop(old, None)
                    _next_attempt.pop(old, None)
        except Exception as error:
            # Never invent a schedule or make the whole application fail when CAIXA is unavailable.
            logging.warning('Cronograma CAIXA indisponível (%s).', type(error).__name__)
        return _cache.get(key)


def cached_month(year, month):
    key = (year, month)
    if key not in _cache:
        try:
            bundled = read_snapshot().get(key)
            if bundled:
                _cache[key] = bundled
                remaining = bundled['ttl'] - (time.monotonic() - bundled['checked_monotonic'])
                if remaining > 0:
                    _next_attempt[key] = time.monotonic() + min(3600, remaining)
        except (OSError, ValueError, TypeError, KeyError):
            pass
    with _jobs_lock:
        if key not in _refreshing and time.monotonic() >= _next_attempt.get(key, 0):
            _refreshing.add(key)
            _refresh_started[key] = time.monotonic()

            def refresh():
                try:
                    load_month(year, month)
                finally:
                    with _jobs_lock:
                        _refreshing.discard(key)
                        _refresh_started.pop(key, None)

            threading.Thread(target=refresh, daemon=True, name='caixa-calendar').start()
    return _cache.get(key)


def daily_tips(today, day):
    choices = [
        ('Seu limite vem primeiro', 'Defina um valor de lazer antes de jogar. Não use dinheiro de contas nem aumente apostas para recuperar perdas.'),
        ('Histórico não é previsão', 'Uma estratégia aparecer mais no passado não garante que ela será a próxima. Cada novo sorteio é independente.'),
        ('Jogos diferentes, sem repetição', 'Confira se você não repetiu a mesma combinação. Repetir um jogo no mesmo concurso não amplia a cobertura de combinações.'),
        ('Sua superstição, com consciência', 'Pares, ímpares e números da sorte ajudam a escolher um estilo. Nenhum desses filtros garante prêmio.'),
        ('Compare antes de escolher', 'Na consulta Premium, compare seus jogos e veja o histórico de acertos. Use o resumo para conhecer o jogo, não para prever o futuro.'),
        ('Proteja sua conta', 'Use uma senha exclusiva e nunca compartilhe códigos de acesso. Apostas e pagamentos só devem ser feitos em canais oficiais.'),
        ('Dê uma pausa', 'Se jogar deixou de ser diversão, pare. Não existe obrigação de apostar em todos os concursos.'),
    ]
    title, text = choices[today.toordinal() % len(choices)]
    if not day['confirmed']:
        schedule = 'Não foi possível confirmar a agenda de hoje. Consulte o cronograma oficial antes de apostar.'
    elif day['draws']:
        schedule = 'Na agenda de hoje: ' + ', '.join(draw['name'] for draw in day['draws']) + '. Confira os prazos de aposta nos canais oficiais.'
    else:
        schedule = 'Nenhum sorteio das quatro modalidades do app está previsto para hoje no cronograma consultado.'
    return [{'title': title, 'text': text}, {'title': 'De olho na agenda', 'text': schedule}]


def get_calendar(today=None, background=False):
    today = today or datetime.now(TIMEZONE).date()
    monday = today - timedelta(days=today.weekday())
    dates = [monday + timedelta(days=i) for i in range(7)]
    loader = cached_month if background else load_month
    months = {key: loader(*key) for key in sorted({(day.year, day.month) for day in dates})}
    days = []
    for day in dates:
        cached = months[(day.year, day.month)]
        fresh = bool(cached and time.monotonic() - cached['checked_monotonic'] < cached.get('ttl', 3600))
        days.append({'date': day.isoformat(), 'label': LABELS[day.weekday()], 'today': day == today,
                     'confirmed': fresh, 'available': bool(cached),
                     'draws': cached['days'].get(day.isoformat(), []) if cached else []})
    checked = [value['checked_at'] for value in months.values() if value]
    status = 'current' if all(day['confirmed'] for day in days) else 'unavailable' if not checked else 'stale'
    if not checked and background and any(key in _refreshing and time.monotonic() - _refresh_started.get(key, 0) < 30 for key in months):
        status = 'loading'
    return {'today': today.isoformat(), 'timezone': 'America/Sao_Paulo', 'days': days,
            'status': status,
            'checked_at': min(checked) if checked else None,
            'source': SOURCE, 'tips': daily_tips(today, days[today.weekday()])}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Atualiza somente a cópia pública do calendário oficial.')
    parser.add_argument('--update-snapshot', action='store_true', required=True)
    parser.parse_args()
    try:
        update_snapshot()
    except Exception as error:
        logging.error('Falha na atualização do cronograma público (%s).', type(error).__name__)
        raise SystemExit(1)
