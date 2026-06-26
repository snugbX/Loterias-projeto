import os
import pandas as pd
import numpy as np
import datetime
import logging
import joblib

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
os.makedirs(OUTPUT_DIR, exist_ok=True)

_MODEL_CACHE = {}

logging.basicConfig(
    filename=os.path.join(PROJECT_ROOT, "loterias.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
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
    }
}

LOTTERY_DISPLAY_NAMES = {
    "megasena": "Mega Sena",
    "lotofacil": "Lotofácil",
    "quina": "Quina",
}


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

    return {
        "lottery_type": lottery_type,
        "name": LOTTERY_DISPLAY_NAMES.get(lottery_type, lottery_type),
        "contest": int(concurso) if pd.notna(concurso) and str(concurso).isdigit() else str(concurso),
        "date": str(date_value),
        "numbers": [int(number) for number in numbers],
        "color_primary": config["COLOR_PRIMARY"],
        "color_secondary": config["COLOR_SECONDARY"],
    }


def get_latest_results():
    results = {}

    for lottery_type in LOTTERY_CONFIGS:
        latest_result = get_latest_result(lottery_type)

        if latest_result is not None:
            results[lottery_type] = latest_result

    return results


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

def generate_n_lottery_games(lottery_type, num_games_to_generate=None):
    if lottery_type not in LOTTERY_CONFIGS:
        logging.error(f"Tipo de loteria inválido: {lottery_type}")
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

    model = load_trained_model(lottery_type)

    all_generated_games = []

    for _ in range(num_games):
        if lottery_type == "megasena":
            main_numbers = generate_filtered_megasena_game(
                probabilidades=prob_main_numbers,
                model=model,
                df=df,
                config=config
            )
        elif model is not None:
            main_numbers = generate_single_set_with_ml_proba(
                model=model,
                df=df,
                columns_prefix=config['CSV_COLUMNS_PREFIX'],
                min_num=config['MIN_NUMBER'],
                max_num=config['MAX_NUMBER'],
                num_to_draw=config['NUM_BALLS_TO_DRAW']
            )
        else:
            main_numbers = generate_single_set(
                probabilidades=prob_main_numbers,
                num_to_draw=config['NUM_BALLS_TO_DRAW'],
                min_num=config['MIN_NUMBER'],
                max_num=config['MAX_NUMBER']
            )

        all_generated_games.append([int(num) for num in main_numbers])

    return all_generated_games


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

        df_jogos = pd.DataFrame(jogos, columns=columns)
        os.makedirs(output_dir, exist_ok=True)
        df_jogos.to_csv(file_path, index=False, encoding='utf-8')

        try:
            import history_database

            history_database.save_history_record(
                file_name,
                lottery_type,
                [[int(num) for num in jogo] for jogo in jogos],
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
