"""Factual draw summaries from validated public results, never betting advice."""

from math import ceil
import gerador_loterias as lottery


def build_digest(lottery_type, draws, skipped):
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    contest, date, numbers, month = draws[0]
    previous = draws[1] if len(draws) > 1 and draws[1][0] == contest - 1 else None
    repeated = sorted(set(numbers) & set(previous[2])) if previous else None
    even = sum(n % 2 == 0 for n in numbers)
    bucket_count = min(5, len(numbers))
    width = ceil(config['MAX_NUMBER'] / bucket_count)
    ranges = [{'from': start, 'to': min(start + width - 1, config['MAX_NUMBER']),
               'count': sum(start <= n <= min(start + width - 1, config['MAX_NUMBER']) for n in numbers)}
              for start in range(1, config['MAX_NUMBER'] + 1, width)]
    month_name = config.get('EXTRA_CHOICES', {}).get('Mês da Sorte', [])[month - 1] if month and lottery_type == 'diadesorte' else None
    missing = max(0, draws[0][0] - draws[-1][0] + 1 - len(draws))
    text = f'{even} pares e {len(numbers) - even} ímpares; soma {sum(numbers)}.'
    text += f' {len(repeated)} dezenas repetidas do concurso anterior.' if repeated is not None else ' Comparação com o concurso anterior indisponível na base.'
    if lottery_type == 'diadesorte':
        text += f' Mês da Sorte: {month_name or "não informado na base"}.'
    return {'lottery_type': lottery_type, 'lottery_name': lottery.LOTTERY_DISPLAY_NAMES[lottery_type],
            'contest': contest, 'date': date, 'numbers': list(numbers), 'even': even,
            'odd': len(numbers) - even, 'sum': sum(numbers), 'repeated_numbers': repeated,
            'consecutive_pairs': sum(b == a + 1 for a, b in zip(numbers, numbers[1:])),
            'ranges': ranges, 'month': month_name, 'trevos': list(month) if lottery_type == 'maismilionaria' else None,
            'coverage': {'total_draws': len(draws), 'missing_contests': missing, 'skipped_rows': skipped},
            'text': text, 'note': 'Resumo factual da base validada, não previsão, avaliação de prêmio ou confirmação de aposta. Consulte os canais oficiais da CAIXA.'}
