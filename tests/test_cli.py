"""CLI smoke tests via subprocess.

These intentionally invoke the installed ``ltspice-convert`` console
script (not the function directly) so we exercise the same code path
end-users will hit, including exit-code propagation through the
setuptools-generated entry-point wrapper.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


FIXTURES = Path(__file__).parent / "fixtures" / "bidirectional"
RC_ASC = FIXTURES / "00_converter_test_rc_lowpass.asc"
RC_CIR = FIXTURES / "00_converter_test_rc_lowpass.cir"


def run_cli(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    """Invoke the CLI as `python -m ltspice_converter.cli ARGS`.

    Using `python -m` avoids depending on whether the console script
    is on PATH in the CI environment.
    """
    return subprocess.run(
        [sys.executable, "-m", "ltspice_converter.cli", *args],
        capture_output=True,
        text=True,
        check=check,
    )


# =============================================================================
# Basics
# =============================================================================

def test_version():
    r = run_cli("--version")
    assert r.returncode == 0
    assert r.stdout.strip().startswith("ltspice-convert ")


def test_help():
    r = run_cli("--help")
    assert r.returncode == 0
    assert "input file" in r.stdout.lower() or "input" in r.stdout.lower()


def test_error_on_unknown_extension(tmp_path):
    bad = tmp_path / "x.txt"
    bad.write_text("garbage")
    r = run_cli(str(bad))
    assert r.returncode != 0
    assert "unknown" in r.stderr.lower() or "extension" in r.stderr.lower()


def test_error_on_missing_file(tmp_path):
    r = run_cli(str(tmp_path / "nope.asc"))
    assert r.returncode != 0


# =============================================================================
# Convert mode
# =============================================================================

def test_convert_asc_to_cir(tmp_path):
    out = tmp_path / "rc.cir"
    r = run_cli(str(RC_ASC), "-o", str(out))
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "R1" in text
    assert "C1" in text


def test_convert_cir_to_asc(tmp_path):
    out = tmp_path / "rc.asc"
    r = run_cli(str(RC_CIR), "-o", str(out))
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    text = out.read_text(encoding="latin-1")
    assert "Version" in text or "SYMBOL" in text


def test_convert_auto_output_path(tmp_path):
    src = tmp_path / "rc.asc"
    src.write_text(RC_ASC.read_text(encoding="utf-8"))
    r = run_cli(str(src))   # no -o, expect rc.cir alongside
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "rc.cir").is_file()


def test_convert_with_to_flag(tmp_path):
    src = tmp_path / "rc.asc"
    src.write_text(RC_ASC.read_text(encoding="utf-8"))
    r = run_cli(str(src), "--to", "py")
    assert r.returncode == 0, r.stderr
    py_out = tmp_path / "rc.py"
    assert py_out.is_file()
    assert "schemdraw" in py_out.read_text(encoding="utf-8")


def test_convert_batch_to_dir(tmp_path):
    out_dir = tmp_path / "batch"
    inputs = list(FIXTURES.glob("00_converter_test_*.asc"))
    assert len(inputs) >= 5
    r = run_cli(*[str(p) for p in inputs], "-o", str(out_dir), "--to", "cir")
    assert r.returncode == 0, r.stderr
    cir_outputs = list(out_dir.glob("*.cir"))
    assert len(cir_outputs) == len(inputs)


# =============================================================================
# Check (lint) mode
# =============================================================================

def test_check_clean_file_pass():
    r = run_cli("--check", str(RC_ASC))
    assert r.returncode == 0, r.stderr
    assert "PASS" in r.stdout
    assert "[warn]" not in r.stdout


def test_check_strict_clean_still_pass():
    r = run_cli("--check", "--strict", str(RC_ASC))
    assert r.returncode == 0, r.stderr


def test_check_multiple_files():
    inputs = list(FIXTURES.glob("00_converter_test_*.asc"))[:3]
    r = run_cli("--check", *[str(p) for p in inputs])
    assert r.returncode == 0, r.stderr
    # Each file should produce its own section
    assert r.stdout.count("==") >= len(inputs) * 2  # header has == on both sides


# =============================================================================
# Info mode
# =============================================================================

def test_info_text():
    r = run_cli("--info", str(RC_ASC))
    assert r.returncode == 0, r.stderr
    assert "component_count" in r.stdout
    assert "component_types" in r.stdout


def test_info_json():
    r = run_cli("--info", "--json", str(RC_ASC))
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert isinstance(data, list)
    assert len(data) == 1
    item = data[0]
    assert item["format"] == "asc"
    assert item["component_count"] == 3
    assert item["component_types"] == {"I": 1, "R": 1, "C": 1}


# =============================================================================
# .asy search dir
# =============================================================================

def test_asy_dir_flag_accepted(tmp_path):
    # Flag should be parsed even if dir does not exist (just no-op there)
    r = run_cli("--asy-dir", str(tmp_path),
                "--info", str(RC_ASC))
    assert r.returncode == 0, r.stderr


# =============================================================================
# C5: static lint checks
# =============================================================================

def _write_cir(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_check_detects_duplicate_instance(tmp_path):
    cir = _write_cir(tmp_path, "dup.cir",
                     "* dup\nR1 a b 1k\nR1 b c 2k\n.end\n")
    r = run_cli("--check", str(cir))
    assert "duplicate instance name" in r.stdout
    assert "R1" in r.stdout


def test_check_detects_floating_node(tmp_path):
    cir = _write_cir(tmp_path, "float.cir",
                     "* float\nV1 in 0 5\nR1 in mid 1k\n"
                     "R2 mid out 1k\nR3 dangle 0 1k\n.end\n")
    r = run_cli("--check", str(cir))
    assert "floating node" in r.stdout
    assert "dangle" in r.stdout or "out" in r.stdout


def test_check_detects_orphan_model(tmp_path):
    cir = _write_cir(tmp_path, "orphan.cir",
                     "* orphan\nV1 in 0 5\nR1 in out 1k\n"
                     ".model UNUSED D\n.end\n")
    r = run_cli("--check", str(cir))
    assert "never used" in r.stdout
    assert "UNUSED" in r.stdout


def test_check_detects_undefined_model(tmp_path):
    cir = _write_cir(tmp_path, "undef_model.cir",
                     "* undef\nV1 in 0 5\nD1 in 0 MY_CUSTOM_DIODE\n.end\n")
    r = run_cli("--check", str(cir))
    # Should mention the undefined model since it's not a standard one
    assert "MY_CUSTOM_DIODE" in r.stdout


def test_check_detects_undefined_param(tmp_path):
    cir = _write_cir(tmp_path, "undef_param.cir",
                     "* undef\nR1 in out {missingparam}\n"
                     "R2 in out {Rval}\n.param Rval=1k\n.end\n")
    r = run_cli("--check", str(cir))
    assert "missingparam" in r.stdout
    # The defined param should NOT be flagged
    assert "Rval" not in r.stdout.split("parameter(s)")[1].split("\n")[0]


def test_check_clean_netlist_no_warnings(tmp_path):
    cir = _write_cir(tmp_path, "clean.cir",
                     "* clean\nV1 in 0 5\nR1 in out 1k\nC1 out 0 1u\n"
                     ".ac dec 100 1 100k\n.end\n")
    r = run_cli("--check", str(cir))
    assert r.returncode == 0
    assert "PASS" in r.stdout
    # Should have no [warn] lines from C5 checks
    static_warns = [
        "duplicate", "floating", "never used", "referenced but not defined",
        "parameter(s) referenced",
    ]
    for w in static_warns:
        assert w not in r.stdout, f"unexpected warning containing {w!r}: {r.stdout}"


# =============================================================================
# B4: unparsed-line surfacing + suggestions
# =============================================================================

def test_check_surfaces_unparsed_line(tmp_path):
    cir = _write_cir(tmp_path, "unparsed.cir",
                     "* test\nV1 in 0 5\nZorg foo bar baz\n.end\n")
    r = run_cli("--check", str(cir))
    assert "line 3" in r.stdout
    assert "Zorg" in r.stdout
    assert "unrecognised element" in r.stdout.lower() or \
           "SPICE elements start" in r.stdout


def test_check_typo_suggestion(tmp_path):
    # 'Resistor' starts with R and gets accepted by the parser (oddly named),
    # but a token like 'Diode' (starts with D, valid prefix) also passes.
    # Use an actually-unrecognised token so we hit the hint path.
    cir = _write_cir(tmp_path, "typo.cir",
                     "* typo test\nR1 in out 1k\nZorg foo bar\n.end\n")
    r = run_cli("--check", str(cir))
    assert "Zorg" in r.stdout
