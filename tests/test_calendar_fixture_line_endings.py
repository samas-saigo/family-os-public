"""Exercise actual Git checkout conversion without reading other datasets."""

import hashlib
import os
from pathlib import Path
import subprocess

import pytest

from family_os import calendar_evidence_evaluation as evaluator
from family_os.calendar_action_evidence import CalendarEvidenceError


ROOT = Path(__file__).resolve().parents[1]
PATHS = tuple(evaluator.FILES)


def git(repo, *args):
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(
        ["git", "-C", str(repo), *args], env=env, check=True,
        capture_output=True, text=True,
    ).stdout


def repository(tmp_path, autocrlf, *, attributes=True):
    repo = tmp_path / "checkout"
    repo.mkdir()
    git(repo, "-c", "init.templateDir=", "init")
    git(repo, "config", "core.autocrlf", autocrlf)
    git(repo, "config", "core.safecrlf", "false")
    git(repo, "config", "core.attributesFile", os.devnull)
    for name in PATHS:
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    (repo / "control.txt").write_bytes(b"synthetic control\nsecond line\n")
    if attributes:
        (repo / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
        git(repo, "add", "--", ".gitattributes")
    git(repo, "add", "--", *PATHS, "control.txt")
    git(repo, "-c", "user.name=Synthetic checkout test", "-c",
        "user.email=synthetic@example.invalid", "-c", "commit.gpgsign=false",
        "commit", "-m", "Synthetic checkout inputs")
    return repo


def recheckout(repo, paths):
    # Git may skip stat-clean files even with checkout-index --force.
    for name in paths:
        (repo / name).unlink()
    git(repo, "checkout-index", "--index", "--force", "--", *paths)


@pytest.mark.parametrize("autocrlf", ["true", "input", "false"])
def test_checkout_preserves_pinned_lf_bytes(tmp_path, monkeypatch, autocrlf):
    repo = repository(tmp_path, autocrlf)
    recheckout(repo, (*PATHS, "control.txt"))
    for name, fingerprint in evaluator.FILES.items():
        raw = (repo / name).read_bytes()
        assert b"\r" not in raw
        assert hashlib.sha256(raw).hexdigest() == fingerprint
    # Prove Windows-style conversion is active, rather than silently disabled.
    expected = b"synthetic control\nsecond line\n"
    if autocrlf == "true":
        expected = expected.replace(b"\n", b"\r\n")
    assert (repo / "control.txt").read_bytes() == expected
    monkeypatch.setattr(evaluator, "ROOT", repo)
    evaluator.load_cohorts()


def test_attributes_are_exact_and_do_not_cover_other_files(tmp_path):
    repo = repository(tmp_path, "true")
    result = git(repo, "check-attr", "text", "eol", "--", *PATHS, "control.txt")
    for name in PATHS:
        assert f"{name}: text: set" in result
        assert f"{name}: eol: lf" in result
    assert "control.txt: text: unspecified" in result
    assert "control.txt: eol: unspecified" in result


def test_existing_crlf_checkout_requires_targeted_refresh(tmp_path, monkeypatch):
    repo = repository(tmp_path, "true", attributes=False)
    recheckout(repo, (*PATHS, "control.txt"))
    control = (repo / "control.txt").read_bytes()
    monkeypatch.setattr(evaluator, "ROOT", repo)
    for name in PATHS:
        assert b"\r\n" in (repo / name).read_bytes()
        with pytest.raises(CalendarEvidenceError):
            evaluator._read(name)
    (repo / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    git(repo, "add", "--", ".gitattributes")
    # Adding attributes alone does not rewrite an already checked-out file.
    assert all(b"\r\n" in (repo / name).read_bytes() for name in PATHS)
    # Refresh stat information; content remains identical in Git's clean filter.
    git(repo, "diff", "--", *PATHS)
    assert not git(repo, "status", "--porcelain", "--", *PATHS).strip()
    recheckout(repo, PATHS)
    for name, fingerprint in evaluator.FILES.items():
        assert hashlib.sha256((repo / name).read_bytes()).hexdigest() == fingerprint
    assert (repo / "control.txt").read_bytes() == control
    evaluator.load_cohorts()


def test_local_fixture_edits_remain_visible_and_integrity_rejected(tmp_path, monkeypatch):
    repo = repository(tmp_path, "true")
    name = PATHS[0]
    with (repo / name).open("ab") as stream:
        stream.write(b"\n")
    # The documented safety guard must stop before any forced checkout.
    assert git(repo, "status", "--porcelain", "--", *PATHS).strip()
    monkeypatch.setattr(evaluator, "ROOT", repo)
    with pytest.raises(CalendarEvidenceError):
        evaluator._read(name)
