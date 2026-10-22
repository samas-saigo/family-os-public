"""I4b-only presentation guards; no real data, providers or runtime database."""
from pathlib import Path
import re
import shutil
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / 'prototypes/i3-workbench/connected.css'


def foundation():
    return CSS.read_text().split('/* UX2 Connected UI Foundation.')[1]


def test_every_foundation_rule_is_scoped_to_i4b_not_shared_i3_i4a_or_offline_ui():
    css = re.sub(r'/\*.*?\*/', '', '/* UX2 Connected UI Foundation.' + foundation(), flags=re.S)
    for selector in re.findall(r'([^{}]+)\{', css):
        selector = selector.strip()
        if selector.startswith('@media'):
            continue
        assert all(part.strip().startswith('html[data-connection="i4b"]') for part in selector.split(',')), selector
    assert '@import' not in css and 'url(' not in css


def test_connected_browser_renderer_requires_explicit_opt_in_before_starting_service():
    result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/browser/ux2-connected.js')],
                            text=True, capture_output=True, timeout=30)
    assert result.returncode != 0
    assert 'Exact synthetic opt-in required' in result.stderr


def tokens(theme):
    selector = 'html[data-connection="i4b"]' + ('[data-theme="dark"]' if theme == 'dark' else '') + ' {'
    return dict(re.findall(r'--([a-z-]+):\s*(#[0-9a-f]{6})', CSS.read_text().split(selector)[1].split('}')[0]))


def contrast(first, second):
    def luminance(value):
        channels = [int(value[i:i+2], 16) / 255 for i in (1, 3, 5)]
        return sum((x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4) * w
                   for x, w in zip(channels, (.2126, .7152, .0722)))
    low, high = sorted((luminance(first), luminance(second)))
    return (high + .05) / (low + .05)


@pytest.mark.parametrize('theme', ['light', 'dark'])
@pytest.mark.parametrize('ink,paper', [('ink', 'paper'), ('muted', 'paper'), ('ink', 'surface'),
    ('primary-on', 'primary-fill'), ('amber', 'warning-bg'), ('red', 'badge-red-bg'),
    ('disabled-ink', 'control-bg')])
def test_connected_text_roles_have_aa_contrast(theme, ink, paper):
    palette = tokens(theme)
    assert contrast(palette[ink], palette[paper]) >= 4.5


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_connected_control_and_focus_roles_are_distinct(theme):
    palette = tokens(theme)
    for foreground, background in [('control-border', 'surface'), ('focus', 'paper')]:
        assert contrast(palette[foreground], palette[background]) >= 3


SCREENSHOTS = [
    'before-tasks-1440', 'before-detail-1440', 'before-tasks-390',
    *[f'tasks-{peer}-{lang}-{theme}-{width}'
      for peer, lang in [('clara', 'zh'), ('devon', 'en')]
      for theme in ('light', 'dark') for width in (1440, 390, 320)],
    *[f'{state}-{peer}-{lang}-{theme}-{width}'
      for state, widths in [('detail', (1440, 320)), ('confirm', (1440, 390))]
      for peer, lang, theme in [('clara', 'zh', 'light'), ('devon', 'en', 'dark')]
      for width in widths],
    'pending-clara-zh-light-1440', 'pending-clara-zh-light-390',
]


@pytest.mark.parametrize('name', SCREENSHOTS)
def test_connected_browser_screenshots_are_present_at_declared_dimensions(name):
    data = (ROOT / 'docs/screenshots/ux2-connected-foundation' / (name + '.png')).read_bytes()
    width = int(name.rsplit('-', 1)[1])
    assert data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) > 10000
    assert struct.unpack('>II', data[16:24]) == (width, 1000 if width > 730 else 844)
