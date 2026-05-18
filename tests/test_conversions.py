#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round-trip conversion tests: .cir <-> schemdraw <-> .asc

Tests:
1. .cir -> schemdraw script compiles and executes
2. .cir <-> schemdraw round-trip preserves nodes and directives
3. .cir <-> .asc round-trip preserves component count
4. Two routes (direct .asc vs via schemdraw) produce equivalent .asc
"""
from __future__ import annotations

import os
import pytest

from ltspice_converter.parser.cir_to_schemdraw import cir_string_to_schemdraw
from ltspice_converter.parser.schemdraw_to_cir import schemdraw_script_to_cir
from ltspice_converter.parser.netlist_to_asc import NetlistToAsc
from ltspice_converter.parser.asc_parser import AscParser, NetlistExtractor


# =============================================================================
# Author-authored test circuits (minimal, no third-party derivative content)
# =============================================================================
CIRCUITS = {
    "rc_lowpass": """* RC Lowpass Filter
V1 in 0 AC 1
R1 in out 1k
C1 out 0 1u
.ac dec 20 1 100k
.end""",
    "rlc_series": """* RLC Series
V1 in 0 SINE(0 1 1k)
R1 in n1 100
L1 n1 out 10m
C1 out 0 1u
.tran 10m
.end""",
    "voltage_divider": """* Voltage Divider
V1 in 0 5
R1 in out 1k
R2 out 0 1k
.op
.end""",
    "pi_filter": """* Pi Filter
V1 in 0 AC 1
C1 in 0 10u
L1 in out 100m
C2 out 0 10u
R1 out 0 50
.ac dec 20 1 100k
.end""",
    "bandpass": """* RLC Bandpass
V1 in 0 AC 1
R1 in n1 100
L1 n1 out 10m
C1 out 0 100n
R2 out 0 10k
.ac dec 50 100 100k
.end""",
}

DIRECTIVE_CHECKS = {
    "rc_lowpass": ".ac",
    "rlc_series": ".tran",
    "voltage_divider": ".op",
    "pi_filter": ".ac",
    "bandpass": ".ac",
}


# =============================================================================
# Helpers
# =============================================================================
def _count_components(netlist: str) -> int:
    count = 0
    for line in netlist.strip().split("\n"):
        line = line.strip()
        if line and line[0].isalpha() and not line.startswith("*") and not line.startswith("."):
            count += 1
    return count


def _count_signal_nodes(netlist: str) -> int:
    nodes = set()
    for line in netlist.strip().split("\n"):
        parts = line.split()
        if len(parts) >= 3 and parts[0][0].isalpha() and parts[0][0] != "*":
            for p in parts[1:3]:
                if p != "0" and p.lower() != "gnd":
                    nodes.add(p)
    return len(nodes)


def _has_directive(netlist: str, prefix: str) -> bool:
    for line in netlist.strip().split("\n"):
        if line.strip().lower().startswith(prefix.lower()):
            return True
    return False


def _asc_to_netlist_pure_python(asc_text: str) -> str:
    """Pure-Python ASC -> netlist (no LTspice.exe required)."""
    parser = AscParser()
    parser.parse_string(asc_text)
    extractor = NetlistExtractor(parser)
    return extractor.extract()


# =============================================================================
# Tests
# =============================================================================
@pytest.mark.parametrize("name,cir", list(CIRCUITS.items()))
def test_cir_to_schemdraw_compiles(name, cir):
    script = cir_string_to_schemdraw(cir, name)
    compile(script, f"<{name}>", "exec")


@pytest.mark.parametrize("name,cir", list(CIRCUITS.items()))
def test_cir_to_schemdraw_executes(name, cir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    script = cir_string_to_schemdraw(cir, name)
    exec_globals: dict = {}
    exec(script, exec_globals)


@pytest.mark.parametrize("name,cir", list(CIRCUITS.items()))
def test_schemdraw_roundtrip_nodes(name, cir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    script = cir_string_to_schemdraw(cir, name)
    recovered = schemdraw_script_to_cir(script, name)
    assert _count_signal_nodes(cir) == _count_signal_nodes(recovered), \
        f"{name}: node count changed: {cir!r} -> {recovered!r}"


@pytest.mark.parametrize("name,cir", list(CIRCUITS.items()))
def test_schemdraw_roundtrip_directives(name, cir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    script = cir_string_to_schemdraw(cir, name)
    recovered = schemdraw_script_to_cir(script, name)
    expected = DIRECTIVE_CHECKS.get(name)
    if expected:
        assert _has_directive(recovered, expected), \
            f"{name}: directive {expected!r} lost in round-trip"


@pytest.mark.parametrize("name,cir", list(CIRCUITS.items()))
def test_cir_to_asc_roundtrip_component_count(name, cir):
    asc = NetlistToAsc().convert_string(cir)
    recovered = _asc_to_netlist_pure_python(asc)
    assert _count_components(cir) == _count_components(recovered), \
        f"{name}: component count changed via .asc round-trip"


@pytest.mark.parametrize("name,cir", list(CIRCUITS.items()))
def test_route_a_equals_route_b(name, cir, tmp_path, monkeypatch):
    """Direct .cir->.asc and via-schemdraw .cir->schemdraw->.cir->.asc agree."""
    monkeypatch.chdir(tmp_path)
    asc_a = NetlistToAsc().convert_string(cir)
    script = cir_string_to_schemdraw(cir, name)
    cir_b = schemdraw_script_to_cir(script, name)
    asc_b = NetlistToAsc().convert_string(cir_b)

    if asc_a == asc_b:
        return  # identical

    # otherwise require structural equivalence: same WIRE / SYMBOL count
    assert asc_a.count("WIRE") == asc_b.count("WIRE") and \
        asc_a.count("SYMBOL") == asc_b.count("SYMBOL"), \
        f"{name}: route A and route B disagree structurally"


def test_unknown_vendor_symbol_preserved():
    """Regression: vendor-specific SYMBOL (e.g. ISO16750-2) must survive
    a .asc -> netlist -> .asc round-trip. Previously such symbols were
    silently dropped because the extractor produced a 2-token U-statement
    with no model name, which NetlistParser rejected.
    """
    # Hand-crafted minimal vendor-symbol .asc -- same shape as real
    # LTspice vendor templates but no proprietary content.
    asc = """Version 4
SHEET 1 880 680
WIRE 128 -64 128 -96
WIRE 128 48 128 16
FLAG 128 48 0
SYMBOL ACME_PROPRIETARY_BLOCK 128 -64 R0
SYMATTR InstName U1
SYMBOL ACME_PROPRIETARY_BLOCK 256 -64 R0
SYMATTR InstName U2
TEXT 0 100 Left 2 !.tran 1m
"""
    parser = AscParser()
    parser.parse_string(asc)
    netlist = NetlistExtractor(parser).extract()
    # Both vendor symbols must appear in the netlist with the model name
    assert "ACME_PROPRIETARY_BLOCK" in netlist.lower() or "acme_proprietary_block" in netlist.lower()

    n1 = _count_components(netlist)
    assert n1 == 2, f"expected 2 components, got {n1}: {netlist!r}"

    # Round-trip back to .asc
    asc2 = NetlistToAsc().convert_string(netlist)
    parser2 = AscParser()
    parser2.parse_string(asc2)
    netlist2 = NetlistExtractor(parser2).extract()
    n2 = _count_components(netlist2)
    assert n1 == n2, (
        f"component count drifted in round-trip: {n1} -> {n2}\n"
        f"asc2: {asc2}\nnetlist2: {netlist2}"
    )


def test_top_level_api_smoke():
    """Public API smoke test."""
    import ltspice_converter as lc
    netlist = CIRCUITS["rc_lowpass"]
    script = lc.netlist_to_schemdraw(netlist, "rc")
    assert "schemdraw" in script
    recovered = lc.schemdraw_to_netlist(script, "rc")
    assert _count_signal_nodes(netlist) == _count_signal_nodes(recovered)
