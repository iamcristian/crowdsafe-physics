"""Generated results must not replace the maintained project landing page."""
from pathlib import Path
import shutil

from src.reporting import write_reports


def test_reporting_preserves_curated_readme(tmp_path):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / 'README.md').write_text('Curated project instructions\n', encoding='utf-8')
    shutil.copy(root / 'MATH_AND_PHYSICS_TUTORIAL.md', tmp_path)
    shutil.copytree(root / 'src', tmp_path / 'src', ignore=shutil.ignore_patterns('__pycache__'))
    reports = write_reports(output=root / 'outputs', repository=tmp_path)
    assert (tmp_path / 'README.md').read_text(encoding='utf-8') == 'Curated project instructions\n'
    assert Path(reports[0]).name == 'BENCHMARK_REPORT.md'
    assert 'Peak pair pressure' in Path(reports[0]).read_text(encoding='utf-8')
