"""Static isolation checks plus the real JS interaction model; fictional files only."""
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / 'prototypes' / 'h0-workbench'


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_h0_javascript_behavior_regressions():
    # Both existing Ubuntu CI jobs provide Node. No npm install/build is required.
    node = shutil.which('node')
    assert node, 'Node >=18 is required for H0 developer model tests, not to open the demo'
    result = subprocess.run([node, str(ROOT / 'tests/browser/h0-model.test.js')],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert re.search(r'(?:pass\s+31|# pass 31)', result.stdout), result.stdout
    assert re.search(r'(?:fail\s+0|# fail 0)', result.stdout), result.stdout


def test_entry_point_has_only_local_resources_and_no_forms_or_embeds():
    html = (PROTOTYPE / 'index.html').read_text()
    elements = Elements(html).elements
    resources = [(tag, attrs.get('src') or attrs.get('href'))
                 for tag, attrs in elements if 'src' in attrs or 'href' in attrs]
    assert resources == [('link', 'styles.css'), ('script', 'fixtures.js'),
                         ('script', 'translations.js'), ('script', 'i18n.js'), ('script', 'model.js'),
                         ('script', 'presentation.js'), ('script', 'app.js'), ('a', '#main')]
    assert not set(tag for tag, _ in elements) & {'iframe', 'object', 'embed', 'form', 'base'}
    assert not any(attrs.get('type') == 'file' for _, attrs in elements)
    for _, resource in resources[:-1]:
        assert (PROTOTYPE / resource).is_file()


def test_entry_point_csp_blocks_connections_and_inline_execution():
    policies = [attrs['content'] for tag, attrs in Elements((PROTOTYPE / 'index.html').read_text()).elements
                if tag == 'meta' and attrs.get('http-equiv') == 'Content-Security-Policy']
    assert len(policies) == 1
    policy = policies[0]
    for required in ["default-src 'none'", "script-src 'self'", "style-src 'self'",
                     "connect-src 'none'", "object-src 'none'", "base-uri 'none'", "form-action 'none'"]:
        assert required in policy
    assert 'unsafe-inline' not in policy and 'unsafe-eval' not in policy


@pytest.mark.parametrize('filename', ['app.js', 'model.js', 'fixtures.js'])
def test_no_network_persistence_provider_or_executable_display_paths(filename):
    text = (PROTOTYPE / filename).read_text()
    for forbidden in ['fetch', 'XMLHttpRequest', 'WebSocket', 'EventSource', 'sendBeacon',
                      'serviceWorker', 'localStorage', 'sessionStorage', 'indexedDB',
                      'document.cookie', 'innerHTML', 'outerHTML', 'insertAdjacentHTML',
                      'eval(', 'new Function', 'location.href', 'window.open',
                      'family_os', 'sqlalchemy', 'keyring', 'oauth', 'Ollama',
                      'Development', 'Holdout', 'ID_token', 'refresh_token']:
        assert forbidden not in text, (filename, forbidden)
    imports = re.findall(r'require\(([^)]+)\)', text)
    assert imports == (["'./fixtures.js'"] if filename == 'model.js' else [])
    assert not re.search(r'\bimport\b', text)


def test_local_styles_and_accessible_structure():
    css = (PROTOTYPE / 'styles.css').read_text()
    assert '@import' not in css and 'url(' not in css
    assert 'focus-visible' in css and '@media' in css
    html = (PROTOTYPE / 'index.html').read_text()
    assert '离线演示 · 虚构数据 · 无真实操作' in html
    assert '不是身份认证' in html
    assert 'aria-live="polite"' in html and '<dialog' in html
    elements = Elements(html).elements
    assert any(tag == 'nav' and attrs.get('aria-label') for tag, attrs in elements)
    assert any(tag == 'main' for tag, _ in elements)
    assert not any(any(key.startswith('on') for key in attrs) for _, attrs in elements)


def test_fiction_is_dedicated_and_not_loaded_from_any_corpus():
    text = (PROTOTYPE / 'fixtures.js').read_text()
    assert 'Newly authored H0 fiction' in text and '2031-04-14' in text
    assert 'Linden' in text and 'Nora' in text and 'Julian' in text
    assert '.example.invalid' in text
    assert not re.search(r'https?://|[\w.+-]+@[\w.-]+\.[A-Za-z]+', text)
    assert not re.search(r'\b(?:require|import|fetch|readFile)\s*\(', text)
