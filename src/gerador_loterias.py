import os
import pandas as pd
import numpy as np
import datetime
import logging
import joblib
from itertools import combinations
from logging.handlers import RotatingFileHandler

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except Exception:
    pass


def resolve_project_path(path):
    if os.path.isabs(path):
        return path

    return os.path.join(PROJECT_ROOT, path)


def env_flag(name, default=False):
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = os.environ.get(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


OUTPUT_DIR = resolve_project_path(
    os.environ.get(
        "LOTTERY_OUTPUT_DIR",
        os.path.join(PROJECT_ROOT, "resultados_Loterias")
    )
)
MODEL_DIR = resolve_project_path(
    os.environ.get(
        "LOTTERY_MODEL_DIR",
        os.path.join(BASE_DIR, "models")
    )
)
USE_ML_MODELS = env_flag("LOTTERY_USE_ML", default=True)
LOG_FILE = resolve_project_path(
    os.environ.get(
        "LOTTERY_LOG_FILE",
        os.path.join(PROJECT_ROOT, "loterias.log")
    )
)
LOG_MAX_BYTES = env_int("LOTTERY_LOG_MAX_BYTES", 512 * 1024)
LOG_BACKUP_COUNT = env_int("LOTTERY_LOG_BACKUP_COUNT", 3)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

_MODEL_CACHE = {}

_log_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=LOG_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT,
    encoding="utf-8"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[_log_handler],
    force=True
)

LOTTERY_CONFIGS = {
    'megasena': {
        'FILE_PATH': os.path.join(PROJECT_ROOT, "mega_sena_asloterias_ate_concurso_3019_sorteio - mega_sena_www.asloterias.com.br.csv"),
        'NUM_BALLS_TO_DRAW': 6,
        'MIN_NUMBER': 1,
        'MAX_NUMBER': 60,
        'CSV_COLUMNS_PREFIX': 'bola ',
        'SKIP_ROWS': 6,
        'NUM_GAMES_DEFAULT': 5,
        'COLOR_PRIMARY': '#209869',
        'COLOR_SECONDARY': '#8FCBB3'
    },
    'lotofacil': {
        'FILE_PATH': os.path.join(PROJECT_ROOT, "loto_facil_asloterias_ate_concurso_3713_sorteio - lotofacil_www.asloterias.com.br.csv"),
        'NUM_BALLS_TO_DRAW': 15,
        'MIN_NUMBER': 1,
        'MAX_NUMBER': 25,
        'CSV_COLUMNS_PREFIX': 'bola ',
        'SKIP_ROWS': 6,
        'NUM_GAMES_DEFAULT': 5,
        'COLOR_PRIMARY': '#930089',
        'COLOR_SECONDARY': '#C87FC3'
    },
    'quina': {
        'FILE_PATH': os.path.join(PROJECT_ROOT, "quina_asloterias_ate_concurso_6759_sorteio - quina_www.asloterias.com.br.csv"),
        'NUM_BALLS_TO_DRAW': 5,
        'MIN_NUMBER': 1,
        'MAX_NUMBER': 80,
        'CSV_COLUMNS_PREFIX': 'bola ',
        'SKIP_ROWS': 6,
        'NUM_GAMES_DEFAULT': 5,
        'COLOR_PRIMARY': '#260085',
        'COLOR_SECONDARY': '#927FC1'
    },
    'diadesorte': {
        'FILE_PATH': os.path.join(PROJECT_ROOT, "dia_sorte_asloterias_ate_concurso_1230_sorteio - dia_de_sorte_www.asloterias.com.br.csv"),
        'NUM_BALLS_TO_DRAW': 7,
        'MIN_NUMBER': 1,
        'MAX_NUMBER': 31,
        'CSV_COLUMNS_PREFIX': 'bola ',
        'SKIP_ROWS': 6,
        'NUM_GAMES_DEFAULT': 5,
        'COLOR_PRIMARY': '#C76A00',
        'COLOR_SECONDARY': '#F4C56A',
        'EXTRA_COLUMNS': ['Mês da Sorte'],
        'EXTRA_CHOICES': {
            'Mês da Sorte': [
                'Janeiro',
                'Fevereiro',
                'Março',
                'Abril',
                'Maio',
                'Junho',
                'Julho',
                'Agosto',
                'Setembro',
                'Outubro',
                'Novembro',
                'Dezembro',
            ]
        }
    }
}

LOTTERY_DISPLAY_NAMES = {
    "megasena": "Mega Sena",
    "lotofacil": "Lotofácil",
    "quina": "Quina",
    "diadesorte": "Dia de Sorte",
}

GENERATION_MODES = {
    "normal": "Jogo normal",
    "balanced_parity": "Pares e ímpares equilibrados",
    "even_only": "Somente pares",
    "odd_only": "Somente ímpares",
    "spread": "Bem distribuído por faixas",
    "hot_cold_mix": "Quentes e frios misturados",
    "lucky_dates": "Datas da sorte",
    "high_numbers": "Números altos",
    "never_prize": "Sem prêmio histórico",
    "mixed": "Tudo junto e misturado",
}
PREMIUM_GENERATION_MODES = set(GENERATION_MODES) - {"normal"}
MIXED_STRATEGY_POOL = [
    "balanced_parity",
    "spread",
    "hot_cold_mix",
    "lucky_dates",
    "high_numbers",
]
HISTORICAL_PRIZE_FILTERS = {
    "megasena": {
        "min_matches": 4,
        "label": "quadra, quina ou sena",
    },
    "quina": {
        "min_matches": 4,
        "label": "quadra ou quina",
    },
    "lotofacil": {
        "min_matches": 13,
        "label": "13, 14 ou 15 acertos",
    },
    "diadesorte": {
        "min_matches": 5,
        "label": "5, 6 ou 7 dezenas",
    },
}


def normalize_generation_mode(mode):
    mode = (mode or "normal").strip().lower()

    if mode in GENERATION_MODES:
        return mode

    return None


def count_numbers_matching(config, predicate):
    return sum(1 for number in all_main_numbers(config) if predicate(number))


def is_generation_mode_available_for_lottery(mode, lottery_type):
    mode = normalize_generation_mode(mode)

    if mode is None or lottery_type not in LOTTERY_CONFIGS:
        return False

    if mode == "normal":
        return True

    config = LOTTERY_CONFIGS[lottery_type]
    num_to_draw = config['NUM_BALLS_TO_DRAW']

    if mode == "never_prize":
        return lottery_type in HISTORICAL_PRIZE_FILTERS

    if mode == "even_only":
        return count_numbers_matching(config, lambda number: number % 2 == 0) >= num_to_draw

    if mode == "odd_only":
        return count_numbers_matching(config, lambda number: number % 2 != 0) >= num_to_draw

    if mode == "high_numbers":
        midpoint = (config['MIN_NUMBER'] + config['MAX_NUMBER']) / 2
        return count_numbers_matching(config, lambda number: number > midpoint) >= num_to_draw

    if mode == "lucky_dates":
        date_count = count_numbers_matching(config, lambda number: number <= 31)
        total_numbers = len(all_main_numbers(config))
        return num_to_draw <= date_count < total_numbers

    if mode == "mixed":
        return bool(get_available_mixed_strategy_pool(lottery_type))

    return True


def get_available_mixed_strategy_pool(lottery_type):
    return [
        mode
        for mode in MIXED_STRATEGY_POOL
        if is_generation_mode_available_for_lottery(mode, lottery_type)
    ]


def sort_number_columns(columns):
    def extract_number(column_name):
        digits = "".join(filter(str.isdigit, column_name))
        return int(digits) if digits else 0

    return sorted(columns, key=extract_number)


def load_data(file_path, skiprows):
    try:
        return pd.read_csv(file_path, skiprows=skiprows, encoding="utf-8")

    except UnicodeDecodeError:
        try:
            logging.warning(
                f"Falha com utf-8. Tentando latin1: {file_path}"
            )

            return pd.read_csv(
                file_path,
                skiprows=skiprows,
                encoding="latin1"
            )

        except Exception as e:
            logging.error(
                f"Erro ao ler com latin1 '{file_path}': {e}"
            )

    except FileNotFoundError:
        logging.error(f"Arquivo não encontrado: {file_path}")

    except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
        logging.error(f"Erro ao ler o arquivo '{file_path}': {e}")

    except Exception as e:
        logging.error(
            f"Erro inesperado ao carregar '{file_path}': {e}"
        )

    return None


def calculate_probabilities(df, columns_prefix, min_num, max_num):
    number_cols = [
        col for col in df.columns
        if col.startswith(columns_prefix)
    ]

    if not number_cols:
        logging.error(f"Nenhuma coluna encontrada com prefixo: {columns_prefix}")
        return pd.Series(dtype=float)

    bolas_df = pd.concat([
        pd.to_numeric(df[col], errors="coerce")
        for col in number_cols
    ])
    bolas_df = bolas_df.dropna().astype(int)

    bolas_df = bolas_df[
        (bolas_df >= min_num) &
        (bolas_df <= max_num)
    ]

    if bolas_df.empty:
        return pd.Series(dtype=float)

    value_counts = bolas_df.value_counts()
    probabilidades = value_counts / len(bolas_df)

    return probabilidades.sort_values(ascending=False)


def get_latest_result(lottery_type):
    if lottery_type not in LOTTERY_CONFIGS:
        logging.error(f"Tipo de loteria inválido: {lottery_type}")
        return None

    config = LOTTERY_CONFIGS[lottery_type]
    df = load_data(config['FILE_PATH'], config['SKIP_ROWS'])

    if df is None or df.empty:
        return None

    number_cols = [
        col for col in df.columns
        if col.startswith(config['CSV_COLUMNS_PREFIX'])
    ]
    number_cols = sort_number_columns(number_cols)

    if not number_cols:
        logging.error(f"Nenhuma coluna de bola encontrada para {lottery_type}")
        return None

    latest_df = df.copy()

    if "Concurso" in latest_df.columns:
        latest_df["_sort_concurso"] = pd.to_numeric(
            latest_df["Concurso"],
            errors="coerce"
        )
        latest_df = latest_df.sort_values(
            "_sort_concurso",
            ascending=False,
            na_position="last"
        )

    latest_row = latest_df.iloc[0]
    numbers = (
        pd.to_numeric(latest_row[number_cols], errors="coerce")
        .dropna()
        .astype(int)
        .tolist()
    )

    concurso = latest_row.get("Concurso", "")
    date_value = latest_row.get("Data", latest_row.get("Data Sorteio", ""))
    extras = {}

    for column in config.get("EXTRA_COLUMNS", []):
        if column in latest_row.index and pd.notna(latest_row[column]):
            extras[column] = str(latest_row[column])

    result = {
        "lottery_type": lottery_type,
        "name": LOTTERY_DISPLAY_NAMES.get(lottery_type, lottery_type),
        "contest": int(concurso) if pd.notna(concurso) and str(concurso).isdigit() else str(concurso),
        "date": str(date_value),
        "numbers": [int(number) for number in numbers],
        "color_primary": config["COLOR_PRIMARY"],
        "color_secondary": config["COLOR_SECONDARY"],
    }

    if extras:
        result["extras"] = extras

    return result


def get_latest_results():
    results = {}

    for lottery_type in LOTTERY_CONFIGS:
        latest_result = get_latest_result(lottery_type)

        if latest_result is not None:
            results[lottery_type] = latest_result

    return results


def get_data_status():
    status = {}

    for lottery_type, config in LOTTERY_CONFIGS.items():
        file_path = config["FILE_PATH"]
        file_exists = os.path.exists(file_path)
        latest_result = get_latest_result(lottery_type) if file_exists else None
        modified_at = None
        file_size = None

        if file_exists:
            modified_at = datetime.datetime.fromtimestamp(
                os.path.getmtime(file_path)
            ).isoformat(timespec="seconds")
            file_size = os.path.getsize(file_path)

        status[lottery_type] = {
            "lottery_type": lottery_type,
            "name": LOTTERY_DISPLAY_NAMES.get(lottery_type, lottery_type),
            "file_exists": file_exists,
            "file_name": os.path.basename(file_path),
            "file_size": file_size,
            "modified_at": modified_at,
            "contest": latest_result.get("contest") if latest_result else None,
            "date": latest_result.get("date") if latest_result else None,
            "color_primary": config["COLOR_PRIMARY"],
            "color_secondary": config["COLOR_SECONDARY"],
        }

    return status


def generate_single_set(probabilidades, num_to_draw, min_num, max_num):
    all_numbers = list(range(min_num, max_num + 1))

    if num_to_draw > len(all_numbers):
        logging.error("Quantidade de números maior que a faixa disponível.")
        return []

    valid_probs = probabilidades[
        probabilidades.index.to_series().between(min_num, max_num)
    ].copy()

    chosen_numbers = set()

    if not valid_probs.empty and valid_probs.sum() > 0:
        normalized_probs = valid_probs / valid_probs.sum()

        try:
            chosen = np.random.choice(
                normalized_probs.index.tolist(),
                size=min(num_to_draw, len(normalized_probs)),
                replace=False,
                p=normalized_probs.values.tolist()
            )

            chosen_numbers.update(int(n) for n in chosen)

        except Exception as e:
            logging.warning(f"Erro na geração probabilística: {e}")

    if len(chosen_numbers) < num_to_draw:
        remaining_needed = num_to_draw - len(chosen_numbers)

        remaining_pool = [
            n for n in all_numbers
            if n not in chosen_numbers
        ]

        random_fill = np.random.choice(
            remaining_pool,
            size=remaining_needed,
            replace=False
        )

        chosen_numbers.update(int(n) for n in random_fill)

    return sorted(chosen_numbers)


def choose_weighted_extra_value(df, column_name, fallback_values):
    values = []

    if column_name in df.columns:
        values = (
            df[column_name]
            .dropna()
            .astype(str)
            .str.strip()
            .replace("", np.nan)
            .dropna()
            .tolist()
        )

    if values:
        counts = pd.Series(values).value_counts()
        probabilities = counts / counts.sum()

        try:
            return str(
                np.random.choice(
                    probabilities.index.tolist(),
                    p=probabilities.values.tolist()
                )
            )
        except Exception as e:
            logging.warning(f"Erro ao sortear valor extra '{column_name}': {e}")

    if fallback_values:
        return str(np.random.choice(fallback_values))

    return ""


def generate_extra_values(df, config):
    extra_values = []
    extra_choices = config.get("EXTRA_CHOICES", {})

    for column_name in config.get("EXTRA_COLUMNS", []):
        value = choose_weighted_extra_value(
            df,
            column_name,
            extra_choices.get(column_name, [])
        )

        if value:
            extra_values.append(value)

    return extra_values


def load_trained_model(lottery_type):
    if not USE_ML_MODELS:
        logging.info("Modelos ML desativados por LOTTERY_USE_ML=0.")
        return None

    if lottery_type in _MODEL_CACHE:
        return _MODEL_CACHE[lottery_type]

    model_path = os.path.join(
        MODEL_DIR,
        f"{lottery_type}_model.pkl"
    )

    if not os.path.exists(model_path):
        logging.warning(f"Modelo não encontrado para {lottery_type}: {model_path}")
        return None

    try:
        loaded = joblib.load(model_path)

        if isinstance(loaded, dict):
            if "model" in loaded:
                metadata = loaded.get("metadata", {})

                logging.info(
                    f"Modelo carregado para {lottery_type}. "
                    f"Treinado em: {metadata.get('trained_at', 'não informado')}"
                )

                _MODEL_CACHE[lottery_type] = loaded["model"]
                return _MODEL_CACHE[lottery_type]

        logging.warning(
            f"Formato antigo de modelo detectado para {lottery_type}."
        )

        _MODEL_CACHE[lottery_type] = loaded
        return _MODEL_CACHE[lottery_type]

    except Exception as e:
        logging.error(f"Erro ao carregar modelo de {lottery_type}: {e}")
        return None


def draw_to_binary(row, max_num):
    numbers = set(pd.to_numeric(row, errors='coerce').dropna().astype(int).values)

    return [
        1 if number in numbers else 0
        for number in range(1, max_num + 1)
    ]


def generate_single_set_with_ml_proba(
    model,
    df,
    columns_prefix,
    min_num,
    max_num,
    num_to_draw
):
    number_cols = [
        col for col in df.columns
        if col.startswith(columns_prefix)
    ]

    if not number_cols:
        logging.error(f"Nenhuma coluna encontrada para ML com prefixo: {columns_prefix}")
        return generate_random_set(min_num, max_num, num_to_draw)

    df_numbers = (
        df[number_cols]
        .apply(pd.to_numeric, errors="coerce")
        .dropna()
        .astype(int)
    )

    if df_numbers.empty:
        if len(df_numbers) < 2:
            logging.warning("Poucos dados disponíveis para geração ML.")
            return generate_random_set(min_num,max_num,num_to_draw)
                    
        logging.warning("Dados vazios para geração com ML.")
        return generate_random_set(min_num, max_num, num_to_draw)

    last_draw = df_numbers.iloc[-1]
    base_input = draw_to_binary(last_draw, max_num)

    try:
        proba_list = model.predict_proba([base_input])
        probs = []

        for proba in proba_list:
            if hasattr(proba, "shape") and proba.shape[1] > 1:
                probs.append(float(proba[0][1]))
            else:
                probs.append(0.0)

        if len(probs) != max_num:
            logging.warning("Quantidade de probabilidades diferente do esperado.")
            return generate_random_set(min_num, max_num, num_to_draw)

        probs = np.array(probs, dtype=float)

        valid_indices = list(range(min_num - 1, max_num))
        valid_numbers = list(range(min_num, max_num + 1))
        valid_probs = probs[valid_indices]

        prob_sum = valid_probs.sum()

        if prob_sum <= 0:
            valid_probs = np.ones(len(valid_numbers)) / len(valid_numbers)
        else:
            valid_probs = valid_probs / prob_sum

        sample_size = min(num_to_draw, len(valid_numbers))

        chosen = np.random.choice(
            valid_numbers,
            size=sample_size,
            replace=False,
            p=valid_probs
        )

        return sorted([int(n) for n in chosen])

    except Exception as e:
        logging.error(f"Erro ao usar predict_proba no modelo ML: {e}")
        return generate_random_set(min_num, max_num, num_to_draw)


def generate_random_set(min_num, max_num, num_to_draw):
    return sorted(
        np.random.choice(
            range(min_num, max_num + 1),
            size=num_to_draw,
            replace=False
        ).astype(int).tolist()
    )


def all_main_numbers(config):
    return list(range(config['MIN_NUMBER'], config['MAX_NUMBER'] + 1))


def weighted_sample_from_pool(pool, probabilidades, count):
    pool = sorted({int(number) for number in pool})

    if count <= 0:
        return []

    if len(pool) < count:
        return []

    weights = np.array(
        [float(probabilidades.get(number, 0.0)) + 0.0001 for number in pool],
        dtype=float
    )

    if weights.sum() <= 0:
        weights = np.ones(len(pool), dtype=float) / len(pool)
    else:
        weights = weights / weights.sum()

    return sorted(
        np.random.choice(
            pool,
            size=count,
            replace=False,
            p=weights
        ).astype(int).tolist()
    )


def fill_missing_numbers(selected, config, probabilidades):
    selected = list(dict.fromkeys(int(number) for number in selected))
    needed = config['NUM_BALLS_TO_DRAW'] - len(selected)

    if needed <= 0:
        return sorted(selected[:config['NUM_BALLS_TO_DRAW']])

    pool = [
        number
        for number in all_main_numbers(config)
        if number not in selected
    ]
    selected.extend(weighted_sample_from_pool(pool, probabilidades, needed))

    return sorted(selected)


def generate_balanced_parity_set(config, probabilidades):
    num_to_draw = config['NUM_BALLS_TO_DRAW']
    even_pool = [number for number in all_main_numbers(config) if number % 2 == 0]
    odd_pool = [number for number in all_main_numbers(config) if number % 2 != 0]

    if num_to_draw % 2 == 0:
        even_count = num_to_draw // 2
    else:
        even_count = int(np.random.choice([num_to_draw // 2, num_to_draw // 2 + 1]))

    odd_count = num_to_draw - even_count

    selected = []
    selected.extend(weighted_sample_from_pool(even_pool, probabilidades, even_count))
    selected.extend(weighted_sample_from_pool(odd_pool, probabilidades, odd_count))

    return fill_missing_numbers(selected, config, probabilidades)


def generate_pool_set(config, probabilidades, predicate, strict=False):
    pool = [number for number in all_main_numbers(config) if predicate(number)]
    num_to_draw = config['NUM_BALLS_TO_DRAW']

    if strict and len(pool) < num_to_draw:
        raise ValueError(
            "Essa estratégia não tem dezenas suficientes para esta loteria."
        )

    selected = weighted_sample_from_pool(
        pool,
        probabilidades,
        min(len(pool), num_to_draw)
    )

    return fill_missing_numbers(selected, config, probabilidades)


def generate_spread_set(config, probabilidades):
    numbers = all_main_numbers(config)
    num_to_draw = config['NUM_BALLS_TO_DRAW']
    bucket_count = min(5, num_to_draw, len(numbers))
    bucket_size = int(np.ceil(len(numbers) / bucket_count))
    selected = []

    for bucket_index in range(bucket_count):
        start = bucket_index * bucket_size
        end = min(start + bucket_size, len(numbers))
        bucket = numbers[start:end]
        count = num_to_draw // bucket_count

        if bucket_index < num_to_draw % bucket_count:
            count += 1

        selected.extend(weighted_sample_from_pool(bucket, probabilidades, count))

    return fill_missing_numbers(selected, config, probabilidades)


def generate_hot_cold_mix_set(config, probabilidades):
    numbers = all_main_numbers(config)
    num_to_draw = config['NUM_BALLS_TO_DRAW']
    frequency = {
        number: float(probabilidades.get(number, 0.0))
        for number in numbers
    }
    pool_size = min(len(numbers), max(num_to_draw * 2, num_to_draw))
    hot_pool = sorted(numbers, key=lambda number: frequency[number], reverse=True)[:pool_size]
    cold_pool = sorted(numbers, key=lambda number: (frequency[number], number))[:pool_size]
    hot_count = num_to_draw // 2
    cold_count = num_to_draw - hot_count
    selected = []

    selected.extend(weighted_sample_from_pool(hot_pool, probabilidades, hot_count))
    selected.extend(weighted_sample_from_pool(cold_pool, probabilidades, cold_count))

    return fill_missing_numbers(selected, config, probabilidades)


def get_number_columns(df, config):
    return sort_number_columns([
        col for col in df.columns
        if col.startswith(config['CSV_COLUMNS_PREFIX'])
    ])


def get_historical_number_sets(df, config):
    number_cols = get_number_columns(df, config)

    if not number_cols:
        return []

    historical_sets = []

    for _, row in df[number_cols].iterrows():
        numbers = (
            pd.to_numeric(row, errors="coerce")
            .dropna()
            .astype(int)
            .tolist()
        )

        if len(numbers) >= config['NUM_BALLS_TO_DRAW']:
            historical_sets.append(frozenset(numbers[:config['NUM_BALLS_TO_DRAW']]))

    return historical_sets


def get_historical_number_lists(df, config):
    number_cols = get_number_columns(df, config)

    if not number_cols:
        return []

    historical_lists = []

    for _, row in df[number_cols].iterrows():
        numbers = (
            pd.to_numeric(row, errors="coerce")
            .dropna()
            .astype(int)
            .tolist()
        )

        if len(numbers) >= config['NUM_BALLS_TO_DRAW']:
            historical_lists.append([
                int(number)
                for number in numbers[:config['NUM_BALLS_TO_DRAW']]
            ])

    return historical_lists


def has_balanced_parity(numbers):
    even_count = sum(1 for number in numbers if number % 2 == 0)
    odd_count = len(numbers) - even_count

    return abs(even_count - odd_count) <= 1


def has_spread_distribution(numbers, config):
    all_numbers = all_main_numbers(config)
    bucket_count = min(5, config['NUM_BALLS_TO_DRAW'], len(all_numbers))

    if bucket_count <= 0:
        return False

    bucket_size = int(np.ceil(len(all_numbers) / bucket_count))
    bucket_counts = [0] * bucket_count

    for number in numbers:
        index = min(
            bucket_count - 1,
            max(0, (int(number) - config['MIN_NUMBER']) // bucket_size)
        )
        bucket_counts[index] += 1

    return min(bucket_counts) > 0 and max(bucket_counts) - min(bucket_counts) <= 1


def strategy_matches_historical_draw(numbers, mode, config):
    if mode == "balanced_parity":
        return has_balanced_parity(numbers)

    if mode == "even_only":
        return all(number % 2 == 0 for number in numbers)

    if mode == "odd_only":
        return all(number % 2 != 0 for number in numbers)

    if mode == "spread":
        return has_spread_distribution(numbers, config)

    if mode == "lucky_dates":
        return all(number <= 31 for number in numbers)

    if mode == "high_numbers":
        midpoint = (config['MIN_NUMBER'] + config['MAX_NUMBER']) / 2
        return all(number > midpoint for number in numbers)

    return None


def get_generation_strategy_stats(lottery_type):
    if lottery_type not in LOTTERY_CONFIGS:
        logging.error(f"Tipo de loteria invÃ¡lido: {lottery_type}")
        return None

    config = LOTTERY_CONFIGS[lottery_type]
    df = load_data(config['FILE_PATH'], config['SKIP_ROWS'])

    if df is None or df.empty:
        return {
            "lottery_type": lottery_type,
            "total_draws": 0,
            "modes": {},
        }

    historical_draws = get_historical_number_lists(df, config)
    total_draws = len(historical_draws)
    modes = {}

    for mode, label in GENERATION_MODES.items():
        available = is_generation_mode_available_for_lottery(mode, lottery_type)
        stat_payload = {
            "mode": mode,
            "label": label,
            "available": available,
            "has_stat": False,
            "matches": None,
            "total": total_draws,
            "percentage": None,
        }

        if mode == "normal":
            stat_payload["message"] = "Base padr\u00e3o"
        elif mode in {"never_prize", "hot_cold_mix", "mixed"}:
            stat_payload["message"] = "Sem base hist\u00f3rica direta"
        elif available and total_draws > 0:
            matches = sum(
                1
                for numbers in historical_draws
                if strategy_matches_historical_draw(numbers, mode, config)
            )
            stat_payload.update({
                "has_stat": True,
                "matches": matches,
                "percentage": round((matches / total_draws) * 100, 2),
                "message": f"{matches} de {total_draws} sorteios",
            })
        elif not available:
            stat_payload["message"] = "Indispon\u00edvel nesta loteria"
        else:
            stat_payload["message"] = "Sem dados suficientes"

        modes[mode] = stat_payload

    return {
        "lottery_type": lottery_type,
        "lottery_name": LOTTERY_DISPLAY_NAMES.get(lottery_type, lottery_type),
        "total_draws": total_draws,
        "modes": modes,
    }


def has_historical_prize(game, historical_sets, min_matches):
    game_set = set(int(number) for number in game)

    return any(
        len(game_set.intersection(historical_set)) >= min_matches
        for historical_set in historical_sets
    )


def build_historical_prize_signatures(historical_sets, min_matches):
    signatures = set()

    for historical_set in historical_sets:
        numbers = sorted(int(number) for number in historical_set)

        for prize_combo in combinations(numbers, min_matches):
            signatures.add(prize_combo)

    return signatures


def has_historical_prize_signature(game, historical_prize_signatures, min_matches):
    numbers = sorted(int(number) for number in game)

    return any(
        prize_combo in historical_prize_signatures
        for prize_combo in combinations(numbers, min_matches)
    )


def generate_default_main_numbers(lottery_type, probabilidades, model, df, config):
    if lottery_type == "megasena":
        return generate_filtered_megasena_game(
            probabilidades=probabilidades,
            model=model,
            df=df,
            config=config
        )

    if model is not None:
        return generate_single_set_with_ml_proba(
            model=model,
            df=df,
            columns_prefix=config['CSV_COLUMNS_PREFIX'],
            min_num=config['MIN_NUMBER'],
            max_num=config['MAX_NUMBER'],
            num_to_draw=config['NUM_BALLS_TO_DRAW']
        )

    return generate_single_set(
        probabilidades=probabilidades,
        num_to_draw=config['NUM_BALLS_TO_DRAW'],
        min_num=config['MIN_NUMBER'],
        max_num=config['MAX_NUMBER']
    )


def generate_candidate_by_mode(lottery_type, mode, probabilidades, model, df, config):
    if mode == "normal":
        return generate_default_main_numbers(lottery_type, probabilidades, model, df, config)

    if mode == "balanced_parity":
        return generate_balanced_parity_set(config, probabilidades)

    if mode == "even_only":
        return generate_pool_set(
            config,
            probabilidades,
            lambda number: number % 2 == 0,
            strict=True
        )

    if mode == "odd_only":
        return generate_pool_set(
            config,
            probabilidades,
            lambda number: number % 2 != 0,
            strict=True
        )

    if mode == "spread":
        return generate_spread_set(config, probabilidades)

    if mode == "hot_cold_mix":
        return generate_hot_cold_mix_set(config, probabilidades)

    if mode == "lucky_dates":
        return generate_pool_set(
            config,
            probabilidades,
            lambda number: number <= 31,
            strict=True
        )

    if mode == "high_numbers":
        midpoint = (config['MIN_NUMBER'] + config['MAX_NUMBER']) / 2
        return generate_pool_set(
            config,
            probabilidades,
            lambda number: number > midpoint,
            strict=True
        )

    return generate_default_main_numbers(lottery_type, probabilidades, model, df, config)


def generate_main_numbers_with_mode(
    lottery_type,
    generation_mode,
    probabilidades,
    model,
    df,
    config,
    historical_prize_signatures
):
    if not is_generation_mode_available_for_lottery(generation_mode, lottery_type):
        raise ValueError(
            "Essa estratégia não está disponível para a loteria escolhida."
        )

    historical_filter = HISTORICAL_PRIZE_FILTERS.get(lottery_type)

    if generation_mode == "never_prize" and historical_filter is None:
        raise ValueError(
            "O modo sem prêmio histórico não está disponível para esta loteria."
        )

    max_attempts = 5000 if generation_mode == "never_prize" else 800
    min_prize_matches = (
        historical_filter["min_matches"]
        if historical_filter
        else None
    )
    mixed_strategy_pool = (
        get_available_mixed_strategy_pool(lottery_type)
        if generation_mode == "mixed"
        else []
    )

    for _ in range(max_attempts):
        mode = generation_mode

        if generation_mode == "mixed":
            mode = str(np.random.choice(mixed_strategy_pool))

        if generation_mode == "never_prize":
            candidate = generate_random_set(
                config['MIN_NUMBER'],
                config['MAX_NUMBER'],
                config['NUM_BALLS_TO_DRAW']
            )
        else:
            candidate = generate_candidate_by_mode(
                lottery_type,
                mode,
                probabilidades,
                model,
                df,
                config
            )

        if not candidate:
            continue

        if generation_mode == "never_prize" and has_historical_prize_signature(
            candidate,
            historical_prize_signatures,
            min_prize_matches
        ):
            continue

        return sorted(int(number) for number in candidate)

    raise ValueError(
        "Não foi possível encontrar uma combinação para essa estratégia agora. "
        "Tente reduzir a quantidade de jogos ou usar outro modo."
    )



def is_good_megasena_game(game):
    """
    Aplica filtros estatísticos simples para evitar jogos muito desequilibrados
    na Mega-Sena.

    Observação: isso não garante acerto, apenas remove combinações pouco
    interessantes, como jogos muito concentrados, com soma muito baixa/alta
    ou com excesso de pares/ímpares.
    """
    game = sorted([int(n) for n in game])

    if len(game) != 6:
        return False

    pares = sum(1 for n in game if n % 2 == 0)
    soma = sum(game)

    faixas = [
        sum(1 for n in game if 1 <= n <= 10),
        sum(1 for n in game if 11 <= n <= 20),
        sum(1 for n in game if 21 <= n <= 30),
        sum(1 for n in game if 31 <= n <= 40),
        sum(1 for n in game if 41 <= n <= 50),
        sum(1 for n in game if 51 <= n <= 60),
    ]

    sequencias = sum(
        1
        for i in range(len(game) - 1)
        if game[i + 1] == game[i] + 1
    )

    if pares < 2 or pares > 4:
        return False

    if soma < 120 or soma > 240:
        return False

    if max(faixas) > 3:
        return False

    if sequencias > 2:
        return False

    return True


def generate_filtered_megasena_game(probabilidades, model, df, config):
    """
    Gera um jogo da Mega-Sena usando ML quando disponível e, em seguida,
    aplica filtros estatísticos para melhorar o equilíbrio da combinação.
    """
    max_attempts = 500

    for _ in range(max_attempts):
        if model is not None:
            game = generate_single_set_with_ml_proba(
                model=model,
                df=df,
                columns_prefix=config['CSV_COLUMNS_PREFIX'],
                min_num=config['MIN_NUMBER'],
                max_num=config['MAX_NUMBER'],
                num_to_draw=config['NUM_BALLS_TO_DRAW']
            )
        else:
            game = generate_single_set(
                probabilidades=probabilidades,
                num_to_draw=config['NUM_BALLS_TO_DRAW'],
                min_num=config['MIN_NUMBER'],
                max_num=config['MAX_NUMBER']
            )

        if is_good_megasena_game(game):
            return game

    logging.warning(
        "Não foi possível gerar uma Mega-Sena filtrada dentro do limite "
        "de tentativas. Usando geração padrão."
    )

    if model is not None:
        return generate_single_set_with_ml_proba(
            model=model,
            df=df,
            columns_prefix=config['CSV_COLUMNS_PREFIX'],
            min_num=config['MIN_NUMBER'],
            max_num=config['MAX_NUMBER'],
            num_to_draw=config['NUM_BALLS_TO_DRAW']
        )

    return generate_single_set(
        probabilidades=probabilidades,
        num_to_draw=config['NUM_BALLS_TO_DRAW'],
        min_num=config['MIN_NUMBER'],
        max_num=config['MAX_NUMBER']
    )

def generate_n_lottery_games(lottery_type, num_games_to_generate=None, generation_mode="normal"):
    if lottery_type not in LOTTERY_CONFIGS:
        logging.error(f"Tipo de loteria inválido: {lottery_type}")
        return []

    generation_mode = normalize_generation_mode(generation_mode)

    if generation_mode is None:
        logging.error("Modo de geração inválido.")
        return []

    config = LOTTERY_CONFIGS[lottery_type]

    num_games = (
        num_games_to_generate
        if num_games_to_generate is not None
        else config['NUM_GAMES_DEFAULT']
    )

    df = load_data(config['FILE_PATH'], config['SKIP_ROWS'])

    if df is None:
        return []

    prob_main_numbers = calculate_probabilities(
        df,
        config['CSV_COLUMNS_PREFIX'],
        config['MIN_NUMBER'],
        config['MAX_NUMBER']
    )

    model = (
        None
        if generation_mode == "never_prize"
        else load_trained_model(lottery_type)
    )
    historical_prize_signatures = set()

    if generation_mode == "never_prize":
        historical_filter = HISTORICAL_PRIZE_FILTERS.get(lottery_type)

        if historical_filter is None:
            raise ValueError(
                "O modo sem prêmio histórico não está disponível para esta loteria."
            )

        historical_sets = get_historical_number_sets(df, config)
        historical_prize_signatures = build_historical_prize_signatures(
            historical_sets,
            historical_filter["min_matches"]
        )

    all_generated_games = []

    for _ in range(num_games):
        main_numbers = generate_main_numbers_with_mode(
            lottery_type=lottery_type,
            generation_mode=generation_mode,
            probabilidades=prob_main_numbers,
            model=model,
            df=df,
            config=config,
            historical_prize_signatures=historical_prize_signatures
        )

        game = [int(num) for num in main_numbers]
        game.extend(generate_extra_values(df, config))
        all_generated_games.append(game)

    return all_generated_games


def serialize_game_value(value):
    if pd.isna(value):
        return ""

    try:
        numeric_value = float(value)

        if numeric_value.is_integer():
            return int(numeric_value)

    except (TypeError, ValueError):
        pass

    return str(value)


def save_generated_games_to_csv(jogos, lottery_type, output_dir):
    if not jogos:
        logging.info(f"Nenhum jogo para salvar para {lottery_type}.")
        return

    if lottery_type not in LOTTERY_CONFIGS:
        logging.error(f"Tipo de loteria inválido ao salvar: {lottery_type}")
        return

    now = datetime.datetime.now()
    data_hora = now.strftime("%Y-%m-%d_%H-%M-%S")

    file_name = f"{lottery_type}_resultados_{data_hora}.csv"
    file_path = os.path.join(output_dir, file_name)

    try:
        config = LOTTERY_CONFIGS[lottery_type]

        columns = [
            f"{config['CSV_COLUMNS_PREFIX'].strip()}{i + 1}"
            for i in range(config['NUM_BALLS_TO_DRAW'])
        ]
        columns.extend(config.get("EXTRA_COLUMNS", []))

        df_jogos = pd.DataFrame(jogos, columns=columns)
        os.makedirs(output_dir, exist_ok=True)
        df_jogos.to_csv(file_path, index=False, encoding='utf-8')

        try:
            import history_database

            history_database.save_history_record(
                file_name,
                lottery_type,
                [
                    [serialize_game_value(value) for value in jogo]
                    for jogo in jogos
                ],
                now.isoformat(timespec="seconds")
            )
        except Exception as e:
            logging.error(f"Erro ao salvar histórico no banco SQLite: {e}")

        logging.info(
            f"{len(jogos)} jogos de {lottery_type} salvos em '{file_path}'"
        )

        print(f"Resultados de {lottery_type} salvos em: {file_path}")

    except Exception as e:
        logging.error(f"Erro ao salvar jogos de {lottery_type} em CSV: {e}")


def get_hot_cold_numbers(lottery_type, top_n=10):
    if lottery_type not in LOTTERY_CONFIGS:
        logging.error(f"Tipo de loteria inválido: {lottery_type}")
        return {
            "hot_numbers": [],
            "cold_numbers": []
        }

    config = LOTTERY_CONFIGS[lottery_type]
    df = load_data(config['FILE_PATH'], config['SKIP_ROWS'])

    if df is None:
        return {
            "hot_numbers": [],
            "cold_numbers": []
        }

    number_cols = [
        col for col in df.columns
        if col.startswith(config['CSV_COLUMNS_PREFIX'])
    ]

    if not number_cols:
        logging.error(f"Nenhuma coluna encontrada para {lottery_type}")
        return {
            "hot_numbers": [],
            "cold_numbers": []
        }

    bolas_df = pd.concat([df[col] for col in number_cols])
    bolas_df = pd.to_numeric(bolas_df, errors='coerce').dropna().astype(int)

    bolas_validas = bolas_df[
        (bolas_df >= config['MIN_NUMBER']) &
        (bolas_df <= config['MAX_NUMBER'])
    ]

    if bolas_validas.empty:
        return {
            "hot_numbers": [],
            "cold_numbers": []
        }

    value_counts = bolas_validas.value_counts()

    all_possible_numbers = set(
        range(config['MIN_NUMBER'], config['MAX_NUMBER'] + 1)
    )

    drawn_numbers = set(value_counts.index)
    never_drawn = sorted(list(all_possible_numbers - drawn_numbers))

    hot_numbers = value_counts.head(top_n).index.astype(int).tolist()

    cold_numbers_drawn = (
        value_counts
        .sort_values(ascending=True)
        .head(max(0, top_n - len(never_drawn)))
        .index
        .astype(int)
        .tolist()
    )

    cold_numbers = sorted(
        list(set(never_drawn + cold_numbers_drawn))
    )[:top_n]

    return {
        "hot_numbers": hot_numbers,
        "cold_numbers": cold_numbers
    }


def main():
    for lottery_type in LOTTERY_CONFIGS.keys():
        print("\n" + "=" * 60)
        print(f"{lottery_type.upper():^60}")
        print("=" * 60)

        config = LOTTERY_CONFIGS[lottery_type]

        games = generate_n_lottery_games(
            lottery_type,
            num_games_to_generate=2
        )

        if games:
            columns = [
                f"bola {i + 1}"
                for i in range(config['NUM_BALLS_TO_DRAW'])
            ]

            print(pd.DataFrame(games, columns=columns))

            save_generated_games_to_csv(
                games,
                lottery_type,
                OUTPUT_DIR
            )

            hot_cold = get_hot_cold_numbers(lottery_type)

            print(f"Números quentes: {hot_cold['hot_numbers']}")
            print(f"Números frios: {hot_cold['cold_numbers']}")


if __name__ == "__main__":
    main()
