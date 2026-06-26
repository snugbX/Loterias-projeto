import os
import time
import json
import hashlib
import joblib
import numpy as np
import pandas as pd

from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import hamming_loss, accuracy_score, f1_score

from gerador_loterias import LOTTERY_CONFIGS, MODEL_DIR


RANDOM_STATE = 42
TEST_SIZE = 0.2


def line(char="=", size=70):
    print(char * size)


def title(text):
    print()
    line("=")
    print(f"{text:^70}")
    line("=")


def step(text):
    print(f"  → {text}")


def success(text):
    print(f"  ✓ {text}")


def warning(text):
    print(f"  ⚠ {text}")


def error(text):
    print(f"  ✗ {text}")


def info(label, value):
    print(f"  {label:<22}: {value}")


def format_seconds(seconds):
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours >= 1:
        return f"{int(hours)}h {int(minutes)}min {sec:.2f}s"

    if minutes >= 1:
        return f"{int(minutes)}min {sec:.2f}s"

    return f"{sec:.2f}s"


def generate_data_hash(df_numbers):
    data_string = df_numbers.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(data_string).hexdigest()


def sort_number_columns(columns):
    def extract_number(col):
        digits = "".join(filter(str.isdigit, col))
        return int(digits) if digits else 0

    return sorted(columns, key=extract_number)


def read_csv_safely(file_path):
    try:
        return pd.read_csv(file_path, skiprows=6)
    except UnicodeDecodeError:
        warning("Falha com encoding padrão. Tentando latin1...")
        return pd.read_csv(file_path, skiprows=6, encoding="latin1")


def draws_to_binary_matrix(df_numbers, max_number):
    values = df_numbers.to_numpy(dtype=int)

    binary = np.zeros((len(values), max_number), dtype=np.uint8)

    rows = np.repeat(np.arange(len(values)), values.shape[1])
    cols = values.flatten() - 1

    valid = (cols >= 0) & (cols < max_number)
    binary[rows[valid], cols[valid]] = 1

    return binary


def validate_draw_data(df_numbers, max_number):
    step("Validando dados dos sorteios")

    if df_numbers.empty:
        raise ValueError("Nenhum sorteio válido encontrado.")

    if df_numbers.isnull().any().any():
        raise ValueError("Existem valores vazios nas colunas dos sorteios.")

    invalid_mask = (df_numbers < 1) | (df_numbers > max_number)

    if invalid_mask.any().any():
        raise ValueError(
            f"Existem números fora do intervalo permitido: 1 até {max_number}."
        )

    duplicated_rows = df_numbers.duplicated().sum()

    if duplicated_rows > 0:
        warning(f"Sorteios duplicados encontrados: {duplicated_rows}")
    else:
        success("Nenhum sorteio duplicado encontrado")

    repeated_numbers = df_numbers.apply(
        lambda row: row.duplicated().any(),
        axis=1
    )

    if repeated_numbers.any():
        raise ValueError(
            "Existem sorteios com números repetidos na mesma linha."
        )

    success("Dados validados com sucesso")


def sort_dataframe_if_possible(df):
    if "Concurso" in df.columns:
        step("Ordenando dados pela coluna Concurso")
        return df.sort_values("Concurso").reset_index(drop=True)

    if "Data Sorteio" in df.columns:
        step("Ordenando dados pela coluna Data Sorteio")
        df["Data Sorteio"] = pd.to_datetime(
            df["Data Sorteio"],
            errors="coerce",
            dayfirst=True
        )
        return df.sort_values("Data Sorteio").reset_index(drop=True)

    warning("Nenhuma coluna de ordenação encontrada. Mantendo ordem original.")
    return df.reset_index(drop=True)


def save_training_report(report_path, report_data):
    with open(report_path, "w", encoding="utf-8") as file:
        json.dump(report_data, file, indent=4, ensure_ascii=False)


def train_model(file_path, columns_prefix, max_number, model_path):
    start_time = time.time()

    model_path = Path(model_path)
    report_path = model_path.with_suffix(".json")

    title(f"TREINAMENTO: {model_path.name}")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    model_path.parent.mkdir(parents=True, exist_ok=True)

    step("Carregando CSV")
    df = read_csv_safely(file_path)
    success(f"CSV carregado com {len(df)} linhas")

    original_rows = len(df)

    df = sort_dataframe_if_possible(df)

    number_cols = [
        col for col in df.columns
        if col.startswith(columns_prefix)
    ]

    number_cols = sort_number_columns(number_cols)

    if not number_cols:
        raise ValueError(
            f"Nenhuma coluna encontrada com o prefixo: {columns_prefix}"
        )

    info("Colunas numéricas", len(number_cols))

    df_numbers = df[number_cols].dropna().astype(int)

    removed_rows = original_rows - len(df_numbers)

    if removed_rows > 0:
        warning(f"Linhas removidas por dados vazios: {removed_rows}")

    if len(df_numbers) < 10:
        warning("Poucos dados disponíveis. As métricas podem ser pouco confiáveis.")

    if len(df_numbers) < 2:
        raise ValueError("Dados insuficientes para treino.")

    validate_draw_data(df_numbers, max_number)

    data_hash = generate_data_hash(df_numbers)

    step("Convertendo sorteios para matriz binária")
    binary_matrix = draws_to_binary_matrix(
        df_numbers,
        max_number
    )
    success("Matriz binária criada")

    step("Separando dados de treino e teste")

    data = binary_matrix[:-1]
    targets = binary_matrix[1:]

    x_train, x_test, y_train, y_test = train_test_split(
        data,
        targets,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        shuffle=False
    )

    info("Treino", len(x_train))
    info("Teste", len(x_test))

    if len(x_test) == 0:
        raise ValueError("Base de teste ficou vazia.")

    step("Criando modelo RandomForest")

    base_model = RandomForestClassifier(
        n_estimators=300,
        max_depth=16,
        min_samples_leaf=2,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        class_weight="balanced_subsample",
        verbose=0
    )

    model = MultiOutputClassifier(base_model)

    step("Treinando modelo")
    model.fit(x_train, y_train)
    success("Modelo treinado")

    step("Realizando previsões")
    predictions = model.predict(x_test)

    step("Calculando métricas")
    loss = hamming_loss(y_test, predictions)
    exact_match = accuracy_score(y_test, predictions)
    f1 = f1_score(
        y_test,
        predictions,
        average="micro",
        zero_division=0
    )

    elapsed = time.time() - start_time

    training_metadata = {
        "model_path": str(model_path),
        "source_file": str(file_path),
        "max_number": max_number,
        "columns_prefix": columns_prefix,
        "number_columns": number_cols,
        "total_original_rows": original_rows,
        "total_valid_draws": len(df_numbers),
        "removed_rows": removed_rows,
        "train_size": len(x_train),
        "test_size": len(x_test),
        "test_size_percent": TEST_SIZE,
        "random_state": RANDOM_STATE,
        "hamming_loss": float(loss),
        "exact_match": float(exact_match),
        "f1_score": float(f1),
        "data_hash_sha256": data_hash,
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(elapsed, 2)
    }

    model_package = {
        "model": model,
        "metadata": training_metadata
    }

    step("Salvando modelo")
    joblib.dump(
        model_package,
        model_path,
        compress=3
    )
    success("Modelo salvo")

    step("Salvando relatório de treinamento")
    save_training_report(report_path, training_metadata)
    success(f"Relatório salvo em {report_path}")

    title("TREINAMENTO FINALIZADO")
    info("Modelo salvo", model_path)
    info("Relatório", report_path)
    info("Hamming Loss", f"{loss:.6f}")
    info("Exact Match", f"{exact_match:.6f}")
    info("F1 Score", f"{f1:.6f}")
    info("Hash dos dados", data_hash[:16] + "...")
    info("Tempo total", format_seconds(elapsed))

    return training_metadata


if __name__ == "__main__":

    total_start = time.time()
    results = []

    title("TREINAMENTO DOS MODELOS DE LOTERIA")

    for lottery_type, config in LOTTERY_CONFIGS.items():

        model_filename = os.path.join(MODEL_DIR, f"{lottery_type}_model.pkl")

        try:
            result = train_model(
                file_path=config["FILE_PATH"],
                columns_prefix=config["CSV_COLUMNS_PREFIX"],
                max_number=config["MAX_NUMBER"],
                model_path=model_filename
            )

            results.append({
                "lottery": lottery_type,
                "status": "sucesso",
                "hamming_loss": result["hamming_loss"],
                "exact_match": result["exact_match"],
                "f1_score": result["f1_score"],
                "model_path": result["model_path"]
            })

        except Exception as exc:
            error(f"Falha ao treinar {lottery_type}: {exc}")

            results.append({
                "lottery": lottery_type,
                "status": "erro",
                "error": str(exc)
            })

    total_elapsed = time.time() - total_start

    title("RESUMO FINAL")

    for result in results:
        if result["status"] == "sucesso":
            success(result["lottery"].upper())
            info("Modelo", result["model_path"])
            info("Hamming Loss", f"{result['hamming_loss']:.6f}")
            info("Exact Match", f"{result['exact_match']:.6f}")
            info("F1 Score", f"{result['f1_score']:.6f}")
        else:
            error(result["lottery"].upper())
            info("Erro", result["error"])

        print()

    title("TODOS OS PROCESSOS FORAM FINALIZADOS")
    info("Tempo total geral", format_seconds(total_elapsed))
