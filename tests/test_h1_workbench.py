"""H1 fictional bilingual presentation checks; no database/provider access."""
from pathlib import Path
import re
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / 'prototypes/h0-workbench'


def test_bilingual_javascript_contracts():
    node = shutil.which('node')
    assert node, 'Node >=18 required for developer tests only'
    result = subprocess.run([node, str(ROOT / 'tests/browser/h1-i18n.test.js')],
                            cwd=ROOT, text=True, encoding='utf-8', capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert re.search(r'pass\s+30', result.stdout), result.stdout


@pytest.mark.parametrize('filename,allowed', [
    ('translations.js', []), ('i18n.js', ["'./translations.js'"]),
    ('presentation.js', ["'./i18n.js'"]),
])
def test_new_localization_modules_have_only_local_presentation_dependencies(filename, allowed):
    text = (PROTOTYPE / filename).read_text(encoding='utf-8')
    assert re.findall(r'require\(([^)]+)\)', text) == allowed
    for forbidden in ['fetch(', 'XMLHttpRequest', 'WebSocket', 'sendBeacon',
                      'serviceWorker', 'localStorage', 'sessionStorage', 'indexedDB',
                      'innerHTML', 'insertAdjacentHTML', 'eval(', 'new Function',
                      'family_os', 'sqlalchemy', 'keyring', 'oauth', 'Ollama']:
        assert forbidden not in text, (filename, forbidden)
    assert not re.search(r'\bimport\b', text)


def test_index_defaults_to_chinese_and_labels_language_without_persistence():
    html = (PROTOTYPE / 'index.html').read_text(encoding='utf-8')
    assert '<html lang="zh-CN">' in html
    assert 'id="language"' in html
    assert '<option value="zh-CN">简体中文</option>' in html
    assert '<option value="en-US">English</option>' in html
    assert '不是身份认证' in html
    app = (PROTOTYPE / 'app.js').read_text(encoding='utf-8')
    assert 'document.documentElement.lang = locale()' in app
    assert "if (dialog.open) closeModal()" in app
