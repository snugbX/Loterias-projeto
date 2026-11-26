"""Fingerprint-checked public artifacts. HTTP requests never run simulations."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

import gerador_loterias as lottery

REPORT_PATH = Path(__file__).with_name('public_lottery_reports.json')
# Increment when the meaning of persisted statistics changes, even if CSVs do not.
RECIPE = 3


@lru_cache(maxsize=8)
def _fingerprint(path, modified_ns, size):
    # Line endings differ between GitHub/Linux and Windows checkouts.
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def fingerprint(lottery_type):
    path = Path(lottery.LOTTERY_CONFIGS[lottery_type]['FILE_PATH'])
    stat = path.stat()
    return _fingerprint(str(path), stat.st_mtime_ns, stat.st_size)


def read_bundle(path=None):
    path = Path(path or REPORT_PATH)
    stat = path.stat()
    return _read_bundle(str(path), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=2)
def _read_bundle(path, modified_ns, size):
    path = Path(path)
    if size > 2_000_000:
        raise ValueError('Relatório público acima do limite.')
    def invalid_constant(value):
        raise ValueError('Valor não finito no relatório.')
    bundle = json.loads(path.read_text(encoding='utf-8'), parse_constant=invalid_constant)
    if set(bundle) != {'schema', 'recipe', 'generated_at', 'reports'} or bundle['schema'] != 1 or bundle['recipe'] != RECIPE:
        raise ValueError('Formato de relatório inválido.')
    if set(bundle['reports']) != set(lottery.LOTTERY_CONFIGS):
        raise ValueError('Modalidades incompletas no relatório.')
    for kind, report in bundle['reports'].items():
        if set(report) != {'fingerprint', 'coverage', 'audit', 'validation', 'months_validation', 'intervals', 'digest'}:
            raise ValueError('Campos não permitidos no relatório.')
        if not re.fullmatch('[0-9a-f]{64}', report['fingerprint']):
            raise ValueError('Identificador da base inválido.')
        maximum = lottery.LOTTERY_CONFIGS[kind]['MAX_NUMBER']
        audit = report['audit']
        if set(audit) != {'method', 'family_size', 'alpha', 'significant_pairs', 'q_values', 'stable_positive', 'resamples', 'seed', 'global_statistic', 'global_p_value', 'minimum_p_resolution', 'note', 'strategies'}:
            raise ValueError('Campos de auditoria inválidos.')
        for field in ('q_values', 'stable_positive'):
            matrix = audit[field]
            if len(matrix) != maximum or any(len(row) != maximum for row in matrix):
                raise ValueError('Dimensões da auditoria inválidas.')
        if any(type(q) not in (int, float) or not 0 <= q <= 1 for row in audit['q_values'] for q in row):
            raise ValueError('Probabilidade inválida na auditoria.')
        if any(type(value) is not bool for row in audit['stable_positive'] for value in row):
            raise ValueError('Indicador de estabilidade inválido.')
    return bundle


def get_report(lottery_type):
    try:
        bundle = read_bundle()
        report = bundle['reports'][lottery_type]
        if report['fingerprint'] != fingerprint(lottery_type):
            return {'status': 'pending', 'message': 'A base mudou; aguardando o relatório correspondente.'}
        return {'status': 'current', 'generated_at': bundle['generated_at'], 'report': report}
    except (OSError, ValueError, KeyError, TypeError):
        return {'status': 'unavailable', 'message': 'Relatório ainda indisponível. As análises descritivas continuam disponíveis.'}


def get_digests():
    results = {}
    for kind in lottery.LOTTERY_CONFIGS:
        result = get_report(kind)
        digest = result.get('report', {}).get('digest')
        results[kind] = {'status': 'current', 'digest': digest} if result['status'] == 'current' and digest else {
            'status': 'pending', 'message': 'Boletim aguardando processamento para a base atual.'}
    return results
