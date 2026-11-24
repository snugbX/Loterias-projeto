"""Descriptive parity transitions with a chronological, frozen holdout test."""

from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from math import comb, sqrt
import os

import game_analysis
import gerador_loterias as lottery


MIN_SAMPLE = 30
TRAIN_FRACTION = 0.7
PRIOR_WEIGHT = 20
MONTH_NAMES = ('Janeiro Fevereiro Março Abril Maio Junho Julho Agosto Setembro Outubro Novembro Dezembro').split()


def walk_forward_validation(draws, probabilities):
    folds = []
    for fraction in (0.4, 0.6, 0.8):
        start = max(1, int(len(draws) * fraction))
        end = min(len(draws), int(len(draws) * (fraction + 0.2) + 1e-8))
        if end <= start:
            continue
        training = defaultdict(Counter)
        for previous, current in zip(draws[:start], draws[1:start]):
            if current[0] == previous[0] + 1:
                training[previous[2]][current[2]] += 1
        loss = baseline_loss = hits = baseline_hits = tested = 0
        baseline_choice = max(probabilities, key=probabilities.get)
        for index in range(start, end):
            previous, current = draws[index - 1], draws[index]
            if current[0] != previous[0] + 1:
                continue
            observed = training[previous[2]]
            sample = sum(observed.values())
            estimated = {key: (observed[key] + PRIOR_WEIGHT * p) / (sample + PRIOR_WEIGHT)
                         for key, p in probabilities.items()}
            tested += 1
            hits += int(max(estimated, key=estimated.get) == current[2])
            baseline_hits += int(baseline_choice == current[2])
            loss += sum((p - int(key == current[2])) ** 2 for key, p in estimated.items())
            baseline_loss += sum((p - int(key == current[2])) ** 2 for key, p in probabilities.items())
        folds.append({'train_last_contest': draws[start - 1][0], 'test_first_contest': draws[start][0],
                      'test_last_contest': draws[end - 1][0], 'sample': tested,
                      'model_accuracy': hits / tested if tested else None,
                      'baseline_accuracy': baseline_hits / tested if tested else None,
                      'model_brier': loss / tested if tested else None,
                      'baseline_brier': baseline_loss / tested if tested else None})
    total = sum(fold['sample'] for fold in folds)
    return {'folds': folds, 'sample': total, 'enough_data': len(folds) == 3 and all(f['sample'] >= MIN_SAMPLE for f in folds),
            'model_brier': sum(f['model_brier'] * f['sample'] for f in folds if f['sample']) / total if total else None,
            'baseline_brier': sum(f['baseline_brier'] * f['sample'] for f in folds if f['sample']) / total if total else None,
            'note': 'Três janelas posteriores de 20%, com treino expansivo inicial de 40%, 60% e 80%. Modelo congelado dentro de cada janela; os testes não se sobrepõem. Resultado descritivo, sem vantagem comprovada.'}


def build_month_radar(raw):
    chronological = list(reversed(raw))
    draws = [(contest, date, month) for contest, date, _, month in chronological
             if type(month) is int and 1 <= month <= 12]
    probabilities = {month: 1 / 12 for month in range(1, 13)}
    frequencies = Counter(row[2] for row in draws)
    transitions = defaultdict(Counter)
    for previous, current in zip(draws, draws[1:]):
        if current[0] == previous[0] + 1:
            transitions[previous[2]][current[2]] += 1
    groups = {}
    for month in probabilities:
        observed = transitions[month]
        sample = sum(observed.values())
        groups[month] = {
            'month': month, 'label': MONTH_NAMES[month - 1], 'sample': sample, 'small_sample': sample < MIN_SAMPLE,
            'profiles': [{'month': target, 'label': MONTH_NAMES[target - 1], 'matches': observed[target],
                          'conditional_probability': observed[target] / sample if sample else None,
                          'historical_probability': frequencies[target] / len(draws) if draws else None,
                          'theoretical_probability': 1 / 12,
                          'difference_pp': (observed[target] / sample - 1 / 12) * 100 if sample else None,
                          'interval': wilson_interval(observed[target], sample)} for target in probabilities],
        }
    latest = chronological[-1]
    month = latest[3] if type(latest[3]) is int and latest[3] in probabilities else None
    return {'latest': {'contest': latest[0], 'date': latest[1], 'month': month,
                       'label': MONTH_NAMES[month - 1] if month else 'Mês indisponível'},
            'coverage': {'total_draws': len(draws), 'missing_months': len(raw) - len(draws),
                         'valid_transitions': sum(sum(values.values()) for values in transitions.values())},
            'profiles': [{'month': key, 'label': MONTH_NAMES[key - 1]} for key in probabilities],
            'groups': groups, 'validation': validate_chronologically(draws, probabilities),
            'disclaimer': 'Frequências e transições dos meses são descritivas. Cada mês tem chance matemática de 1 em 12; o mês anterior não altera essa chance em sorteios independentes.'}


def parity_probabilities(count, maximum):
    evens = maximum // 2
    odds = maximum - evens
    return {
        even: comb(evens, even) * comb(odds, count - even) / comb(maximum, count)
        for even in range(max(0, count - odds), min(count, evens) + 1)
    }


def wilson_interval(successes, total):
    if total == 0:
        return None
    z = 1.959963984540054
    proportion = successes / total
    divisor = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / divisor
    margin = z * sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / divisor
    return [max(0, center - margin), min(1, center + margin)]


def profile_label(even, count):
    odd = count - even
    return f"{even} {'par' if even == 1 else 'pares'} e {odd} {'ímpar' if odd == 1 else 'ímpares'}"


def validate_chronologically(draws, probabilities):
    split = int(len(draws) * TRAIN_FRACTION)
    training = defaultdict(Counter)
    # No holdout outcomes enter training, including the boundary transition.
    for index in range(1, split):
        previous, current = draws[index - 1], draws[index]
        if current[0] == previous[0] + 1:
            training[previous[2]][current[2]] += 1
    model_loss = baseline_loss = 0.0
    model_hits = baseline_hits = tested = 0
    baseline_choice = max(probabilities, key=probabilities.get)
    for index in range(max(split, 1), len(draws)):
        previous, current = draws[index - 1], draws[index]
        if current[0] != previous[0] + 1:
            continue
        observed = training[previous[2]]
        sample = sum(observed.values())
        estimated = {key: (observed[key] + PRIOR_WEIGHT * value) / (sample + PRIOR_WEIGHT)
                     for key, value in probabilities.items()}
        choice = max(estimated, key=estimated.get)
        tested += 1
        model_hits += int(choice == current[2])
        baseline_hits += int(baseline_choice == current[2])
        model_loss += sum((value - int(key == current[2])) ** 2 for key, value in estimated.items())
        baseline_loss += sum((value - int(key == current[2])) ** 2 for key, value in probabilities.items())
    return {
        "train_draws": split, "test_transitions": tested,
        "walk_forward": walk_forward_validation(draws, probabilities),
        "train_last_contest": draws[split - 1][0] if split else None,
        "test_first_contest": draws[split][0] if split < len(draws) else None,
        "model_accuracy": model_hits / tested if tested else None,
        "baseline_accuracy": baseline_hits / tested if tested else None,
        "model_brier": model_loss / tested if tested else None,
        "baseline_brier": baseline_loss / tested if tested else None,
        "enough_data": tested >= MIN_SAMPLE,
        "note": ("Treino nos primeiros 70% dos concursos e teste nos 30% seguintes. "
                 "Modelo de transições congelado, suavizado com peso 20 da referência matemática. "
                 "Brier menor indica menor erro de probabilidade neste teste, não vantagem comprovada. "
                 "Um único recorte não demonstra capacidade de previsão."),
    }


@lru_cache(maxsize=4)
def _build_radar(lottery_type, path, modified_ns, size, skiprows):
    raw, skipped = game_analysis._read_draws(lottery_type, path, modified_ns, size, skiprows)
    return build_radar_from_draws(lottery_type, raw, skipped, modified_ns)


def build_radar_from_draws(lottery_type, raw, skipped, modified_ns):
    """Build from a supplied snapshot so comparisons cannot mix CSV revisions."""
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    count = config["NUM_BALLS_TO_DRAW"]
    draws = [(contest, date, sum(number % 2 == 0 for number in numbers))
             for contest, date, numbers, _ in reversed(raw)]
    probabilities = parity_probabilities(count, config["MAX_NUMBER"])
    frequencies = Counter(draw[2] for draw in draws)
    transitions = defaultdict(Counter)
    for previous, current in zip(draws, draws[1:]):
        if current[0] == previous[0] + 1:
            transitions[previous[2]][current[2]] += 1
    groups = {}
    for source in probabilities:
        observed = transitions[source]
        sample = sum(observed.values())
        groups[source] = {
            "even": source, "label": profile_label(source, count), "sample": sample,
            "small_sample": sample < MIN_SAMPLE,
            "profiles": [{
                "even": target, "odd": count - target, "label": profile_label(target, count),
                "matches": observed[target], "sample": sample,
                "conditional_probability": observed[target] / sample if sample else None,
                "historical_probability": frequencies[target] / len(draws),
                "theoretical_probability": baseline,
                "difference_pp": (observed[target] / sample - baseline) * 100 if sample else None,
                "interval": wilson_interval(observed[target], sample),
            } for target, baseline in probabilities.items()],
        }
    latest = draws[-1]
    return {
        "lottery_type": lottery_type, "lottery_name": lottery.LOTTERY_DISPLAY_NAMES[lottery_type],
        "latest": {"contest": latest[0], "date": latest[1], "even": latest[2], "label": profile_label(latest[2], count)},
        "coverage": {"total_draws": len(draws), "first_contest": draws[0][0], "last_contest": latest[0],
                     "valid_transitions": sum(sum(group.values()) for group in transitions.values()),
                     "skipped_rows": skipped, "excluded_gaps": max(0, len(draws) - 1 - sum(sum(group.values()) for group in transitions.values()))},
        "profiles": [{"even": key, "label": profile_label(key, count)} for key in probabilities],
        "groups": groups, "validation": validate_chronologically(draws, probabilities),
        "months": build_month_radar(raw) if lottery_type == 'diadesorte' else None,
        "data_updated_at": datetime.fromtimestamp(modified_ns / 1e9, timezone.utc).isoformat(),
        "disclaimer": ("Análise exploratória de pares e ímpares, não previsão de prêmios. "
                       "Em sorteios independentes, o concurso anterior não altera a probabilidade matemática. "
                       "Frequências condicionais e intervalos de Wilson de 95% são descritivos e aproximados; "
                       "não corrigem a busca por múltiplos padrões nem provam dependência entre sorteios. "
                       "Cada combinação simples mantém a mesma chance. 18+."),
    }


def get_radar(lottery_type, previous_even=None, previous_month=None):
    if lottery_type not in lottery.LOTTERY_CONFIGS:
        raise ValueError("Loteria inválida.")
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    try:
        stat = os.stat(config["FILE_PATH"])
    except OSError as error:
        raise game_analysis.HistoryUnavailable("Base do radar indisponível. Solicite a atualização dos dados.") from error
    snapshot = _build_radar(lottery_type, config["FILE_PATH"], stat.st_mtime_ns, stat.st_size, config["SKIP_ROWS"])
    source = snapshot["latest"]["even"] if previous_even is None else previous_even
    if type(source) is not int or source not in snapshot["groups"]:
        raise ValueError("Perfil de pares e ímpares inválido para esta loteria.")
    result = {key: value for key, value in snapshot.items() if key not in {'groups', 'months'}} | {"selected": snapshot["groups"][source]}
    if previous_month is not None and (lottery_type != 'diadesorte' or type(previous_month) is not int or not 1 <= previous_month <= 12):
        raise ValueError('Mês de referência inválido para esta loteria.')
    if snapshot['months'] is not None:
        months = snapshot['months']
        selected_month = months['latest']['month'] if previous_month is None else previous_month
        result['months'] = {key: value for key, value in months.items() if key != 'groups'} | {
            'selected': months['groups'].get(selected_month)}
    return result
