"""按精确节点隔离 Screening，其余 DOE GUI 文件逐进程串行验收。"""
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
files = sorted(ROOT.glob('tests/test_doe*gui.py'))
screening = ROOT / 'tests/test_doe_screening_gui.py'
collected = subprocess.run(
    [sys.executable, '-m', 'pytest', '--collect-only', '-q', str(screening)],
    cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace',
)
(OUT / 'final-screening-collection.log').write_text(collected.stdout + collected.stderr, encoding='utf-8')
assert collected.returncode == 0, collected.stderr
nodes = [line.strip() for line in collected.stdout.splitlines() if line.startswith('tests/') and '::' in line]
assert nodes and len(nodes) == len(set(nodes))
# 精确节点每20项一组，避免数字子串过滤导致参数化用例重复。
groups = [(p.stem, [p.relative_to(ROOT).as_posix()]) for p in files if p != screening]
groups += [(f'screening-{i // 20:02}', nodes[i:i + 20]) for i in range(0, len(nodes), 20)]
manifest = {'screening_nodes': nodes, 'groups': []}
for name, args in groups:
    xml = OUT / f'final-gui-{name}.xml'
    log = OUT / f'final-gui-{name}.log'
    command = [sys.executable, '-m', 'pytest', *args, '-q', '--tb=short', f'--junitxml={xml}']
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    record = {'name': name, 'args': args, 'returncode': result.returncode, 'log': log.name, 'xml': xml.name}
    if xml.exists():
        suites = ET.parse(xml).getroot().iter('testsuite')
        record['counts'] = {key: 0 for key in ('tests', 'failures', 'errors', 'skipped')}
        for suite in suites:
            for key in record['counts']:
                record['counts'][key] += int(suite.get(key, 0))
    manifest['groups'].append(record)
    (OUT / 'final-gui-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(name, result.returncode, record.get('counts'), flush=True)
    if result.returncode:
        sys.exit(result.returncode)
assert set(nodes) == {node for name, args in groups if name.startswith('screening-') for node in args}
