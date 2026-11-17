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
        "data_updated_at": datetime.fromtimestamp(modified_ns / 1e9, timezone.utc).isoformat(),
        "disclaimer": ("Análise exploratória de pares e ímpares, não previsão de prêmios. "
                       "Em sorteios independentes, o concurso anterior não altera a probabilidade matemática. "
                       "Frequências condicionais e intervalos de Wilson de 95% são descritivos e aproximados; "
                       "não corrigem a busca por múltiplos padrões nem provam dependência entre sorteios. "
                       "Cada combinação simples mantém a mesma chance. 18+."),
    }


def get_radar(lottery_type, previous_even=None):
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
    return {key: value for key, value in snapshot.items() if key != "groups"} | {"selected": snapshot["groups"][source]}
