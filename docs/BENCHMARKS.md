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
3. **Round-trip count match**: re-parse the round-tripped .asc and
   verify the **component count** is preserved.

We also measure two stricter checks:

- **Symbol-kind drift**: count how many original SYMBOL kinds (e.g.
  `ind2`, `schottky`, `pnp`, `polcap`) disappear from the regenerated
  .asc.  This captures whether the schematic *looks* the same when
  re-opened in LTspice.
- **GND-connectivity preservation**: rebuild the bipartite
  component-to-node graph and check whether each component's set of
  ground-touching pin positions matches between original and
  round-tripped netlists.  This is a node-rename-invariant proxy for
  topology preservation.

Per-source sample size is 100 (count) / 80 (kind + GND) circuits, drawn
deterministically (`random.seed(0)`).  `github_repos` is the most
diverse and the closest proxy for unseen real-world input;
`textbook` was iterated against during development and is a noisy
upper bound.

The script is `bench/baseline.py` (gitignored; depends on a
LAB-private corpus path).

## Textbook training-data corpus (LAB-private)

A second benchmark consumes a small, curated set of circuits harvested
straight from electrical engineering textbooks. Each entry is a
self-contained `.cir` of 3–20 components that exercises a specific
SPICE feature (DC node analysis, RC/LCR/CR filter, diode companion
model, CMOS SUBCKT, ...).  Provenance for every circuit is recorded
in `circuit_db_<book>.json`:

```json
{
  "book": "MATLABで学ぶ 回路シミュレーションとモデリング",
  "author": "菅原光俊",
  "publisher": "鳥影社",
  "entries": [
    {
      "page": 158, "figure": "Fig 4.2.1",
      "chapter": 4, "section": "4.2 DC解析",
      "circuit_type": "linear DC node analysis (current source driven)",
      "cir_file": "circuits_matlab/textbook_p158_Fig_4-2-1.cir",
      "lint_status": "PASS (no warnings)",
      ...
    }, ...
  ]
}
```

The `.cir` files themselves stay LAB-private (publisher copyright) and
live under `<mcp-server>/circuit/textbook/circuits_<book>/`.

### Round-trip pass rate (28 textbook circuits, 2026-05-19)

| Book | Entries | PASS (clean) | PASS (with warn) | FAIL |
|---|---:|---:|---:|---:|
| MATLAB で学ぶ                | 17 | 16 (94.1%) | 1 | 0 |
| Python で学ぶ (新版)         | 11 | 10 (90.9%) | 1 | 0 |
| **All textbook circuits**    | **28** | **26 (92.9%)** | **2** | **0** |
| **Combined pass (any)**      |        |               | **100.0%** | |

The two PASS-with-warn cases are both copies of the same `.SUBCKT INV`
CMOS-inverter example and share a known C5 false-positive
(X-subckt-invocation flagged as undefined `.model`; subckt-internal
`.model` flagged as orphan) — both fixes are tracked in the
`lint_findings_for_converter[]` section of the LAB-private DB JSON
and will land in a future C5 patch.

## Headline results — v0.3.1 (after C2: `.asy` lookup + isolation zone)

`C2` — when emitting a multi-pin SUBCIRCUIT, place the SYMBOL in an
isolated coordinate band (x ≥ 4096), then emit one FLAG per pin at
the **canonical offset** reported by `AsyParser.get_terminal_offsets`
(the same lookup the asc parser uses on re-extraction). On the way
back through the pipeline asc_parser finds the same offsets and the
node names match exactly. Without an available `.asy` file the
generator falls back to the v0.3.0 compact grid (count-preserving
but topology-lossy).

### GND-connectivity preservation (node-rename-invariant topology proxy)

| Source | v0.3.0 | v0.3.1 | Δ |
|---|---|---|---|
| LTspice Examples                | 43.8 % | **48.8 %** | +5 pt |
| LTspice Applications            | 13.8 % | **76.2 %** | **+62.4 pt** |
| GitHub repos                    | 30.0 % | **46.2 %** | +16.2 pt |
| **Mean (240 samples)**          | **29.2 %** | **57.1 %** | **+27.9 pt** |

Count preservation unchanged (still 99.25 % mean). The 62-point jump
on LTspice Applications is the .asy lookup hitting on common vendor
ICs (LTC*, ADP*, ADA*, AD*). The smaller bump on GitHub repos
reflects symbols whose `.asy` files live in third-party libraries
that are not on the default LTspice search path.

## Headline results — v0.3.0 (after B1 partial)

`B1` — extend `Component` with `extra_nodes: List[str]` and propagate all
pin connections through NetlistParser → AscGenerator. AscGenerator now
emits a compact 4×5 grid of `FLAG + WIRE` lines around each multi-pin
SUBCIRCUIT, preserving the full pin list in the regenerated `.asc`.

Result: count preservation unchanged (99.25%); GND-connectivity
**unchanged** at the corpus level. Diagnostic showed the geometric
placement chosen by the auto-layouter often coincides with another
component's WIRE endpoint, so `asc_parser._estimate_terminals`
selects those external endpoints over the dedicated multi-pin FLAGs.
A proper fix needs either (a) a dedicated isolation zone in the
layouter or (b) `.asy` file lookup (planned for Phase C1). For now
B1 preserves the data structurally (pin info is in the netlist) but
the geometric round-trip remains lossy.

## Headline results — v0.2.1 (after Phase A: A1-A4)

### schemdraw script execution (new check)

| Source | Failures (v0.2.0) | Failures (v0.2.1) |
|---|---|---|
| 150 samples (50 each of LTspice examples / applications / github_repos) | **7 / 150** | **0 / 150** |

Three classes of bug fixed in Phase A:
- `AttributeError: 'X.end' not defined` when an Opamp/multi-pin element
  is the last in a parallel group (now falls back to `d.move()`).
- `ValueError: Axis limits cannot be NaN or Inf` on empty drawings (now
  emits an invisible guard line).
- 4-pin BJT substrate variants (`npn3`, `pnp4`) were re-emitted as
  `SYMBOL <Q-model-name>` instead of `SYMBOL npn3` (model name was
  being confused with symbol kind). Fixed by extending `SYMBOL_TO_SPICE`
  to recognise substrate variants.

## Headline results — v0.2.0 (after P1 + P4)

### `.asc → netlist → .asc` round-trip (component count)

| Source | v0.1.0 | v0.2.0 | Δ |
|---|---|---|---|
| textbook (training-adjacent)    | 100%   | 100%   | 0   |
| LTspice Applications            |  98%   | **100%** | +2  |
| LTspice Examples                |  94%   |  **99%** | +5  |
| GitHub repos (unseen)           |  79%   |  **98%** | +19 |
| **Mean (400 samples)**          | **92.75%** | **99.25%** | **+6.5** |

### `netlist → schemdraw script → netlist` round-trip

| Source | v0.1.0 | v0.2.0 | Δ |
|---|---|---|---|
| textbook                        | 100%   | 100%   | 0   |
| LTspice Applications            |  96%   |  **98%** | +2  |
| LTspice Examples                |  74%   |  **80%** | +6  |
| GitHub repos                    |  60%   |  **82%** | +22 |
| **Mean (200 samples)**          | **82.5%** | **90.0%** | **+7.5** |

The schemdraw arm shares the `asc_to_netlist` stage with the
.asc-round-trip arm, so P1 vendor-symbol handling improved both.

### Symbol-kind preservation (240 samples, after P4)

Drift events (smaller is better):

| Symbol kind | v0.1.0 | v0.2.0 | Δ |
|---|---:|---:|---:|
| `ind2`                          | 91 |   0 | -91 |
| `schottky`                      | 56 |   0 | -56 |
| `pnp`                           | 47 |   4 | -43 |
| `cap` (variant losses)          | 23 |  34 |   ? |
| `polcap`                        | 11 |   0 | -11 |
| `npn3`                          | 13 |  13 |   0 |
| `LTspiceControlLibrary\*` (15 kinds) |  ~90 | ~85 |  -5 |
| **Files with any drift**        | 195 | 145 | -50 |

The `cap`/`res`/`voltage` rows are mostly count side-effects, not
actual variant losses — investigated separately.

### GND-connectivity preservation (new metric in v0.2.0)

This is the strictest check we run, and it shows the **biggest
remaining weakness** — topology drift in regenerated schematics:

| Source | GND-connectivity preserved |
|---|---|
| LTspice Examples                |  43.8% |
| LTspice Applications            |  13.8% |
| GitHub repos                    |  30.0% |

Even when the component count is exactly right, the regenerated .asc
often has different pin connections to ground than the original.  The
biggest contributor is **multi-pin vendor symbols** (LTC*/ADP*/ISO*
ICs with 5–20 pins): the converter currently preserves the
**count** of such symbols but reduces them to 2-pin generic blocks
because it does not have access to the symbol's `.asy` definition.

If your use case requires faithful topology preservation for vendor
ICs, the workaround today is:

- Keep the original `.asc` as the source of truth and use the converter
  for **netlist generation only** (asc → netlist, which is 100% across
  all sources).
- For the reverse direction (netlist → asc), use the converter only on
  circuits built from standard LTspice library symbols (R/C/L/V/I/D/Q/M/J).

## Known failure modes (after v0.2.0)

Even at 98–100% count-preservation pass rate, some classes of circuit
are weak:

- **Multi-pin vendor IC topology** — counts are preserved but pin
  layout collapses to 2 pins.  See [GND-connectivity preservation]
  (#gnd-connectivity-preservation-new-metric-in-v020) above.
- **`.subckt` body inclusion** — when a circuit embeds a `.subckt`
  block in the same .asc, only the invocation is preserved on
  round-trip; the body may be lost.
- **`LTspiceControlLibrary\\*`** math/logic blocks — currently treated
  as 5-pin opamps but the math operation identity (`and`, `mul`, etc.)
  is not fully recovered.
- **`npn3` (BJT with substrate symbol)** — recovered as `npn` (3-pin
  view), substrate connection lost.
- **schemdraw script execution errors on some inputs** — observed in
  ~6% of github_repos samples (XML parse errors, axis-limit NaN,
  unknown element types).  These produce no output but raise a
  Python exception, so they are at least visible to the caller.

These will be addressed in subsequent releases.  Run
`python bench/baseline.py` against your own corpus and file an
[issue](https://github.com/ksugahar/ltspice-converter/issues) with the
failing `.asc` if you hit one of these or a new class.

## Reproducibility

```bash
pip install ltspice-converter[test]
git clone https://github.com/ksugahar/ltspice-converter
cd ltspice-converter
# Edit bench/baseline.py:CORPUS_ROOTS to point at your own .asc corpus
python bench/baseline.py --per-source 100 --out bench/my_baseline.json
```
