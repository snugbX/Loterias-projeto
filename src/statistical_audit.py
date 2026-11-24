"""Offline fair-draw audit. No inference here claims future winning advantage."""

from itertools import combinations
from math import ceil, comb
import numpy as np
from scipy.sparse import csr_matrix
from scipy.stats import binom, binomtest, false_discovery_control

import game_alternative
import gerador_loterias as lottery
import pattern_radar


def strategy_reference(mode, count, maximum):
    denominator = comb(maximum, count)
    if mode == 'balanced_parity':
        return sum(p for even, p in pattern_radar.parity_probabilities(count, maximum).items() if abs(2 * even - count) <= 1)
    pools = {'even_only': maximum // 2, 'odd_only': maximum - maximum // 2,
             'lucky_dates': min(31, maximum), 'high_numbers': maximum - int((maximum + 1) / 2)}
    if mode in pools:
        return comb(pools[mode], count) / denominator
    buckets = min(5, count); width = ceil(maximum / buckets)
    sizes = [min(width, maximum - i * width) for i in range(buckets)]
    base, remainder = divmod(count, buckets)
    ways = 0
    for larger in combinations(range(buckets), remainder):
        product = 1
        for i, size in enumerate(sizes):
            take = base + int(i in larger)
            product *= comb(size, take) if take <= size else 0
        ways += product
    return ways / denominator


def strategy_counts(incidence, modes, count, maximum):
    evens = incidence[:, 1::2].sum(axis=1)
    result = {}
    for mode in modes:
        if mode == 'balanced_parity': matched = np.abs(2 * evens - count) <= 1
        elif mode == 'even_only': matched = evens == count
        elif mode == 'odd_only': matched = evens == 0
        elif mode == 'lucky_dates': matched = incidence[:, 31:].sum(axis=1) == 0
        elif mode == 'high_numbers': matched = incidence[:, :int((maximum + 1) / 2)].sum(axis=1) == 0
        else:
            width = ceil(maximum / min(5, count))
            buckets = np.column_stack([incidence[:, start:start + width].sum(axis=1) for start in range(0, maximum, width)])
            matched = (buckets.min(axis=1) > 0) & (buckets.max(axis=1) - buckets.min(axis=1) <= 1)
        result[mode] = int(np.count_nonzero(matched))
    return result


def pair_counts(numbers, maximum):
    rows = np.repeat(np.arange(len(numbers)), len(numbers[0]))
    columns = np.asarray(numbers, dtype=int).ravel() - 1
    matrix = csr_matrix((np.ones(len(columns), dtype=np.int64), (rows, columns)), shape=(len(numbers), maximum))
    return (matrix.T @ matrix).toarray()


def audit_draws(lottery_type, draws, resamples=199, seed=1729):
    if type(resamples) is not int or not 19 <= resamples <= 1999:
        raise ValueError('Use de 19 a 1999 simulações.')
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    maximum, count, total = config['MAX_NUMBER'], config['NUM_BALLS_TO_DRAW'], len(draws)
    if not total:
        raise ValueError('Não há concursos para auditar.')
    pairs = list(combinations(range(maximum), 2))
    a, b = np.array(pairs).T
    observed = pair_counts([row[2] for row in draws], maximum)[a, b]
    probability = count * (count - 1) / (maximum * (maximum - 1))
    pvalues = binom.sf(observed - 1, total, probability)
    adjusted = false_discovery_control(pvalues, method='by')
    q_matrix = np.ones((maximum, maximum))
    q_matrix[a, b] = adjusted
    q_matrix[b, a] = adjusted
    expected = total * probability
    deviation = np.sqrt(total * probability * (1 - probability))
    statistic = float(np.max((observed - expected) / deviation))
    rng = np.random.default_rng(seed)
    extreme = 0
    modes = [mode for mode in ('balanced_parity', 'even_only', 'odd_only', 'spread', 'lucky_dates', 'high_numbers')
             if lottery.is_generation_mode_available_for_lottery(mode, lottery_type)]
    incidence = np.zeros((total, maximum), dtype=np.int64)
    incidence[np.repeat(np.arange(total), count), np.array([row[2] for row in draws]).ravel() - 1] = 1
    observed_strategies = strategy_counts(incidence, modes, count, maximum)
    simulated_counts = {mode: [] for mode in modes}
    # Each row is one independent k-subset. Sampling globally without replacement is wrong.
    for _ in range(resamples):
        incidence = rng.multivariate_hypergeometric(np.ones(maximum, dtype=int), count, size=total)
        matrix = csr_matrix(incidence)
        simulated = (matrix.T @ matrix).toarray()[a, b]
        extreme += int(float(np.max((simulated - expected) / deviation)) >= statistic)
        for mode, value in strategy_counts(incidence, modes, count, maximum).items():
            simulated_counts[mode].append(value)
    stable = np.zeros((maximum, maximum), dtype=bool)
    if total >= 60:
        first = game_alternative.build_synergy(lottery_type, tuple(draws[:total // 2]))
        second = game_alternative.build_synergy(lottery_type, tuple(draws[total // 2:]))
        for left, right in pairs:
            positive = (game_alternative.pair_affinity(first, left + 1, right + 1)['positive']
                        and game_alternative.pair_affinity(second, left + 1, right + 1)['positive'])
            stable[left, right] = stable[right, left] = positive
    strategy_p = [binomtest(observed_strategies[mode], total, strategy_reference(mode, count, maximum)).pvalue for mode in modes]
    strategy_q = false_discovery_control(strategy_p, method='by')
    strategies = [{'mode': mode, 'label': lottery.GENERATION_MODES[mode], 'observed': observed_strategies[mode], 'total': total,
                   'reference_probability': strategy_reference(mode, count, maximum),
                   'simulation_interval': np.quantile(simulated_counts[mode], [0.025, 0.975]).tolist(),
                   'p_value': strategy_p[i], 'q_value': float(strategy_q[i])} for i, mode in enumerate(modes)]
    return {'method': 'binomial_uniform_pair_excess_BY', 'family_size': len(pairs), 'alpha': 0.05,
            'strategies': strategies,
            'significant_pairs': int(np.sum(adjusted <= 0.05)), 'q_values': q_matrix.tolist(),
            'stable_positive': stable.tolist(), 'resamples': resamples, 'seed': seed,
            'global_statistic': statistic, 'global_p_value': (extreme + 1) / (resamples + 1),
            'minimum_p_resolution': 1 / (resamples + 1),
            'note': 'Teste unilateral de excesso de coocorrências contra sorteios uniformes independentes, com correção Benjamini–Yekutieli em todos os pares da modalidade. Não testa associação condicionada às frequências individuais e não prova previsão ou fraude. A simulação compara o maior excesso entre todos os pares; os valores p não são chances de ganhar. A estabilidade entre metades também é apenas descritiva.'}


def draw_intervals(lottery_type, draws):
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    latest = draws[0][0]
    contest_ids = {row[0] for row in draws}
    result = []
    for number in range(1, config['MAX_NUMBER'] + 1):
        last = next((row[0] for row in draws if number in row[2]), None)
        complete = last is not None and all(i in contest_ids for i in range(last, latest + 1))
        gap = latest - last if complete else None
        result.append({'number': number, 'last_seen_contest': last, 'gap': gap,
                       'tail_probability': (1 - config['NUM_BALLS_TO_DRAW'] / config['MAX_NUMBER']) ** gap if gap is not None else None})
    return result
