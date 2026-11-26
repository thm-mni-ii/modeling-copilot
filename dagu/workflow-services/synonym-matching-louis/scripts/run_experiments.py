"""Bisherigen JSON-Baukasten getrennt vom ausgewählten Servicekern ausführen."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT/'experiments'


def main():
    modules = {p.stem for p in (EXPERIMENTS/'research').glob('*.py') if p.stem != '__init__'}
    scripts = {'download_models', 'download_lexicons'}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=sorted(modules | scripts | {'tests', 'cli'}))
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    # Relative Cache-/Ergebnispfade des bisherigen Codes bleiben verwendbar.
    # Links zeigen auf die vorhandenen Daten, nicht auf eine zweite Modellkopie.
    for name in ('.cache', 'results'):
        target, link = ROOT/name, EXPERIMENTS/name
        target.mkdir(exist_ok=True)
        if not link.exists() and not link.is_symlink():
            link.symlink_to(Path('..')/name, target_is_directory=True)
        if link.is_symlink() and link.resolve() != target.resolve():
            raise ValueError(f'{link} points to a different resource directory')
    if args.command == 'tests':
        command = ['-m', 'pytest', '-c', 'pytest.ini', 'tests']
    elif args.command == 'cli':
        command = ['src/main.py']
    elif args.command in scripts:
        command = [f'scripts/{args.command}.py']
    else:
        command = ['-m', f'research.{args.command}']
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(EXPERIMENTS/'src'), str(EXPERIMENTS)]),
           'PYTHONDONTWRITEBYTECODE': '1'}
    # Ein eigener Prozess verhindert Kollisionen gleichnamiger alter/neuer Module.
    return subprocess.run([sys.executable, *command, *args.arguments], cwd=EXPERIMENTS, env=env).returncode


if __name__ == '__main__':
    sys.exit(main())
