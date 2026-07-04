import argparse
import datetime
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GIT_SAFE_DIRECTORY = PROJECT_ROOT.as_posix()


def git_command(args):
    return [
        "git",
        "-c",
        f"safe.directory={GIT_SAFE_DIRECTORY}",
        *args,
    ]


def run_git(args, check=True):
    completed = subprocess.run(
        git_command(args),
        cwd=PROJECT_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    if check and completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(message or f"Git falhou: {' '.join(args)}")

    return completed


def normalize_paths(paths):
    normalized = []

    for raw_path in paths:
        path = Path(raw_path)

        if not path.is_absolute():
            path = PROJECT_ROOT / path

        path = path.resolve()

        try:
            path.relative_to(PROJECT_ROOT)
        except ValueError as exc:
            raise ValueError(f"Arquivo fora do projeto: {path}") from exc

        if not path.exists():
            raise FileNotFoundError(f"Arquivo nao encontrado: {path}")

        normalized.append(path.relative_to(PROJECT_ROOT).as_posix())

    return normalized


def current_branch():
    completed = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    branch = completed.stdout.strip()

    if not branch or branch == "HEAD":
        raise RuntimeError("Nao foi possivel identificar a branch atual.")

    return branch


def has_remote():
    completed = run_git(["remote"], check=False)
    remotes = completed.stdout.split()
    return "origin" in remotes


def staged_changes(paths):
    completed = run_git(["diff", "--cached", "--name-only", "--", *paths])
    return [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip()
    ]


def status_for_paths(paths):
    completed = run_git(["status", "--short", "--", *paths], check=False)
    return completed.stdout.strip()


def publish(paths, message, dry_run=False):
    normalized_paths = normalize_paths(paths)

    if not normalized_paths:
        print("Nenhum arquivo informado para publicar.")
        return 0

    if dry_run:
        print("Simulacao de publicacao no GitHub.")
        status = status_for_paths(normalized_paths)
        print(status or "Nenhuma alteracao detectada nos arquivos informados.")
        return 0

    if not has_remote():
        raise RuntimeError("Remote 'origin' nao encontrado. Configure o GitHub antes de publicar.")

    branch = current_branch()
    print("Preparando arquivos para GitHub:")

    for path in normalized_paths:
        print(f" - {path}")

    run_git(["add", "--", *normalized_paths])
    changed_files = staged_changes(normalized_paths)

    if not changed_files:
        print("Nenhuma mudanca nova para commitar.")
        return 0

    run_git(["commit", "-m", message])
    run_git(["push", "origin", branch])
    print(f"Atualizacao enviada para origin/{branch}.")
    return 0


def parse_args(argv):
    default_message = (
        "Atualiza dados das loterias "
        f"{datetime.date.today().isoformat()}"
    )
    parser = argparse.ArgumentParser(
        description="Publica no GitHub os CSVs de loterias atualizados.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Arquivos CSV atualizados que devem entrar no commit.",
    )
    parser.add_argument(
        "--message",
        default=default_message,
        help="Mensagem do commit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria publicado, sem stage, commit ou push.",
    )

    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])

    try:
        return publish(args.paths, args.message, dry_run=args.dry_run)
    except Exception as exc:
        print(f"Erro ao publicar no GitHub: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
