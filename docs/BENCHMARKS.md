# Benchmarks

This document reports the converter's performance on a corpus of
real-world LTspice circuits.  All numbers come from LAB-local
benchmarks; the corpus itself is not redistributed (see [README §
Project history & scope](../README.md)).

## Methodology

For each `.asc` in the sample:

1. **`asc_to_netlist`**: parse the .asc and emit a SPICE netlist
   (pure-Python path, no LTspice.exe).
2. **`netlist_to_asc`**: round-trip the netlist back through
   `NetlistToAsc().convert_string()`.
3. **Round-trip match**: re-parse the round-tripped .asc and verify
   the component count is preserved.

Per-source sample size is 100 circuits, drawn deterministically
(`random.seed(0)`).  The "github_repos" source is the most diverse and
the closest proxy for unseen-style real-world input; "textbook" is the
data the converter was iterated against during development and is
therefore a noisy upper bound.

The script is `bench/baseline.py` (gitignored — depends on a
LAB-private corpus path).

## Results — v0.1.0 → after P1 fix

| Source | asc → netlist | netlist → asc (v0.1.0) | netlist → asc (after P1) | Δ |
|---|---|---|---|---|
| textbook (training-adjacent)            | 100% | 100% | 100% | 0 |
| LTspice Applications                    | 100% | 98% | **100%** | +2 |
| LTspice Examples                        | 100% | 94% | **99%** | +5 |
| GitHub repos (unseen)                   | 100% | 79% | **98%** | **+19** |
| **Mean (400 samples)**                  | 100% | 92.75% | **99.25%** | **+6.5** |

A complementary benchmark on the schemdraw arm (50 samples per source,
200 total) shows the path netlist → schemdraw script → netlist
preserves the component count on:

| Source | compile rate | netlist round-trip |
|---|---|---|
| textbook            | 100% | 100% |
| LTspice Applications | 100% | 96% |
| LTspice Examples     | 100% | 74% |
| GitHub repos         | 100% | 60% |

The schemdraw arm has not yet received targeted improvements; it is
the next focus area.

## Known failure modes

Even at 98–100% pass rate, some classes of circuit are weak:

- **Multi-page schematics** referenced via `TextLine SUBCKT=...` —
  not yet enumerated.
- **B-source (`bv`, `bi`) with model-name disambiguation** — some
  3-token B-statements (`B1 n+ n- V=...`) are emitted but the model
  arg can be mis-classified.
- **Multi-pin vendor symbols (5+ pins)** — the round-trip preserves
  count but truncates to 2 pin connections; topology is not preserved.
- **`.subckt` body inclusion** — when a circuit embeds a `.subckt`
  block in the same .asc, only the invocation is preserved, the body
  may be lost.

These will be addressed in subsequent releases.  Run
`python bench/baseline.py` against your own corpus and file an
[issue](https://github.com/ksugahar/ltspice-converter/issues) with the
failure if you hit one of these or a new class.

## Reproducibility

```bash
pip install ltspice-converter[test]
git clone https://github.com/ksugahar/ltspice-converter
cd ltspice-converter
# Edit bench/baseline.py:CORPUS_ROOTS to point at your own .asc corpus
python bench/baseline.py --per-source 100 --out bench/my_baseline.json
```
