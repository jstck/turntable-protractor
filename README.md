# Vinyl Turntable Pickup Alignment Protractor Generator

Generates a printable 1:1 scale PDF protractor on A4 paper for aligning a phono cartridge on a pivoted tonearm. If you're printing on some other paper size, just make sure to print it at 100% scale.

## Requirements

Python 3 and [reportlab](https://pypi.org/project/reportlab/):

```
pip install reportlab
```

## Usage

```
python protractor.py <D> [-a TYPE] [--all] [-o FILE]
```

**D** is the pivot-to-spindle distance in millimetres — the distance from the tonearm pivot centre to the platter spindle centre. This is the only measurement you need to take from your turntable.

### Options

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `-a` | `baerwald`, `lofgren_a`, `lofgren_b`, `stevenson` | `baerwald` | Alignment type (single-page mode) |
| `--all` | — | — | Generate all three alignments as a single multi-page PDF |
| `-o` | filename | `protractor_<type>_<D>mm.pdf` / `protractor_all_<D>mm.pdf` | Output PDF path |

### Examples

```bash
# Löfgren A / Baerwald alignment, 215 mm pivot-to-spindle distance
python protractor.py 215

# Löfgren B, custom output name
python protractor.py 222.0 -a lofgren_b -o my_arm.pdf

# Stevenson, 211.5 mm
python protractor.py 211.5 -a stevenson

# All three alignments in one PDF
python protractor.py 215 --all

# All three, custom output name
python protractor.py 215 --all -o all_alignments.pdf
```

The script prints the calculated tonearm parameters to the terminal and saves the PDF.

## Alignment types

All three alignments target two null radii — groove positions where tracking error is exactly zero. The choice of null radii reflects different optimisation criteria over the standard IEC groove radii (inner: 60.325 mm, outer: 146.05 mm).

| Type | Null radii | Optimises for |
|------|-----------|---------------|
| **Löfgren A / Baerwald** | 66.0 mm, 120.9 mm | Minimum peak (maximum) tracking distortion |
| **Löfgren B** | 70.3 mm, 116.6 mm | Minimum average distortion; lower error across most of the record but slightly higher at the inner and outer extremes |
| **Stevenson** | 60.325 mm, 117.42 mm | Null point at the inner groove radius — minimises distortion on the innermost grooves at the expense of higher error elsewhere |

Note that the two options `baerwald` and `lofgren_a` are aliases for the exact same algorithm.

## Calculated parameters

Given D and the null radii (r₁, r₂), the following are derived:

| Parameter | Formula | Meaning |
|-----------|---------|---------|
| Effective length L | √(D² + r₁·r₂) | Distance from pivot centre to stylus tip |
| Offset angle β | arcsin((r₁+r₂) / 2L) | Angle between tonearm tube and cartridge body axis |
| Overhang h | L − D | Distance the stylus extends past the spindle centre |

## Printing

1. Open the PDF and print at **100% / actual size** — disable any "fit to page" or "scale to fit" option.
2. After printing, measure the 100 mm scale bar at the bottom of the sheet. It must measure exactly 100 mm; if not, adjust your printer settings and reprint.

## How to use the protractor

1. Place the protractor on the platter with the spindle through the centre hole.
2. Swing the tonearm so the stylus tip sits on the **inner null point** red dot.
3. Check that the cartridge body is parallel to the tangential grid lines. Adjust overhang (slide cartridge in the headshell slots) and azimuth until it aligns.
4. Swing the arm to the **outer null point** and repeat the check.
5. Iterate between both points until the cartridge is parallel to the grid lines at both null points simultaneously.
