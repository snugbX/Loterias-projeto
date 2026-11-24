"""Generate reproducible public reports offline, without database credentials."""

import argparse
from datetime import datetime, timezone
import json

import game_analysis
import gerador_loterias as lottery
import pattern_radar
import public_reports
from statistical_audit import audit_draws, draw_intervals
from build_draw_digest import build_digest


def build_reports(resamples=199, seed=1729):
    reports = {}
    for kind in lottery.LOTTERY_CONFIGS:
        before = public_reports.fingerprint(kind)
        draws, skipped, stat = game_analysis.load_validated_history(kind)
        radar = pattern_radar.build_radar_from_draws(kind, draws, skipped, stat.st_mtime_ns)
        reports[kind] = {'fingerprint': before, 'coverage': radar['coverage'],
                         'audit': audit_draws(kind, draws, resamples, seed), 'validation': radar['validation'],
                         'months_validation': radar['months']['validation'] if radar['months'] else None,
                         'intervals': draw_intervals(kind, draws), 'digest': build_digest(kind, draws, skipped)}
        if before != public_reports.fingerprint(kind):
            raise RuntimeError('A base mudou durante o processamento. Nenhum relatório foi publicado.')
    return {'schema': 1, 'recipe': public_reports.RECIPE, 'generated_at': datetime.now(timezone.utc).isoformat(), 'reports': reports}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Gera relatórios públicos de validação estatística.')
    parser.add_argument('--resamples', type=int, default=199)
    parser.add_argument('--seed', type=int, default=1729)
    args = parser.parse_args(argv)
    # Do not create timestamp-only commits when the validated source did not change.
    try:
        previous = public_reports.read_bundle()
        if all(previous['reports'][kind]['fingerprint'] == public_reports.fingerprint(kind)
               and previous['reports'][kind]['digest'] is not None
               and previous['reports'][kind]['audit']['resamples'] == args.resamples
               and previous['reports'][kind]['audit']['seed'] == args.seed for kind in lottery.LOTTERY_CONFIGS):
            print('Relatórios já correspondem às bases atuais.')
            return 0
    except (OSError, ValueError, KeyError, TypeError):
        pass
    bundle = build_reports(args.resamples, args.seed)
    temporary = public_reports.REPORT_PATH.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(bundle, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n', encoding='utf-8')
    public_reports.read_bundle(temporary)
    temporary.replace(public_reports.REPORT_PATH)
    print('Relatórios públicos atualizados para as quatro loterias.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
