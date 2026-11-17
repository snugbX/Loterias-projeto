"""Bounded, private batch analysis; every game uses the same history snapshot."""

from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations

import game_analysis
import pattern_radar


MAX_GAMES = 10


def analyze_games(lottery_type, payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('games'), list):
        raise ValueError('Informe uma lista de jogos para consultar.')
    games = payload['games']
    if not 1 <= len(games) <= MAX_GAMES:
        raise ValueError(f'Consulte de 1 a {MAX_GAMES} jogos por vez.')
    validated = []
    for index, game in enumerate(games, 1):
        try:
            validated.append(game_analysis.validate_game(lottery_type, game))
        except ValueError as error:
            raise ValueError(f'Jogo {index}: {error}') from error
    draws, skipped, stat = game_analysis.load_validated_history(lottery_type)
    radar = pattern_radar.build_radar_from_draws(lottery_type, draws, skipped, stat.st_mtime_ns)
    source = radar['groups'][radar['latest']['even']]
    targets = {profile['even']: profile for profile in source['profiles']}
    all_prize_contests = set()
    cached = {}
    results = []
    duplicate_groups = defaultdict(list)
    number_combinations = set()
    for index, (numbers, month) in enumerate(validated, 1):
        key = (tuple(numbers), month)
        duplicate_groups[key].append(index)
        number_combinations.add(tuple(numbers))
        if key not in cached:
            cached[key] = game_analysis.analyze_validated_game(lottery_type, numbers, month, draws, skipped)
        data, contests = cached[key]
        all_prize_contests.update(contests)
        target = targets[data['profile']['even']]
        results.append({**data, 'game_id': index, 'radar_context': {
            'source_label': source['label'], 'target_label': target['label'],
            'sample': source['sample'], 'matches': target['matches'],
            'conditional_probability': target['conditional_probability'],
            'theoretical_probability': target['theoretical_probability'],
            'interval': target['interval'], 'small_sample': source['small_sample'],
        }})
    pairs = []
    for left, right in combinations(results, 2):
        common = sorted(set(left['numbers']).intersection(right['numbers']))
        same_numbers = left['numbers'] == right['numbers']
        same_month = left['month'] == right['month'] if lottery_type == 'diadesorte' else None
        pairs.append({
            'left': left['game_id'], 'right': right['game_id'], 'common_numbers': common,
            'overlap_percentage': len(common) / len(left['numbers']) * 100,
            'same_numbers': same_numbers, 'same_month': same_month,
            'duplicate': same_numbers and (same_month is not False),
        })
    duplicates = [ids for ids in duplicate_groups.values() if len(ids) > 1]
    unique_numbers = len(number_combinations)
    total_combinations = results[0]['probabilities']['jackpot_one_in']
    most_historical = max(data['history']['prize_draws'] for data in results)
    unique_months = len({month for _, month in validated}) if lottery_type == 'diadesorte' else None
    return {
        'analyses': results, 'pairs': pairs,
        'coverage': results[0]['coverage'],
        'data_updated_at': datetime.fromtimestamp(stat.st_mtime_ns / 1e9, timezone.utc).isoformat(),
        'radar': {'latest': radar['latest'], 'validation': radar['validation'], 'disclaimer': radar['disclaimer']},
        'summary': {
            'submitted': len(games), 'unique_games': len(duplicate_groups),
            'duplicate_groups': duplicates, 'unique_number_combinations': unique_numbers,
            'distinct_numbers': len({number for numbers, _ in validated for number in numbers}),
            'historical_prize_draws': len(all_prize_contests),
            'historical_percentage': len(all_prize_contests) / len(draws) * 100,
            'most_historical_prizes': most_historical,
            'historical_leaders': [data['game_id'] for data in results if data['history']['prize_draws'] == most_historical],
            'numeric_jackpot_probability': unique_numbers / total_combinations,
            'numeric_jackpot_one_in': total_combinations / unique_numbers,
            'unique_months': unique_months,
            'month_coverage_probability': unique_months / 12 if unique_months is not None else None,
        },
        'comparison_note': ('Comparação descritiva de apostas simples na mesma loteria e no mesmo concurso. '
                            'O histórico do conjunto conta cada concurso uma única vez. '
                            'Jogos repetidos não ampliam a cobertura de resultados. '
                            'Não somamos probabilidades das faixas menores: os eventos podem se sobrepor. '
                            'Mais acertos no passado ou maior frequência do perfil não tornam uma combinação mais provável no futuro.'),
    }
