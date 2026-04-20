import subprocess
import sys
from pathlib import Path
import pytest

REPO = Path(__file__).parent.parent
PY = sys.executable

# Test CLI entry points for tex_watch.py
def test_once_runs():
    if not (REPO / 'CV_Marion_Holvoet.tex').exists():
        pytest.skip('CV_Marion_Holvoet.tex not found')
    result = subprocess.run([PY, str(REPO / 'tex_watch.py'), '--once'], capture_output=True, text=True)
    if '[OK]' not in result.stdout or result.returncode != 0:
        print('STDOUT:', result.stdout)
        print('STDERR:', result.stderr)
    assert '[OK]' in result.stdout
    assert result.returncode == 0

def test_translate_runs():
    if not (REPO / 'CV_Marion_Holvoet.tex').exists():
        pytest.skip('CV_Marion_Holvoet.tex not found')
    result = subprocess.run([PY, str(REPO / 'tex_watch.py'), '--translate'], capture_output=True, text=True)
    if '[OK]' not in result.stdout or result.returncode != 0:
        print('STDOUT:', result.stdout)
        print('STDERR:', result.stderr)
    assert '[OK]' in result.stdout
    assert result.returncode == 0

def test_translate_force_runs():
    if not (REPO / 'CV_Marion_Holvoet.tex').exists():
        pytest.skip('CV_Marion_Holvoet.tex not found')
    result = subprocess.run([PY, str(REPO / 'tex_watch.py'), '--translate-force'], capture_output=True, text=True)
    if '[OK]' not in result.stdout or result.returncode != 0:
        print('STDOUT:', result.stdout)
        print('STDERR:', result.stderr)
    assert '[OK]' in result.stdout
    assert result.returncode == 0
