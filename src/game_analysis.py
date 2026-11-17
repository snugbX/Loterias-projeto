"""Read-only analysis of simple bets; historical frequency is not a forecast."""

from collections import Counter
from functools import lru_cache
from math import comb
import os

import pandas as pd
import gerador_loterias as lottery


PRIZE_MATCHES = {
    "megasena": (4, 5, 6),
    "quina": (2, 3, 4, 5),
    "lotofacil": (11, 12, 13, 14, 15),
    "diadesorte": (4, 5, 6, 7),
}
RULES_URLS = {
    "megasena": "https://loterias.caixa.gov.br/Paginas/Mega-Sena.aspx",
    "quina": "https://loterias.caixa.gov.br/Paginas/Quina.aspx",
    "lotofacil": "https://loterias.caixa.gov.br/Paginas/Lotofacil.aspx",
    "diadesorte": "https://www.caixa.gov.br/Downloads/loterias-manual-de-produtos/MANUAL_DE_PRODUTOS_v19.pdf",
}


class HistoryUnavailable(Exception):
    pass


def validate_game(lottery_type, payload):
    if lottery_type not in PRIZE_MATCHES:
        raise ValueError("Loteria inválida.")
    if not isinstance(payload, dict):
        raise ValueError("Informe um objeto com as dezenas do jogo.")
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    numbers = payload.get("numbers")
    count = config["NUM_BALLS_TO_DRAW"]
    if not isinstance(numbers, list) or len(numbers) != count:
        raise ValueError(f"Informe exatamente {count} dezenas (aposta simples).")
    if any(type(number) is not int for number in numbers):
        raise ValueError("As dezenas devem ser números inteiros.")
    if len(set(numbers)) != count:
        raise ValueError("Não repita dezenas no mesmo jogo.")
    if any(not config["MIN_NUMBER"] <= number <= config["MAX_NUMBER"] for number in numbers):
        raise ValueError(f"Use dezenas de 1 a {config['MAX_NUMBER']}.")
    month = payload.get("month")
    if lottery_type == "diadesorte":
        if type(month) is not int or not 1 <= month <= 12:
            raise ValueError("Escolha o Mês da Sorte de janeiro a dezembro.")
    elif month is not None:
        raise ValueError("Esta loteria não utiliza Mês da Sorte.")
    return sorted(numbers), month


@lru_cache(maxsize=4)
def _read_draws(lottery_type, path, modified_ns, size, skiprows):
    # The file fingerprint invalidates cached data after the updater replaces a CSV.
    frame = lottery.load_data(path, skiprows)
    if frame is None or frame.empty:
        raise HistoryUnavailable("Histórico indisponível. Tente novamente mais tarde.")
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    columns = lottery.get_number_columns(frame, config)
    if len(columns) != config["NUM_BALLS_TO_DRAW"] or "Concurso" not in frame:
        raise HistoryUnavailable("O arquivo de resultados precisa ser revisado pelo administrador.")
    draws = {}
    skipped = 0
    months = config.get("EXTRA_CHOICES", {}).get("Mês da Sorte", [])
    for row in frame.to_dict("records"):
        try:
            raw = [float(row[column]) for column in columns]
            contest = float(row["Concurso"])
            if not contest.is_integer() or contest < 1 or any(not n.is_integer() for n in raw):
                raise ValueError()
            numbers = tuple(sorted(int(n) for n in raw))
            if len(set(numbers)) != len(columns) or not all(1 <= n <= config["MAX_NUMBER"] for n in numbers):
                raise ValueError()
            date = pd.to_datetime(row.get("Data", row.get("Data Sorteio")), dayfirst=True, errors="coerce")
            if pd.isna(date):
                raise ValueError()
            month_text = str(row.get("Mês da Sorte", "")).strip().casefold()
            month = next((i + 1 for i, name in enumerate(months) if name.casefold() == month_text), None)
            record = (int(contest), date.strftime("%d/%m/%Y"), numbers, month)
            if int(contest) in draws:
                if draws[int(contest)] != record:
                    raise HistoryUnavailable("Há concursos conflitantes na base. Solicite a revisão dos dados.")
                skipped += 1
            else:
                draws[int(contest)] = record
        except (ValueError, TypeError, OverflowError):
            skipped += 1
    if not draws:
        raise HistoryUnavailable("Não há concursos válidos para analisar.")
    return tuple(sorted(draws.values(), reverse=True)), skipped


def probability_summary(lottery_type):
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    count = config["NUM_BALLS_TO_DRAW"]
    universe = config["MAX_NUMBER"]
    total = comb(universe, count)
    tiers = []
    for hits in reversed(PRIZE_MATCHES[lottery_type]):
        remaining = count - hits
        ways = comb(count, hits) * (comb(universe - count, remaining) if remaining <= universe - count else 0)
        probability = ways / total
        tiers.append({"label": f"{hits} acertos", "matches": hits, "probability": probability, "one_in": 1 / probability})
    number_prize = sum(tier["probability"] for tier in tiers)
    any_prize = number_prize
    if lottery_type == "diadesorte":
        tiers.append({"label": "Mês da Sorte (independente)", "matches": None, "probability": 1 / 12, "one_in": 12})
        # Month and numbered tiers overlap: do not simply add their probabilities.
        any_prize = 1 - (1 - number_prize) * (11 / 12)
    return {"tiers": tiers, "any_prize": any_prize, "jackpot_one_in": total}


def load_validated_history(lottery_type):
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    try:
        stat = os.stat(config["FILE_PATH"])
    except OSError as error:
        raise HistoryUnavailable("Histórico indisponível. Solicite a atualização dos dados.") from error
    draws, skipped = _read_draws(lottery_type, config["FILE_PATH"], stat.st_mtime_ns, stat.st_size, config["SKIP_ROWS"])
    return draws, skipped, stat


def analyze_game(lottery_type, payload):
    numbers, month = validate_game(lottery_type, payload)
    draws, skipped, _ = load_validated_history(lottery_type)
    result, _ = analyze_validated_game(lottery_type, numbers, month, draws, skipped)
    return result


def analyze_validated_game(lottery_type, numbers, month, draws, skipped):
    """Analyze an already validated bet against a shared immutable history."""
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    selected = set(numbers)
    tier_counts = Counter()
    occurrences = []
    best = 0
    month_count = 0
    missing_months = 0
    strong_threshold = lottery.HISTORICAL_PRIZE_FILTERS[lottery_type]["min_matches"]
    had_strong_prize = False
    for contest, date, drawn, drawn_month in draws:
        hits = len(selected.intersection(drawn))
        best = max(best, hits)
        had_strong_prize |= hits >= strong_threshold
        month_hit = month is not None and month == drawn_month
        missing_months += int(month is not None and drawn_month is None)
        month_count += int(month_hit)
        if hits in PRIZE_MATCHES[lottery_type]:
            tier_counts[hits] += 1
        if hits in PRIZE_MATCHES[lottery_type] or month_hit:
            occurrences.append({"contest": contest, "date": date, "numbers": list(drawn), "matches": hits, "month_match": month_hit,
                                "matched_numbers": sorted(selected.intersection(drawn))})
    strategies = []
    for mode, label in lottery.GENERATION_MODES.items():
        if not lottery.is_generation_mode_available_for_lottery(mode, lottery_type):
            continue
        if mode == "never_prize":
            matches = not had_strong_prize
        elif mode == "balanced_never_prize":
            matches = not had_strong_prize and lottery.has_balanced_parity(numbers)
        else:
            matches = lottery.strategy_matches_historical_draw(numbers, mode, config)
        if matches:
            strategies.append({"mode": mode, "label": label})
    even = sum(n % 2 == 0 for n in numbers)
    filter_note = f"O filtro Sem prêmio histórico considera {strong_threshold} ou mais acertos numéricos na base consultada."
    if strong_threshold > min(PRIZE_MATCHES[lottery_type]):
        filter_note += " Ele não exclui as faixas numéricas menores."
    if lottery_type == "diadesorte":
        filter_note += " O filtro também não considera o Mês da Sorte."
    result = {
        "lottery_type": lottery_type, "lottery_name": lottery.LOTTERY_DISPLAY_NAMES[lottery_type],
        "numbers": numbers, "month": month,
        "coverage": {"total_draws": len(draws), "first_contest": draws[-1][0], "last_contest": draws[0][0],
                     "first_date": draws[-1][1], "last_date": draws[0][1], "skipped_rows": skipped,
                     "missing_months": missing_months,
                     "missing_contests": max(0, draws[0][0] - draws[-1][0] + 1 - len(draws))},
        "history": {"prize_draws": len(occurrences), "percentage": len(occurrences) / len(draws) * 100,
                    "best_matches": best, "month_matches": month_count,
                    "tiers": [{"matches": hits, "count": tier_counts[hits]} for hits in reversed(PRIZE_MATCHES[lottery_type])],
                    "recent_occurrences": occurrences[:30], "has_more": len(occurrences) > 30},
        "profile": {"even": even, "odd": len(numbers) - even, "sum": sum(numbers),
                    "consecutive_pairs": sum(b == a + 1 for a, b in zip(numbers, numbers[1:]))},
        "strategies": strategies,
        "strategy_note": ("Características compatíveis, não identificação do modo usado para gerar o jogo. "
                          "Normal e Tudo misturado não têm assinatura única; Quentes e frios depende da base usada na geração. "
                          + filter_note),
        "probabilities": probability_summary(lottery_type), "rules_url": RULES_URLS[lottery_type],
        "disclaimer": ("Simulação de aposta simples pelas faixas atuais, somente nos concursos válidos da base local. "
                       "Não comprova aposta ou prêmio recebido, não calcula valores nem aplica regras antigas. "
                       "Em sorteios justos e independentes, toda combinação simples tem a mesma chance. "
                       "Histórico e estratégia não preveem o próximo resultado. Jogue com responsabilidade. 18+."),
    }
    return result, frozenset(row['contest'] for row in occurrences)
