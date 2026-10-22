"""UX1 offline fictional UI; standard-library/Node checks run in both CI jobs."""
from pathlib import Path
import re
import shutil
import subprocess
import pytest

ROOT=Path(__file__).parents[1]
UI=ROOT/'prototypes/h0-workbench'


def test_assignment_reuses_existing_model_safety_contract():
    result=subprocess.run([shutil.which('node'),str(ROOT/'tests/browser/ux1-model.test.js')],text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    assert re.search(r'pass\s+9',result.stdout)


def test_five_primary_destinations_and_quiet_query_paths_are_explicit():
    app=(UI/'app.js').read_text()
    assert "['information', 'offers'].includes(key) ? secondaryNav : primaryNav" in app
    assert "else if (!offersIntent)" in app
    assert 'p.offers' not in app.split("if (view === 'home') {")[1].split("} else if (view === 'tasks')")[0]
    assert "unavailable.disabled = true" in app


def test_responsive_keyboard_structure_is_local_and_not_a_new_runtime():
    css=(UI/'styles.css').read_text()
    for required in ('focus-visible','min-height:44px','repeat(5,minmax(0,1fr))','max-width:730px','prefers-reduced-motion','safe-area-inset-bottom'):
        assert required in css
    assert 'url(' not in css and '@import' not in css
    html=(UI/'index.html').read_text()
    assert 'connect-src' in html and "'none'" in html
    assert 'aria-live="polite"' in html and 'id="detail-dialog"' in html


@pytest.mark.parametrize('ink,paper',[('252a30','ffffff'),('555d67','ffffff'),('ffffff','244d42'),('795116','faf6ef'),('8f3234','f7eff0')])
def test_primary_text_palette_meets_aa_contrast(ink,paper):
    def light(hex):
        rgb=[int(hex[n:n+2],16)/255 for n in (0,2,4)]
        rgb=[c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4 for c in rgb]
        return sum(a*b for a,b in zip(rgb,(0.2126,0.7152,0.0722)))
    a,b=sorted((light(ink),light(paper)))
    assert (b+0.05)/(a+0.05)>=4.5


def test_mobile_secondary_tools_are_native_collapsible_not_a_new_state_model():
    html=(UI/'index.html').read_text()
    assert 'id="secondary-menu"' in html and 'id="secondary-body"' in html
    assert 'id="search-controls"' in html
    assert 'data-i18n="ux.more"' in html and 'data-i18n="ux.search"' in html
    app=(UI/'app.js').read_text()
    assert 'responsiveChrome' in app and 'menu.open = false' in app


PENDING_CASES = re.findall(r"test\('([^']+)'", (ROOT/'tests/browser/ux1-pending.test.js').read_text())


@pytest.mark.parametrize('case', PENDING_CASES)
def test_actor_scoped_pending_contract(case):
    result = subprocess.run([shutil.which('node'), '--test', '--test-name-pattern='+re.escape(case),
                             str(ROOT/'tests/browser/ux1-pending.test.js')],
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    assert re.search(r'pass\s+1\b', result.stdout)


def test_pending_ui_exposes_decisions_not_review_annotations():
    app = (UI/'app.js').read_text()
    assert "confirm('review'" not in app
    assert "confirm('needs-info'" not in app
    for op in ('accept', 'defer', 'archive', 'reopen'):
        assert f"confirm('{op}'" in app
    assert 'control.dataset.bucket = b' in app
    assert 'aria-pressed' in app
    assert 'review: tr(' not in app
