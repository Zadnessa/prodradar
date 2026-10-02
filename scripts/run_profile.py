"""Запуск проверки, аудита или сборщика с явным профилем test/prod."""

import argparse
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime_profiles import select_profile, verify_bot

COMMANDS = {
    "check": "scripts/check_environment.py",
    "prepare-github": "scripts/prepare_test_github.py",
    "configure-github": "scripts/configure_test_github.py",
    "audit": "scripts/audit_sources.py",
    "collect": "scripts/collect_test.py",
    "pool": "scripts/capture_role_pool.py",
    "prepare-roles": "scripts/prepare_role_pool.py",
    "collect-prod": "main.py",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, choices=("test", "prod"))
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if (args.command in ("collect", "pool", "prepare-roles", "prepare-github", "configure-github") and args.profile != "test") or (
        args.command == "collect-prod" and args.profile != "prod"
    ):
        parser.error("Команда сбора не соответствует профилю")
    try:
        profile = select_profile(args.profile)
        import os
        if args.command == "pool":
            os.environ["RADAR_SOURCE_POOL_ONLY"] = "1"
        if "--use-source-pool" in args.arguments:
            os.environ["RADAR_USE_SOURCE_POOL"] = "1"
        verify_bot(profile)
    except Exception as exc:
        # Не печатаем исключения клиентов, которые могут содержать секретные URL.
        print(f"Запуск остановлен до выполнения команды: {type(exc).__name__}", file=sys.stderr)
        return 1
    arguments = args.arguments
    if args.command == "check":
        arguments = [*arguments, "--expected-bot", profile["bot"]]
    sys.argv = [str(ROOT / COMMANDS[args.command]), *arguments]
    runpy.run_path(sys.argv[0], run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
