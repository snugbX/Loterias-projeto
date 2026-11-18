"""Minimal parity edits ranked by descriptive, support-aware co-occurrence."""

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from math import log

import gerador_loterias as lottery
import pattern_radar

MIN_NUMBER_SUPPORT = 30
MIN_PAIR_SUPPORT = 3
PAIR_PRIOR = 5


@dataclass(frozen=True)
class SynergyIndex:
    total: int
    count: int
    maximum: int
    singles: tuple
    pairs: tuple


@lru_cache(maxsize=4)
def build_synergy(lottery_type, draws):
    """Cache only public validated draws; changed snapshots invalidate the index."""
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    maximum = config['MAX_NUMBER']
    singles = Counter()
    pairs = Counter()
    for _, _, numbers, _ in draws:
        singles.update(numbers)
        pairs.update(combinations(sorted(numbers), 2))
    matrix = tuple(tuple(pairs[min(a, b), max(a, b)] if a != b else 0
                         for b in range(maximum + 1)) for a in range(maximum + 1))
    return SynergyIndex(len(draws), config['NUM_BALLS_TO_DRAW'], maximum,
                        tuple(singles[n] for n in range(maximum + 1)), matrix)


def pair_affinity(index, number, anchor):
    observed = index.pairs[number][anchor]
    supported = (index.total > 0 and index.singles[number] >= MIN_NUMBER_SUPPORT
                 and index.singles[anchor] >= MIN_NUMBER_SUPPORT and observed >= MIN_PAIR_SUPPORT)
    # Sampling k distinct numbers induces negative association even in a fair draw.
    # This finite-population correction makes the uniform fair-draw reference 1.
    correction = (index.count - 1) * index.maximum / (index.count * (index.maximum - 1))
    expected = index.singles[number] * index.singles[anchor] / index.total * correction if index.total else 0
    lift = (observed + PAIR_PRIOR) / (expected + PAIR_PRIOR) if supported else 1.0
    return {'number': anchor, 'co_draws': observed, 'expected_co_draws': expected,
            'supported': supported, 'adjusted_lift': lift, 'positive': supported and lift > 1.0}


def synergy_evidence(index, number, anchors):
    pairs = [pair_affinity(index, number, anchor) for anchor in sorted(anchors)]
    positive = [pair['number'] for pair in pairs if pair['positive']]
    return {'number': number, 'anchors': sorted(anchors), 'positive_numbers': positive,
            'positive_count': len(positive), 'anchor_count': len(anchors),
            'majority': len(positive) > len(anchors) / 2 if anchors else False,
            'supported_pairs': sum(pair['supported'] for pair in pairs),
            'mean_log_lift': sum(log(pair['adjusted_lift']) for pair in pairs) / len(pairs) if pairs else 0,
            'pairs': pairs}


def suggest_alternative(lottery_type, numbers, month, radar, synergy=None):
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    source = radar['groups'][radar['latest']['even']]
    current_even = sum(number % 2 == 0 for number in numbers)
    use_transitions = source['sample'] >= pattern_radar.MIN_SAMPLE

    def score(profile):
        baseline = profile['theoretical_probability']
        if not use_transitions:
            return baseline
        return (profile['matches'] + pattern_radar.PRIOR_WEIGHT * baseline) / (source['sample'] + pattern_radar.PRIOR_WEIGHT)

    # A tie preserves more of the submitted game; no individual number is ranked as luckier.
    target = max(source['profiles'], key=lambda profile: (
        score(profile), profile['theoretical_probability'], -abs(profile['even'] - current_even), -profile['even']))
    selected = set(numbers)
    original = frozenset(numbers)
    difference = target['even'] - current_even
    wanted_parity = 0 if difference > 0 else 1
    changes = []
    for _ in range(abs(difference)):
        pairs = [(old, new) for old in selected if old % 2 != wanted_parity
                 for new in range(config['MIN_NUMBER'], config['MAX_NUMBER'] + 1)
                 if new % 2 == wanted_parity and new not in selected]
        if synergy is None:
            break

        def affinity_score(pair):
            old, new = pair
            proposed = (selected - {old}) | {new}
            anchors = original & proposed
            # All newly inserted numbers are checked against the same retained originals.
            evidence = [synergy_evidence(synergy, value, anchors or original) for value in sorted(proposed - original)]
            return (all(item['majority'] for item in evidence),
                    min(item['positive_count'] / item['anchor_count'] for item in evidence),
                    sum(item['mean_log_lift'] for item in evidence) / len(evidence), -new, -old)

        old, new = max(pairs, key=affinity_score)
        selected.remove(old)
        selected.add(new)
        changes.append({'from': old, 'to': new})
    anchors = original & selected
    evidence = [synergy_evidence(synergy, number, anchors or original)
                for number in sorted(selected - original)] if synergy else []
    sufficient = bool(evidence) and all(item['majority'] for item in evidence)
    if difference and not sufficient:
        selected = set(numbers)
        changes = []
        evidence = []
    return {
        'status': 'alternative' if changes else 'insufficient_synergy' if difference else 'already_aligned',
        'numbers': sorted(selected), 'month': month, 'changes': changes,
        'preserved_numbers': sorted(set(numbers) & selected),
        'synergy': {'method': 'adjusted_smoothed_pair_lift', 'total_draws': synergy.total if synergy else 0,
                    'min_number_support': MIN_NUMBER_SUPPORT, 'min_pair_support': MIN_PAIR_SUPPORT,
                    'prior': PAIR_PRIOR, 'reference': 'preserved' if anchors else 'submitted',
                    'evidence': evidence},
        'target_even': target['even'], 'target_odd': target['odd'], 'target_label': target['label'],
        'basis': 'smoothed_transitions' if use_transitions else 'theoretical_fallback',
        'source_label': source['label'], 'source_contest': radar['latest']['contest'],
        'source_date': radar['latest']['date'], 'sample': source['sample'],
        'small_sample': not use_transitions, 'matches': target['matches'],
        'conditional_probability': target['conditional_probability'],
        'theoretical_probability': target['theoretical_probability'], 'reference_score': score(target),
        'note': ('Perfil de referência escolhido pelas transições do último perfil, suavizadas pela distribuição matemática. '
                 if use_transitions else
                 'Amostra insuficiente nas transições do último perfil. Usamos o perfil mais provável pela distribuição matemática, não uma previsão do radar. ')
                + 'As trocas preservam o máximo de dezenas e priorizam coocorrências positivas com a maioria das dezenas mantidas. '
                  'Comparamos coocorrências com a referência ajustada às frequências individuais e ao sorteio sem reposição, '
                  'com suavização e suporte mínimo. A busca é incremental, não uma otimização global nem teste de significância. '
                  'Comparamos muitos pares sem correção de múltiplas comparações; associações podem ser coincidências. '
                  'Afinidade histórica não demonstra dependência ou poder de previsão; não indica números mais prováveis. '
                  'A alternativa tem a mesma chance matemática individual do jogo original. Não garante prêmio.',
    }
