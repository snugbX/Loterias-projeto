"""Bounded generation with SciPy/HiGHS; constraints are preferences, not forecasts."""

from dataclasses import dataclass
from itertools import combinations
from math import comb
import secrets
import threading
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

import gerador_loterias as lottery

MAX_GAMES = 20
TIME_BUDGET = 8.0
_gate = threading.BoundedSemaphore(1)


class GenerationBusy(Exception):
    pass


@dataclass(frozen=True)
class Rules:
    method: str
    num_games: int
    fixed: tuple
    excluded: tuple
    even_count: int | None
    sum_min: int
    sum_max: int
    max_overlap: int
    month: int | None


def capabilities(lottery_type):
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    count, maximum = config['NUM_BALLS_TO_DRAW'], config['MAX_NUMBER']
    return {'count': count, 'maximum': maximum, 'max_games': MAX_GAMES,
            'min_overlap': max(0, 2 * count - maximum),
            'parities': list(range(max(0, count - (maximum + 1) // 2), min(count, maximum // 2) + 1)),
            'months': config.get('EXTRA_CHOICES', {}).get('Mês da Sorte', [])}


def validate_request(lottery_type, payload):
    if lottery_type not in lottery.LOTTERY_CONFIGS or not isinstance(payload, dict):
        raise ValueError('Informe uma loteria e um objeto de regras válidos.')
    allowed = {'method', 'num_games', 'fixed', 'excluded', 'even_count', 'sum_min', 'sum_max', 'max_overlap', 'month'}
    if set(payload) - allowed:
        raise ValueError('Há campos não reconhecidos nas regras.')
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    count, maximum = config['NUM_BALLS_TO_DRAW'], config['MAX_NUMBER']
    method = payload.get('method', 'constraints')
    if method not in ('uniform', 'constraints'):
        raise ValueError('Modo de geração inválido.')
    quantity = payload.get('num_games', 5)
    if type(quantity) is not int or not 1 <= quantity <= MAX_GAMES:
        raise ValueError(f'Gere de 1 a {MAX_GAMES} jogos por lote.')
    lists = []
    for field in ('fixed', 'excluded'):
        values = payload.get(field, [])
        if (not isinstance(values, list) or len(values) > maximum or any(type(n) is not int or not 1 <= n <= maximum for n in values)
                or len(set(values)) != len(values)):
            raise ValueError('Dezenas fixas/excluídas devem ser inteiras, distintas e estar no intervalo da loteria.')
        lists.append(tuple(sorted(values)))
    fixed, excluded = lists
    if set(fixed) & set(excluded) or len(fixed) > count or maximum - len(excluded) < count:
        raise ValueError('As dezenas fixas e excluídas são incompatíveis com a quantidade do jogo.')
    even = payload.get('even_count')
    overlap = payload.get('max_overlap', count - 1)
    if even is not None and (type(even) is not int or even not in capabilities(lottery_type)['parities']):
        raise ValueError('Quantidade de pares impossível nesta loteria.')
    if type(overlap) is not int or not 0 <= overlap < count:
        raise ValueError(f'O limite de dezenas em comum deve estar entre 0 e {count - 1}.')
    month = payload.get('month')
    if month is not None and (lottery_type != 'diadesorte' or type(month) is not int or not 1 <= month <= 12):
        raise ValueError('Mês da Sorte inválido para esta loteria.')
    free = [n for n in range(1, maximum + 1) if n not in fixed and n not in excluded]
    needed = count - len(fixed)
    if even is None:
        capacity = comb(len(free), needed)
        smallest, largest = sum(sorted(free)[:needed]), sum(sorted(free, reverse=True)[:needed])
    else:
        evens = [n for n in free if n % 2 == 0]; odds = [n for n in free if n % 2]
        e = even - sum(n % 2 == 0 for n in fixed); o = needed - e
        if not 0 <= e <= len(evens) or not 0 <= o <= len(odds):
            raise ValueError('A paridade não cabe nas dezenas fixas e disponíveis.')
        capacity = comb(len(evens), e) * comb(len(odds), o)
        smallest = sum(evens[:e]) + sum(odds[:o])
        largest = sum(sorted(evens, reverse=True)[:e]) + sum(sorted(odds, reverse=True)[:o])
    lower = payload.get('sum_min')
    upper = payload.get('sum_max')
    lower = sum(fixed) + smallest if lower is None else lower
    upper = sum(fixed) + largest if upper is None else upper
    if type(lower) is not int or type(upper) is not int or lower > upper or lower < 0 or upper > count * maximum:
        raise ValueError('Intervalo de soma inválido.')
    if lower > sum(fixed) + largest or upper < sum(fixed) + smallest:
        raise ValueError('A soma não é possível com essas dezenas e paridade.')
    if quantity > capacity:
        raise ValueError('Não existem jogos numéricos distintos suficientes para esse lote.')
    if quantity > 1 and overlap < max(len(fixed), 2 * count - (maximum - len(excluded))):
        raise ValueError('O limite de sobreposição é impossível com esse universo e as dezenas fixas.')
    if method == 'uniform' and (fixed or excluded or even is not None or any(payload.get(key) is not None for key in ('sum_min', 'sum_max', 'max_overlap'))):
        raise ValueError('O modo uniforme não aceita filtros; use Minhas regras para personalizar.')
    return Rules(method, quantity, fixed, excluded, even, lower, upper, overlap, month)


def portfolio_summary(numbers, maximum):
    overlaps = [len(set(a) & set(b)) for a, b in combinations(numbers, 2)]
    unique = len({tuple(row) for row in numbers})
    return {'games': len(numbers), 'unique_combinations': unique,
            'distinct_numbers': len({n for row in numbers for n in row}),
            'max_overlap': max(overlaps) if overlaps else None,
            'mean_overlap': sum(overlaps) / len(overlaps) if overlaps else None,
            'jackpot_probability': unique / comb(maximum, len(numbers[0])),
            'note': 'Diversidade descreve o conjunto e não aumenta a chance de uma combinação individual. A cobertura informada considera todos esses jogos no mesmo concurso. A cobertura numérica do prêmio principal depende da quantidade de combinações distintas, não do estilo.'}


def _satisfies(numbers, rules, count, previous):
    return (len(numbers) == count and len(set(numbers)) == count and set(rules.fixed) <= set(numbers)
            and not set(rules.excluded) & set(numbers) and rules.sum_min <= sum(numbers) <= rules.sum_max
            and (rules.even_count is None or sum(n % 2 == 0 for n in numbers) == rules.even_count)
            and all(len(set(numbers) & set(other)) <= rules.max_overlap for other in previous))


def generate_batch(lottery_type, rules):
    if not _gate.acquire(blocking=False):
        raise GenerationBusy('Há outra geração personalizada em andamento. Tente novamente em instantes.')
    try:
        config = lottery.LOTTERY_CONFIGS[lottery_type]
        count, maximum = config['NUM_BALLS_TO_DRAW'], config['MAX_NUMBER']
        values = np.arange(1, maximum + 1)
        lower = np.zeros(maximum); upper = np.ones(maximum)
        for n in rules.fixed: lower[n - 1] = 1
        for n in rules.excluded: upper[n - 1] = 0
        random = secrets.SystemRandom()
        rng = np.random.default_rng(secrets.randbits(128))
        selected = []
        deadline = time.monotonic() + TIME_BUDGET
        while len(selected) < rules.num_games:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise GenerationBusy('A busca atingiu o limite de tempo; nenhum lote foi salvo. Simplifique as regras.')
            if rules.method == 'uniform':
                numbers = sorted(random.sample(range(1, maximum + 1), count))
                if numbers in selected: continue
            else:
                rows = [np.ones(maximum), values.astype(float)]
                lb = [count, rules.sum_min]; ub = [count, rules.sum_max]
                if rules.even_count is not None:
                    rows.append((values % 2 == 0).astype(float)); lb.append(rules.even_count); ub.append(rules.even_count)
                for previous in selected:
                    rows.append(np.isin(values, previous).astype(float)); lb.append(0); ub.append(rules.max_overlap)
                result = milp(rng.uniform(-1, 1, maximum), integrality=np.ones(maximum), bounds=Bounds(lower, upper),
                              constraints=LinearConstraint(np.array(rows), lb, ub), options={'time_limit': min(0.4, remaining)})
                if result.status == 2:
                    raise ValueError('Não foi possível completar o lote com essas regras e os jogos já escolhidos. Nenhum lote foi salvo; flexibilize a sobreposição ou reduza a quantidade. A busca incremental não prova que todo o problema é impossível.')
                if result.x is None:
                    raise GenerationBusy('A busca não concluiu no tempo disponível. Nenhum lote foi salvo.')
                numbers = values[np.asarray(result.x) >= 0.5].astype(int).tolist()
                if not _satisfies(numbers, rules, count, selected):
                    raise GenerationBusy('A solução não passou na validação independente. Nenhum lote foi salvo.')
            selected.append(numbers)
        games = []
        for numbers in selected:
            game = list(numbers)
            if lottery_type == 'diadesorte':
                month = rules.month or random.randrange(1, 13)
                game.append(config['EXTRA_CHOICES']['Mês da Sorte'][month - 1])
            games.append(game)
        portfolio = portfolio_summary(selected, maximum)
        if lottery_type == 'diadesorte':
            portfolio['unique_months'] = len({game[-1] for game in games})
            portfolio['month_probability'] = portfolio['unique_months'] / 12
        return {'games': games, 'portfolio': portfolio,
                'generation_mode': rules.method,
                'method_note': 'Amostragem uniforme sem reposição de dezenas e sem jogos repetidos.' if rules.method == 'uniform'
                               else 'Seleção por restrições com objetivo aleatório (HiGHS). Não é amostragem uniforme de todas as soluções viáveis nem previsão de sorteio.'}
    finally:
        _gate.release()
