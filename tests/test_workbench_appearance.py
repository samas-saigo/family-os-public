"""Contrast of actual offline CSS tokens; no providers, database or real data."""
from pathlib import Path
import re
import pytest

CSS = (Path(__file__).parents[1] / 'prototypes/h0-workbench/styles.css').read_text()
THEME = CSS.split('/* Appearance: visual tokens only.', 1)[1]


def palette(mode):
    selector = r':root\{' if mode == 'light' else r':root\[data-theme="dark"\]\{'
    block = re.search(selector + r'(.*?)\}', THEME, re.S).group(1)
    return dict(re.findall(r'--([\w-]+):#([0-9a-f]{6});', block))


def luminance(color):
    rgb = [int(color[i:i+2], 16) / 255 for i in (0, 2, 4)]
    linear = [x/12.92 if x <= .04045 else ((x+.055)/1.055)**2.4 for x in rgb]
    return sum(x*w for x, w in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    low, high = sorted((luminance(a), luminance(b)))
    return (high+.05)/(low+.05)


TEXT_PAIRS = [
    ('ink', 'paper'), ('muted', 'paper'), ('ink', 'surface'), ('muted', 'surface'),
    ('ink', 'control-bg'), ('muted', 'control-bg'),
    ('primary-on', 'primary-fill'), ('primary-on', 'primary-hover'), ('primary-on', 'primary-active'),
    ('badge-ink', 'green-soft'), ('amber', 'badge-amber-bg'), ('badge-red-ink', 'badge-red-bg'),
    ('blue', 'badge-blue-bg'), ('note-ink', 'control-bg'), ('amber', 'warning-bg'),
    ('count-ink', 'hover-bg'), ('ink', 'pending-active-bg'), ('green', 'date-bg'),
    ('placeholder', 'surface'), ('disabled-ink', 'control-bg'),
]


@pytest.mark.parametrize('mode', ['light', 'dark'])
@pytest.mark.parametrize('foreground,background', TEXT_PAIRS)
def test_appearance_normal_text_meets_wcag_aa(mode, foreground, background):
    colors = palette(mode)
    assert contrast(colors[foreground], colors[background]) >= 4.5


@pytest.mark.parametrize('mode', ['light', 'dark'])
@pytest.mark.parametrize('foreground,background', [
    ('focus', 'paper'), ('control-border', 'control-bg'),
    ('hover-border', 'hover-bg'), ('active-border', 'active-bg'),
])
def test_appearance_focus_and_control_boundaries_meet_nontext_contrast(mode, foreground, background):
    colors = palette(mode)
    assert contrast(colors[foreground], colors[background]) >= 3


def test_initial_system_dark_palette_matches_the_explicit_dark_palette():
    fallback = re.search(r':root:not\(\[data-theme\]\)\{(.*?)\}', THEME, re.S).group(1)
    assert dict(re.findall(r'--([\w-]+):#([0-9a-f]{6});', fallback)) == palette('dark')
