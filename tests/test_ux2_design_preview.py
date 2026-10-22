"""Independent visual-proposal checks. No database or provider data is accessed."""
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'prototypes/ux2-design-preview'


def test_frozen_visual_specimens_and_bilingual_copy_contract():
    result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/browser/ux2-contract.test.js')],
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert re.search(r'pass\s+6\b', result.stdout)


def test_standalone_assets_have_restrictive_csp_and_no_inline_executable_content():
    class Assets(HTMLParser):
        def __init__(self):
            super().__init__(); self.resources = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'script':
                assert 'src' in attrs
                self.resources.append(attrs['src'])
            if tag == 'link':
                self.resources.append(attrs['href'])
            assert not any(key.startswith('on') for key in attrs)
    html = (UI / 'index.html').read_text()
    parser = Assets(); parser.feed(html)
    assert parser.resources == ['styles.css', 'preview.js']
    assert "connect-src 'none'" in html and "form-action 'none'" in html
    assert "script-src 'self'" in html and 'unsafe-inline' not in html
    assert all((UI / file).is_file() for file in parser.resources)


def test_preview_has_no_network_storage_backend_or_execution_integration():
    js = (UI / 'preview.js').read_text()
    for forbidden in ('fetch(', 'XMLHttpRequest', 'WebSocket', 'sendBeacon', 'localStorage', 'sessionStorage',
                      'indexedDB', 'serviceWorker', 'innerHTML', 'insertAdjacentHTML', 'eval(',
                      'family_os', '/api/', 'harness_context', 'TaskService', 'SessionService'):
        assert forbidden not in js, forbidden
    assert not re.search(r'\b(?:import|require)\s*\(?', js)
    css = (UI / 'styles.css').read_text()
    assert '@import' not in css and 'url(' not in css
    assert 'prefers-reduced-motion' in css and 'safe-area-inset-bottom' in css


TEXT_PAIRS = [('ink', 'canvas'), ('ink', 'surface'), ('muted', 'canvas'), ('muted', 'surface'),
              ('accent', 'accent-soft'), ('on-accent', 'accent'), ('amber', 'amber-bg'), ('risk', 'risk-bg')]


@pytest.mark.parametrize('theme', ['light', 'dark'])
@pytest.mark.parametrize('ink,paper', TEXT_PAIRS)
def test_proposed_text_roles_meet_aa_contrast(theme, ink, paper):
    css = (UI / 'styles.css').read_text()
    block = css.split(':root {' if theme == 'light' else ':root[data-theme="dark"] {')[1].split('}')[0]
    tokens = dict(re.findall(r'--([a-z-]+):\s*(#[0-9a-f]{6})', block))
    def light(value):
        rgb = [int(value[i:i+2], 16) / 255 for i in (1, 3, 5)]
        rgb = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in rgb]
        return sum(x * weight for x, weight in zip(rgb, (.2126, .7152, .0722)))
    a, b = sorted((light(tokens[ink]), light(tokens[paper])))
    assert (b + .05) / (a + .05) >= 4.5


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_control_boundary_and_focus_contrast(theme):
    css = (UI / 'styles.css').read_text()
    block = css.split(':root {' if theme == 'light' else ':root[data-theme="dark"] {')[1].split('}')[0]
    tokens = dict(re.findall(r'--([a-z-]+):\s*(#[0-9a-f]{6})', block))
    def light(value):
        rgb = [int(value[i:i+2], 16) / 255 for i in (1, 3, 5)]
        return sum((x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4) * w
                   for x, w in zip(rgb, (.2126, .7152, .0722)))
    for foreground, background in [('control', 'surface'), ('focus', 'canvas')]:
        a, b = sorted((light(tokens[foreground]), light(tokens[background])))
        assert (b + .05) / (a + .05) >= 3


@pytest.mark.parametrize('file,width', [
    *[(f'layout-before-{view}-1828.png', 1828) for view in ('calendar', 'security')],
    *[(f'layout-after-{view}-1828.png', 1828) for view in ('calendar', 'security')],
    *[(f'layout-after-{view}-1440.png', 1440) for view in ('a1', 'tasks')],
    *[(f'layout-after-{view}-390.png', 390) for view in ('a1', 'calendar', 'security', 'tasks')],
    ('layout-after-a1-320.png', 320),
    *[(f'{design}-home-{theme}-{width}.png', width)
      for design in ('a1', 'a2') for theme in ('light', 'dark') for width in (1440, 390, 320)],
    ('home-light-1440.png',1440), ('home-dark-1440.png',1440),
    ('home-light-390.png',390), ('home-dark-390.png',390), ('home-light-320.png',320),
    ('tasks-light-1440.png',1440), ('tasks-light-390.png',390),
    ('pending-light-1440.png',1440), ('pending-light-390.png',390),
    ('detail-zh-light-1440.png',1440), ('detail-zh-light-390.png',390), ('confirm-light-320.png',320),
])
def test_review_screenshots_are_present_at_declared_dimensions(file, width):
    data = (ROOT / 'docs/screenshots/ux2-calm-premium' / file).read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) > 10000
    assert struct.unpack('>II', data[16:24]) == (width, 1000 if width > 730 else 844)


def test_layout_renderer_refuses_implicit_execution_before_loading_browser_or_binding_port():
    result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/browser/ux2-layout.js')],
                            text=True, capture_output=True, timeout=30)
    assert result.returncode != 0
    assert 'Explicit synthetic opt-in required' in result.stderr
