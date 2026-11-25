"""Owner-scoped history organization. Only declared effective games are checked."""

from datetime import date, datetime, timezone
import json
import re

import database
import game_analysis
import gerador_loterias as lottery
import history_database
import history_storage

PAGE_SIZE = 20
MAX_BATCHES = 1000
MAX_GAMES = 50000
STATES = {'all', 'not_effective', 'waiting', 'prize', 'no_prize', 'unavailable', 'invalid', 'incomplete'}


def game_payload(kind, game):
    config = lottery.LOTTERY_CONFIGS[kind]
    count = config['NUM_BALLS_TO_DRAW']
    if not isinstance(game, list) or len(game) != count + (kind == 'diadesorte'):
        raise ValueError('Formato de jogo inválido.')
    months = config.get('EXTRA_CHOICES', {}).get('Mês da Sorte', [])
    month = None
    if months:
        month = next((i + 1 for i, name in enumerate(months) if name.casefold() == str(game[-1]).casefold()), None)
    numbers, month = game_analysis.validate_game(kind, {'numbers': game[:count], 'month': month})
    return numbers, month


def check_game(kind, game, state, draws, latest):
    # This guard intentionally precedes validation and all matching logic.
    if not state.get('effective'):
        return {'status': 'not_effective', 'label': 'Não efetivado'}
    try:
        numbers, month = game_payload(kind, game)
    except ValueError:
        return {'status': 'invalid', 'label': 'Jogo precisa de revisão'}
    contest = state.get('contest')
    if type(contest) is not int or contest < 1:
        return {'status': 'unavailable', 'label': 'Informe o concurso do bilhete'}
    draw = draws.get(contest)
    if not draw:
        pending = latest is not None and contest > latest
        return {'status': 'waiting' if pending else 'unavailable',
                'label': 'Aguardando resultado' if pending else 'Concurso indisponível na base'}
    _, drawn_at, balls, drawn_month = draw
    matched = sorted(set(numbers) & set(balls))
    hits = len(matched)
    month_hit = month == drawn_month if month is not None and drawn_month is not None else None
    prize = hits in game_analysis.PRIZE_MATCHES[kind] or month_hit is True
    incomplete = kind == 'diadesorte' and drawn_month is None
    tiers = ([f'{hits} acertos'] if hits in game_analysis.PRIZE_MATCHES[kind] else [])
    if month_hit is True:
        tiers.append('Mês da Sorte')
    return {'status': 'prize' if prize else 'incomplete' if incomplete else 'no_prize',
            'label': ' + '.join(tiers) if prize else 'Mês indisponível; conferência parcial' if incomplete else 'Sem faixa de prêmio',
            'contest': contest, 'drawn_at': drawn_at, 'hits': hits, 'matched': matched,
            'drawn_numbers': list(balls), 'month_hit': month_hit, 'partial': incomplete,
            'rules_url': game_analysis.RULES_URLS[kind]}


def _records(kind, owner):
    records = history_database.tracked_records(kind, owner)
    truncated = len(records) > MAX_BATCHES
    records = records[:MAX_BATCHES]
    if not database.postgres_enabled():
        known = {row['filename'] for row in records}
        for filename in history_storage.list_history_files(kind, owner):
            if filename in known:
                continue
            if len(records) >= MAX_BATCHES:
                truncated = True
                break
            games = history_storage.read_history_file(filename, owner, include_deleted=True)
            if games is not None:
                records.append({'filename': filename, 'created_at': None, 'games_json': json.dumps(games), 'settings_json': None})
    return records, truncated


def list_games(kind, owner, filters):
    if set(filters) - {'page', 'numbers', 'from', 'to', 'favorite', 'effective', 'status', 'contest', 'sort'}:
        raise ValueError('Filtro desconhecido.')
    page_text = filters.get('page', '1')
    if not re.fullmatch(r'[1-9]\d{0,5}', page_text):
        raise ValueError('Página inválida.')
    page = int(page_text)
    text = filters.get('numbers', '').strip()
    if len(text) > 200 or text and not re.fullmatch(r'\d+(?:[\s,;]+\d+)*', text):
        raise ValueError('Separe as dezenas por espaços ou vírgulas.')
    wanted = set(map(int, re.split(r'[\s,;]+', text))) if text else set()
    if any(not 1 <= n <= lottery.LOTTERY_CONFIGS[kind]['MAX_NUMBER'] for n in wanted):
        raise ValueError('Dezenas fora do intervalo da loteria.')
    bounds = {}
    for name in ('from', 'to'):
        bounds[name] = date.fromisoformat(filters[name]).isoformat() if filters.get(name) else None
    if bounds['from'] and bounds['to'] and bounds['from'] > bounds['to']:
        raise ValueError('O início deve ser anterior ao fim do período.')
    effective = filters.get('effective', 'all')
    status = filters.get('status', 'all')
    favorite = filters.get('favorite', '0')
    order = filters.get('sort', 'recent')
    contest = filters.get('contest', '')
    if effective not in {'all', 'yes', 'no'} or status not in STATES or favorite not in {'0', '1'} or order not in {'recent', 'oldest'}:
        raise ValueError('Filtro inválido.')
    if contest and not re.fullmatch(r'[1-9]\d{0,7}', contest):
        raise ValueError('Concurso inválido.')
    records, truncated = _records(kind, owner)
    try:
        history, skipped, stat = game_analysis.load_validated_history(kind)
        draws = {draw[0]: draw for draw in history}
        latest = max(draws)
        version = str(stat.st_mtime_ns)
    except (game_analysis.HistoryUnavailable, OSError):
        draws, latest, version, skipped = {}, None, None, None
    items = []
    total = effective_count = favorites = checked = prizes = visited = 0
    for row in records:
        filename = row['filename']
        match = history_storage.HISTORY_FILENAME_PATTERN.fullmatch(filename)
        if not match or match.group(1).lower() != kind:
            continue
        day = filename.split('_resultados_')[1][:10]
        settings = json.loads(row['settings_json']) if row['settings_json'] else {}
        for index, game in enumerate(json.loads(row['games_json'])):
            visited += 1
            if visited > MAX_GAMES:
                truncated = True
                break
            state = settings.get(str(index), {})
            if state.get('deleted'):
                continue
            result = check_game(kind, game, state, draws, latest)
            total += 1; effective_count += bool(state.get('effective')); favorites += bool(state.get('favorite'))
            checked += result['status'] in {'prize', 'no_prize', 'incomplete'}
            prizes += result['status'] == 'prize'
            if bounds['from'] and day < bounds['from'] or bounds['to'] and day > bounds['to']:
                continue
            numeric = {n for n in game if type(n) is int}
            if wanted and not wanted <= numeric or favorite == '1' and not state.get('favorite'):
                continue
            if effective != 'all' and bool(state.get('effective')) != (effective == 'yes'):
                continue
            if status != 'all' and status != result['status'] or contest and state.get('contest') != int(contest):
                continue
            items.append({'filename': filename, 'index': index, 'game': game, 'date': day,
                          'created_at': row['created_at'], 'favorite': bool(state.get('favorite')),
                          'effective': bool(state.get('effective')), 'contest': state.get('contest'), 'check': result})
        if visited > MAX_GAMES:
            break
    items.sort(key=lambda item: (item['filename'], -item['index'] if order == 'recent' else item['index']), reverse=order == 'recent')
    matched_count = len(items)
    return {'items': items[(page - 1)*PAGE_SIZE:page*PAGE_SIZE], 'page': page, 'page_size': PAGE_SIZE,
            'matched': matched_count, 'pages': max(1, (matched_count + PAGE_SIZE - 1)//PAGE_SIZE),
            'summary': {'total': total, 'effective': effective_count, 'favorites': favorites, 'checked': checked, 'prizes': prizes},
            'source': {'latest_contest': latest, 'version': version, 'skipped': skipped,
                       'checked_at': datetime.now(timezone.utc).isoformat(), 'rules_url': game_analysis.RULES_URLS[kind]},
            'truncated': truncated}


def update_game(kind, owner, payload):
    if not isinstance(payload, dict) or set(payload) - {'filename', 'index', 'favorite', 'effective', 'contest', 'deleted'}:
        raise ValueError('Atualização inválida.')
    filename, index = payload.get('filename'), payload.get('index')
    if not isinstance(filename, str) or type(index) is not int or index < 0:
        raise ValueError('Jogo inválido.')
    match = history_storage.HISTORY_FILENAME_PATTERN.fullmatch(filename)
    if not match or match.group(1).lower() != kind:
        raise ValueError('Arquivo incompatível com a loteria.')
    changes = {key: payload[key] for key in ('favorite', 'effective', 'contest', 'deleted') if key in payload}
    if not changes or any(type(value) is not bool for key, value in changes.items() if key != 'contest'):
        raise ValueError('Informe opções válidas para o jogo.')
    if changes.get('deleted') is False:
        raise ValueError('A exclusão não pode ser desfeita por esta rota.')
    if 'contest' in changes and changes['contest'] is not None and (type(changes['contest']) is not int or not 1 <= changes['contest'] <= 99999999):
        raise ValueError('Concurso inválido.')
    if changes.get('effective') is True and ('contest' not in changes or changes['contest'] is None):
        raise ValueError('Informe o concurso do bilhete ao marcar como efetivado.')
    if 'contest' in changes and 'effective' not in changes:
        raise ValueError('Confirme também se o jogo foi efetivado.')
    games = history_storage.read_history_file(filename, owner, include_deleted=True)
    if games is None or index >= len(games):
        return False
    if changes.get('effective'):
        game_payload(kind, games[index])
    if not database.postgres_enabled() and history_database.read_history_file(filename, owner) is None:
        history_database.save_history_record(filename, kind, games, owner_key=owner)
    return history_database.update_game_settings(filename, owner, index, changes)
