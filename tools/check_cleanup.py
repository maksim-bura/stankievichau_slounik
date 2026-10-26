"""Run the post-change verification and cleanup steps for a cleanup pass.

Run: py -3 tools/check_cleanup.py
     py -3 tools/check_cleanup.py --probes "%TEMP%/opencode" --clean --status
     py -3 tools/check_cleanup.py --step "baseline::py -3 check_baseline.py"

Built-in steps run only when their target exists: compileall and unused imports.
Extra checks are passed with --step. Probe files accept the repo's PySide
offscreen shutdown codes when they still print a pass marker.
"""
import argparse
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

PASS_MARKERS = ('ALL CHECKS PASSED', 'FAILED: none')
SKIP_DIRS = {'.git', '__pycache__', '.venv', 'venv', 'build', 'dist', 'node_modules'}
CLEAN_GLOBS = ('**/*.pyc', '**/*.pyo', '**/*.orig', '**/*.rej', '**/*.bak')


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--packages', default='')
    parser.add_argument('--probes', default=None)
    parser.add_argument('--step', action='append', default=[])
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--clean', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--scratch', action='append', default=[])
    parser.add_argument('--status', action='store_true')
    return parser.parse_args()


def tail(text, count=25):
    lines = text.strip().splitlines()
    return '\n'.join(lines[-count:])


def run(command, cwd, timeout, env=None):
    started = time.time()
    try:
        result = subprocess.run(command, cwd=str(cwd), capture_output=True,
                                text=True, timeout=timeout, env=env)
        output = (result.stdout or '') + (result.stderr or '')
        return result.returncode, output, time.time() - started
    except FileNotFoundError as exc:
        return 127, str(exc), time.time() - started
    except subprocess.TimeoutExpired:
        return 124, 'timeout after %ds' % timeout, time.time() - started


def resolve_packages(root, value):
    if value:
        candidates = [item.strip() for item in value.split(',') if item.strip()]
    else:
        candidates = [path.name for path in root.iterdir()
                      if path.is_dir() and (path / '__init__.py').exists()]
    return [name for name in candidates if (root / name).exists()]


def builtin_steps(root, packages):
    steps = []
    if packages:
        steps.append({
            'label': 'compileall',
            'command': [sys.executable, '-m', 'compileall', '-q'] + packages,
        })
    unused = Path(__file__).resolve().with_name('find_unused_imports.py')
    if unused.exists():
        steps.append({'label': 'unused imports',
                      'command': [sys.executable, str(unused), '.']})
    return steps


def parse_step(value):
    label, separator, command = value.partition('::')
    if not separator:
        raise SystemExit('--step must look like "label::command"')
    return {'label': label, 'command': shlex.split(command)}


def probe_files(folder):
    return sorted(Path(folder).glob('probe_*.py'))


def check_output(step, code, output):
    if step.get('expect'):
        return step['expect'] in output
    if code == 0:
        return True
    return any(marker in output for marker in PASS_MARKERS)


def clean(root, dry_run, scratch):
    removed = []
    for pattern in CLEAN_GLOBS:
        for path in root.glob(pattern):
            if SKIP_DIRS & set(path.relative_to(root).parts[:-1]):
                continue
            removed.append(str(path.relative_to(root)))
            if not dry_run:
                path.unlink(missing_ok=True)
    for path in sorted(root.rglob('__pycache__')):
        if not path.is_dir():
            continue
        if any(part in {'.venv', 'venv', 'node_modules'} for part in path.parts):
            continue
        removed.append(str(path.relative_to(root)) + '/')
        if not dry_run:
            shutil.rmtree(path, ignore_errors=True)
    for item in scratch:
        target = Path(item)
        if not target.is_absolute():
            target = root / item
        if not target.exists():
            continue
        removed.append(str(target))
        if dry_run:
            continue
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)
    return removed


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    packages = resolve_packages(root, args.packages)
    steps = builtin_steps(root, packages) + [parse_step(item) for item in args.step]
    environment = dict(os.environ)
    environment.setdefault('PYTHONUTF8', '1')
    environment.setdefault('QT_QPA_PLATFORM', 'offscreen')

    results = []
    for step in steps:
        code, output, elapsed = run(step['command'], root, args.timeout, environment)
        ok = check_output(step, code, output)
        results.append((step['label'], ok, code, elapsed, output))
        print('%s %-22s exit %-12s %5.1fs' % (
            'PASS' if ok else 'FAIL', step['label'], code, elapsed))
        if not ok:
            print(tail(output))

    if args.probes:
        for path in probe_files(args.probes):
            code, output, elapsed = run([sys.executable, str(path)], root,
                                        args.timeout, environment)
            ok = code == 0 or any(marker in output for marker in PASS_MARKERS)
            results.append((path.name, ok, code, elapsed, output))
            print('%s %-22s exit %-12s %5.1fs' % (
                'PASS' if ok else 'FAIL', path.name, code, elapsed))
            if not ok:
                print(tail(output))

    if args.clean:
        removed = clean(root, args.dry_run, args.scratch)
        print('\nclean: %d artifact(s)%s' % (
            len(removed), ' (dry run)' if args.dry_run else ''))
        for item in removed[:40]:
            print('  - %s' % item)
        if len(removed) > 40:
            print('  ... %d more' % (len(removed) - 40))

    if args.status:
        code, output, _elapsed = run(
            ['git', 'status', '--porcelain', '--untracked-files=all'], root,
            args.timeout)
        print('\ngit status:')
        print(output.rstrip() or '  (clean)')

    failures = [label for label, ok, _code, _elapsed, _output in results if not ok]
    print()
    if failures:
        print('%d FAILURE(S): %s' % (len(failures), ', '.join(failures)))
        return 1
    print('ALL STEPS PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
