from pathlib import Path


ROOT = Path(__file__).resolve().parent / 'fixtures' / 'source_baselines'


def read_source_baseline(revision, path):
    return (ROOT / revision / f'{path}.txt').read_text(encoding='utf-8')
