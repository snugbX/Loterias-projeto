import gerador_loterias


def normalize_lottery_type(lottery_type):
    normalized = lottery_type.strip().lower()

    if normalized not in gerador_loterias.LOTTERY_CONFIGS:
        gerador_loterias.logging.warning(
            f"Tipo de loteria inválido recebido: {lottery_type}"
        )
        return None

    return normalized
