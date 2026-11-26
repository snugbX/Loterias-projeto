"""Bounded, private batch analysis; every game uses the same history snapshot."""

from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations

import game_analysis
import game_alternative
import pattern_radar
import public_reports


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
    synergy = game_alternative.build_synergy(lottery_type, draws)
    audit_report = public_reports.get_report(lottery_type)
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
        alternative = game_alternative.suggest_alternative(lottery_type, numbers, month, radar, synergy)
        checked_pairs = {(min(item['number'], anchor), max(item['number'], anchor))
                         for item in alternative['synergy']['evidence'] for anchor in item['positive_numbers']}
        alternative['synergy']['audit'] = {'status': audit_report['status'], 'examined': len(checked_pairs)}
        if audit_report['status'] == 'current':
            audit = audit_report['report']['audit']
            alternative['synergy']['audit'].update({
                'significant': sum(audit['q_values'][a - 1][b - 1] <= audit['alpha'] for a, b in checked_pairs),
                'stable': sum(audit['stable_positive'][a - 1][b - 1] for a, b in checked_pairs),
                'family_size': audit['family_size']})
        alternative_key = (tuple(alternative['numbers']), month)
        if alternative_key not in cached:
            cached[alternative_key] = game_analysis.analyze_validated_game(
                lottery_type, alternative['numbers'], month, draws, skipped)
        alternative_data = cached[alternative_key][0]
        alternative['history'] = {key: alternative_data['history'][key]
                                  for key in ('prize_draws', 'best_matches', 'percentage')}
        alternative['jackpot_one_in'] = data['probabilities']['jackpot_one_in']
        alternative['duplicates_game_ids'] = [other for other, (values, other_month) in enumerate(validated, 1)
                                             if other != index and (tuple(values), other_month) == alternative_key]
        results.append({**data, 'game_id': index, 'alternative': alternative, 'radar_context': {
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
        same_trevos = left['trevos'] == right['trevos'] if lottery_type == 'maismilionaria' else None
        pairs.append({
            'left': left['game_id'], 'right': right['game_id'], 'common_numbers': common,
            'overlap_percentage': len(common) / len(left['numbers']) * 100,
            'same_numbers': same_numbers, 'same_month': same_month,
            'same_trevos': same_trevos,
            'duplicate': same_numbers and (same_month is not False) and (same_trevos is not False),
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
            'numeric_jackpot_probability': unique_numbers / results[0]['probabilities'].get('numeric_jackpot_one_in', total_combinations),
            'numeric_jackpot_one_in': results[0]['probabilities'].get('numeric_jackpot_one_in', total_combinations) / unique_numbers,
            'complete_jackpot_probability': len(duplicate_groups) / total_combinations if lottery_type == 'maismilionaria' else None,
            'complete_jackpot_one_in': total_combinations / len(duplicate_groups) if lottery_type == 'maismilionaria' else None,
            'unique_months': unique_months,
            'month_coverage_probability': unique_months / 12 if unique_months is not None else None,
        },
        'comparison_note': ('Comparação descritiva de apostas simples na mesma loteria e no mesmo concurso. '
                            'O histórico do conjunto conta cada concurso uma única vez. '
                            'Jogos repetidos não ampliam a cobertura de resultados. '
                            'Não somamos probabilidades das faixas menores: os eventos podem se sobrepor. '
                            'Mais acertos no passado ou maior frequência do perfil não tornam uma combinação mais provável no futuro.'),
    }
