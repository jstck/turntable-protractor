#!/usr/bin/env python3
"""
Vinyl Turntable Pickup Alignment Protractor Generator

Generates a printable 1:1 scale PDF protractor on A4 paper for aligning
a phono cartridge. Given the pivot-to-spindle distance, computes optimal
tonearm geometry and draws a two-point alignment protractor.

Supports: Lofgren A (Baerwald), Lofgren B, Stevenson alignments.

Usage:
    python protractor.py 215.0
    python protractor.py 215.0 -a lofgren_b
    python protractor.py 222.0 -a stevenson -o my_protractor.pdf

Requires: pip install reportlab
"""

import math
import argparse
import sys

# ---------------------------------------------------------------------------
# Alignment definitions
# ---------------------------------------------------------------------------
# Null radii (in mm) for IEC standard groove radii:
#   Inner groove: 60.325 mm (2-3/8 in)
#   Outer groove: 146.05 mm (5-3/4 in)
#
# At each null radius the stylus is perfectly tangent to the groove.
# The alignment type determines which null radii are targeted.

ALIGNMENTS = {
    "baerwald": {
        "name": "Lofgren A / Baerwald",
        "r1": 66.0,      # inner null radius (mm)
        "r2": 120.9,     # outer null radius (mm)
    },
    "lofgren_b": {
        "name": "Lofgren B",
        "r1": 70.3,
        "r2": 116.6,
    },
    "stevenson": {
        "name": "Stevenson",
        "r1": 60.325,
        "r2": 117.42,
    },
}

# Standard LP groove radii used for arc drawing
INNER_GROOVE_R = 60.325   # mm
OUTER_GROOVE_R = 146.05   # mm

# ---------------------------------------------------------------------------
# Geometry calculations
# ---------------------------------------------------------------------------

def compute_geometry(D: float, r1: float, r2: float) -> dict:
    """
    Compute tonearm alignment geometry from pivot-to-spindle distance and
    desired null radii.

    Theory:
      At a null point (radius r_n from spindle), the stylus is perfectly
      tangent to the groove. In the triangle spindle–pivot–stylus with
      sides D (spindle-to-pivot), L (pivot-to-stylus), r_n (spindle-to-stylus),
      the tangency condition requires the angle at the stylus vertex = 90° - β.
      Applying Vieta's formulas to the resulting quadratic (which must hold
      for both null radii) yields:
          L  = sqrt(D² + r1·r2)
          β  = arcsin((r1 + r2) / (2L))    [offset angle]
          h  = L − D                        [overhang]

    Null point positions (spindle at origin, pivot at (−D, 0)):
      Both null points lie on the arc of radius L from the pivot AND on their
      respective circles of radius r_n from the spindle.  Solving the two
      circle equations gives:
          x_n = r_n · (r_other − r_n) / (2D)
          y_n = sqrt(r_n² − x_n²)

    Args:
        D:  pivot-to-spindle distance (mm)
        r1: inner null radius (mm)
        r2: outer null radius (mm)

    Returns:
        dict with keys: L, beta (deg), h, D, r1, r2, null1, null2
    """
    L = math.sqrt(D**2 + r1 * r2)
    sin_beta = (r1 + r2) / (2.0 * L)
    # Clamp for numerical safety
    sin_beta = max(-1.0, min(1.0, sin_beta))
    beta_deg = math.degrees(math.asin(sin_beta))
    h = L - D

    # Null point 1 (inner)
    x1 = r1 * (r2 - r1) / (2.0 * D)
    y1 = math.sqrt(max(0.0, r1**2 - x1**2))

    # Null point 2 (outer)
    x2 = -r2 * (r2 - r1) / (2.0 * D)
    y2 = math.sqrt(max(0.0, r2**2 - x2**2))

    return {
        "L": L,
        "beta": beta_deg,
        "h": h,
        "D": D,
        "r1": r1,
        "r2": r2,
        "null1": (x1, y1),
        "null2": (x2, y2),
    }


def arc_point_on_groove(L: float, D: float, r_groove: float):
    """
    Find where the stylus arc (radius L from pivot at (−D,0)) intersects
    a groove circle (radius r_groove from spindle at origin).

    Returns (x, y) relative to spindle, or None if no intersection.
    """
    # From the two circle equations:
    #   x² + y² = r_groove²
    #   (x+D)² + y² = L²
    # Subtracting: 2Dx + D² = L² − r_groove²
    x = (L**2 - r_groove**2 - D**2) / (2.0 * D)
    y_sq = r_groove**2 - x**2
    if y_sq < 0:
        return None
    return (x, math.sqrt(y_sq))


# ---------------------------------------------------------------------------
# PDF drawing
# ---------------------------------------------------------------------------

def _require_reportlab():
    try:
        from reportlab.pdfgen import canvas as pdfcanvas
        from reportlab.lib.units import mm
        from reportlab.lib.pagesizes import A4
        return pdfcanvas, mm, A4
    except ImportError:
        print("Error: reportlab is required.  Install with:\n  pip install reportlab")
        sys.exit(1)


def _draw_page(c, geo: dict, alignment_name: str):
    """Draw one protractor page onto an existing canvas (already positioned on a blank page)."""
    from reportlab.lib.units import mm
    from reportlab.lib.pagesizes import A4

    page_w, page_h = A4   # points (1 pt = 1/72 inch ≈ 0.353 mm)

    # ------------------------------------------------------------------
    # Page layout
    # Spindle at the center-bottom of the usable area.
    # All geometry coordinates are in mm relative to spindle.
    # ------------------------------------------------------------------
    SP_X_MM = 105.0   # spindle x on page (mm from left edge)
    SP_Y_MM = 35.0    # spindle y on page (mm from bottom edge)

    def pt(x_mm, y_mm=None):
        """Convert mm (relative to spindle) → PDF points."""
        if y_mm is None:
            # called as pt((x, y))
            x_mm, y_mm = x_mm
        return ((SP_X_MM + x_mm) * mm, (SP_Y_MM + y_mm) * mm)

    D  = geo["D"]
    L  = geo["L"]
    r1 = geo["r1"]
    r2 = geo["r2"]
    null1 = geo["null1"]
    null2 = geo["null2"]

    # ------------------------------------------------------------------
    # 1. Tonearm arc (stylus path)
    # ------------------------------------------------------------------
    # The arc is a circle of radius L centred on the pivot at (−D, 0).
    # We draw only the portion between inner and outer groove radii,
    # extended a little beyond each end for clarity.
    pivot_x_pt = (SP_X_MM - D) * mm
    pivot_y_pt = SP_Y_MM * mm
    arc_r_pt   = L * mm

    p_inner = arc_point_on_groove(L, D, INNER_GROOVE_R)
    p_outer = arc_point_on_groove(L, D, OUTER_GROOVE_R)

    if p_inner and p_outer:
        # Angles from pivot (degrees, CCW from 3 o'clock)
        def pivot_angle(px, py):
            return math.degrees(math.atan2(py, px + D))   # +D because pivot at −D

        a1 = pivot_angle(*p_inner)
        a2 = pivot_angle(*p_outer)
        start_a = min(a1, a2) - 3.0
        extent_a = abs(a2 - a1) + 6.0

        c.setStrokeColorRGB(0.55, 0.55, 0.55)
        c.setLineWidth(0.6)
        c.arc(
            pivot_x_pt - arc_r_pt, pivot_y_pt - arc_r_pt,
            pivot_x_pt + arc_r_pt, pivot_y_pt + arc_r_pt,
            startAng=start_a, extent=extent_a,
        )

    # ------------------------------------------------------------------
    # 2. Groove radius reference circles (from spindle)
    # ------------------------------------------------------------------
    sp_x_pt = SP_X_MM * mm
    sp_y_pt = SP_Y_MM * mm

    c.setLineWidth(0.25)
    for r_ref, is_limit in [
        (INNER_GROOVE_R, True), (OUTER_GROOVE_R, True),
        (70, False), (80, False), (90, False),
        (100, False), (110, False), (120, False), (130, False), (140, False),
    ]:
        if is_limit:
            c.setStrokeColorRGB(0.4, 0.4, 0.4)
            c.setDash(3, 3)
        else:
            c.setStrokeColorRGB(0.80, 0.80, 0.80)
            c.setDash()
        c.circle(sp_x_pt, sp_y_pt, r_ref * mm, stroke=1, fill=0)
    c.setDash()

    # ------------------------------------------------------------------
    # 3. Spindle marker
    # ------------------------------------------------------------------
    SPINDLE_DIAM_MM = 7.24   # standard LP spindle diameter
    sr = (SPINDLE_DIAM_MM / 2.0) * mm

    c.setStrokeColorRGB(0, 0, 0)
    c.setFillColorRGB(0, 0, 0)
    c.setLineWidth(0.8)
    # Outer reference circle
    c.circle(sp_x_pt, sp_y_pt, sr * 2.2, stroke=1, fill=0)
    # The spindle hole itself (white, to cut out or punch)
    c.setFillColorRGB(1, 1, 1)
    c.circle(sp_x_pt, sp_y_pt, sr, stroke=1, fill=1)
    # Tiny centre dot for precision
    c.setFillColorRGB(0, 0, 0)
    c.circle(sp_x_pt, sp_y_pt, 0.4 * mm, stroke=0, fill=1)
    # Crosshair
    c.setLineWidth(0.4)
    for dx, dy in [(8, 0), (-8, 0), (0, 8), (0, -8)]:
        ex, ey = pt(dx, dy)
        c.line(sp_x_pt, sp_y_pt, ex, ey)

    # ------------------------------------------------------------------
    # 3b. Spindle-to-pivot axis line
    # ------------------------------------------------------------------
    # The pivot sits at (−D, 0) in spindle-relative coords; for typical
    # arms it is off the left edge of the page.  Draw a dashed line from
    # the spindle toward the pivot, clipping at the page margin.
    MARGIN_MM = 5.0
    line_end_x = max(-SP_X_MM + MARGIN_MM, -D)   # stop at page edge or pivot
    lx0, ly0 = pt(0, 0)
    lx1, ly1 = pt(line_end_x, 0)
    c.setStrokeColorRGB(0.45, 0.45, 0.45)
    c.setLineWidth(0.5)
    c.setDash(4, 3)
    c.line(lx0, ly0, lx1, ly1)
    c.setDash()
    # Label near the spindle end of the line (always visible on the page)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.setFont("Helvetica", 6.5)
    if -D < -SP_X_MM + MARGIN_MM:
        # Pivot is off-page; place label just left of the spindle marker
        lx_label, ly_label = pt(-10, 1.5)
        c.drawRightString(lx_label, ly_label, f"← pivot  ({D:.0f} mm)")
    else:
        # Pivot fits on page; mark it with a small tick
        c.setStrokeColorRGB(0.45, 0.45, 0.45)
        c.setLineWidth(0.5)
        tx, ty = pt(-D, 0)
        c.line(tx, ty - 2 * mm, tx, ty + 2 * mm)
        c.drawCentredString(tx, ty - 4 * mm, "pivot")

    # ------------------------------------------------------------------
    # 4. Null-point alignment grids
    # ------------------------------------------------------------------
    GRID_REACH_MM  = 18.0   # how far tangential lines extend from null pt
    GRID_SPACING   = 2.0    # mm between parallel (radial-offset) grid lines
    N_GRID_LINES   = 5      # lines on each side of centre

    null_points = [
        (null1, r1, "Inner null  {:.3f} mm".format(r1)),
        (null2, r2, "Outer null  {:.3f} mm".format(r2)),
    ]

    for (nx, ny), r_null, label in null_points:
        # Unit vectors
        rad_x, rad_y = nx / r_null, ny / r_null        # radial (spindle→null)
        tan_x, tan_y = -ny / r_null, nx / r_null       # tangential (CCW)

        npt_x, npt_y = pt(nx, ny)

        # -- Parallel tangential lines (cartridge body guide) --
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.5)

        for j in range(-N_GRID_LINES, N_GRID_LINES + 1):
            off = j * GRID_SPACING
            ox = nx + rad_x * off
            oy = ny + rad_y * off
            lw = 0.7 if j == 0 else 0.3
            c.setLineWidth(lw)
            x0, y0 = pt(ox - tan_x * GRID_REACH_MM, oy - tan_y * GRID_REACH_MM)
            x1, y1 = pt(ox + tan_x * GRID_REACH_MM, oy + tan_y * GRID_REACH_MM)
            c.line(x0, y0, x1, y1)

        # -- Central radial line (spindle direction) --
        c.setLineWidth(0.7)
        x0, y0 = pt(nx - rad_x * GRID_REACH_MM, ny - rad_y * GRID_REACH_MM)
        x1, y1 = pt(nx + rad_x * GRID_REACH_MM, ny + rad_y * GRID_REACH_MM)
        c.line(x0, y0, x1, y1)

        # -- Target circle and dot --
        c.setStrokeColorRGB(0.75, 0, 0)
        c.setFillColorRGB(0.75, 0, 0)
        c.setLineWidth(0.5)
        c.circle(npt_x, npt_y, 2.0 * mm, stroke=1, fill=0)
        c.circle(npt_x, npt_y, 0.4 * mm, stroke=0, fill=1)

        # -- Label: placed just beyond the right end of the grid lines --
        # The tangent vector points leftward for both null points, so
        # the right end of the grid is in the -tangential direction.
        c.setFillColorRGB(0, 0, 0.6)
        c.setFont("Helvetica", 7)
        lx, ly = pt(nx - tan_x * (GRID_REACH_MM + 2), ny - tan_y * (GRID_REACH_MM + 2))
        c.drawString(lx, ly, label)

    # ------------------------------------------------------------------
    # 5. Title block (top of page)
    # ------------------------------------------------------------------
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(page_w / 2, page_h - 18 * mm,
                        f"Phono Cartridge Alignment Protractor")
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(page_w / 2, page_h - 25 * mm, alignment_name)

    params = [
        ("Pivot-to-spindle (D)", f"{D:.1f} mm"),
        ("Effective length (L)", f"{geo['L']:.2f} mm"),
        ("Offset angle (β)",      f"{geo['beta']:.2f}°"),
        ("Overhang (h = L − D)",  f"{geo['h']:.2f} mm"),
        ("Inner null radius",     f"{r1:.3f} mm"),
        ("Outer null radius",     f"{r2:.3f} mm"),
    ]
    c.setFont("Helvetica", 8)
    col_gap = 65 * mm
    base_y  = page_h - 32 * mm
    left_x  = page_w / 2 - col_gap
    for i, (k, v) in enumerate(params):
        row = i % 3
        col = i // 3
        x_label = left_x + col * col_gap
        y_row   = base_y - row * 5.5 * mm
        c.setFillColorRGB(0.3, 0.3, 0.3)
        c.drawString(x_label, y_row, k + ":")
        c.setFillColorRGB(0, 0, 0)
        c.drawString(x_label + 46 * mm, y_row, v)

    # ------------------------------------------------------------------
    # 6. Scale reference bar (bottom of page)
    # ------------------------------------------------------------------
    BAR_LEN_MM = 100.0
    bar_x = (page_w - BAR_LEN_MM * mm) / 2
    bar_y = 10 * mm

    c.setStrokeColorRGB(0, 0, 0)
    c.setFillColorRGB(0, 0, 0)
    c.setLineWidth(0.7)
    # Main bar
    c.line(bar_x, bar_y, bar_x + BAR_LEN_MM * mm, bar_y)
    # End ticks
    c.line(bar_x, bar_y - 2 * mm, bar_x, bar_y + 2 * mm)
    c.line(bar_x + BAR_LEN_MM * mm, bar_y - 2 * mm, bar_x + BAR_LEN_MM * mm, bar_y + 2 * mm)
    # 10 mm ticks
    c.setLineWidth(0.4)
    for j in range(1, int(BAR_LEN_MM / 10)):
        xj = bar_x + j * 10 * mm
        c.line(xj, bar_y - 1.2 * mm, xj, bar_y + 1.2 * mm)
    # 50 mm mid-tick
    c.setLineWidth(0.6)
    xm = bar_x + 50 * mm
    c.line(xm, bar_y - 1.8 * mm, xm, bar_y + 1.8 * mm)

    c.setFont("Helvetica", 7)
    c.drawString(bar_x, bar_y - 4.5 * mm, "0")
    c.drawCentredString(xm, bar_y - 4.5 * mm, "50 mm")
    c.drawRightString(bar_x + BAR_LEN_MM * mm, bar_y - 4.5 * mm, "100 mm")

    c.setFont("Helvetica-Oblique", 6.5)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.drawCentredString(page_w / 2, bar_y - 8.5 * mm,
                        "Print at 100% / actual size — do not scale to fit.  "
                        "Verify scale bar measures exactly 100 mm before use.")

    # ------------------------------------------------------------------
    # Instructions (between header and graphics)
    # ------------------------------------------------------------------
    # The params block ends at roughly page_h − 43 mm; the outer null
    # point reaches to about SP_Y_MM + r2 ≈ 155 mm from the bottom.
    # Centre the instruction block in that gap.
    instr_steps = [
        ("HOW TO USE", None),
        ("1.", "Place the protractor on the platter with the spindle through the centre hole."),
        ("2.", "Swing the tonearm to the inner null point — stylus tip must sit on the red dot."),
        ("3.", "Align the cartridge body parallel to the tangential grid lines."),
        ("4.", "Repeat at the outer null point.  Adjust overhang and/or azimuth, then repeat"
               " until the cartridge is parallel to the grid lines at both null points."),
    ]
    LINE_H    = 4.8 * mm
    INSTR_W   = 160 * mm                       # text column width
    instr_x   = (page_w - INSTR_W) / 2
    # Vertical centre of the blank gap
    gap_top_pt    = page_h - 43 * mm
    gap_bottom_pt = (SP_Y_MM + r2 + 8) * mm   # a little above the outer null
    instr_y = (gap_top_pt + gap_bottom_pt) / 2 + (len(instr_steps) * LINE_H) / 2

    for num, text in instr_steps:
        if text is None:
            # Section heading
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(page_w / 2, instr_y, num)
        else:
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColorRGB(0.3, 0.3, 0.3)
            c.drawString(instr_x, instr_y, num)
            c.setFont("Helvetica", 7.5)
            c.setFillColorRGB(0.2, 0.2, 0.2)
            c.drawString(instr_x + 7 * mm, instr_y, text)
        instr_y -= LINE_H
    # _draw_page ends here — caller is responsible for showPage() / save()


def draw_protractor_pdf(geo: dict, alignment_name: str, output_path: str):
    """Generate a single-page protractor PDF."""
    pdfcanvas, _, A4 = _require_reportlab()
    c = pdfcanvas.Canvas(output_path, pagesize=A4)
    _draw_page(c, geo, alignment_name)
    c.save()
    print(f"Saved: {output_path}")


def draw_all_pdf(D: float, output_path: str):
    """Generate a multi-page PDF with one page per alignment type."""
    pdfcanvas, _, A4 = _require_reportlab()
    c = pdfcanvas.Canvas(output_path, pagesize=A4)
    for alignment in ALIGNMENTS.values():
        geo = compute_geometry(D, alignment["r1"], alignment["r2"])
        _draw_page(c, geo, alignment["name"])
        c.showPage()
    c.save()
    print(f"Saved: {output_path}  ({len(ALIGNMENTS)} pages)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a 1:1 scale vinyl tonearm alignment protractor (A4 PDF).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python protractor.py 215
  python protractor.py 222.0 -a lofgren_b
  python protractor.py 211.5 -a stevenson -o stevenson_211.pdf
  python protractor.py 215 --all
  python protractor.py 215 --all -o all_alignments.pdf

Alignment types:
  baerwald   Lofgren A / Baerwald  – minimises RMS tracking distortion  [default]
  lofgren_b  Lofgren B             – minimises peak tracking distortion
  stevenson  Stevenson             – null at inner groove, minimises outer error
        """,
    )
    parser.add_argument(
        "distance",
        type=float,
        metavar="D",
        help="Pivot-to-spindle distance in mm (measure from tonearm pivot centre to spindle centre)",
    )
    parser.add_argument(
        "-a", "--alignment",
        choices=list(ALIGNMENTS.keys()),
        default="baerwald",
        metavar="TYPE",
        help="Alignment type: baerwald (default), lofgren_b, stevenson",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all three alignment types as a single multi-page PDF",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        metavar="FILE",
        help="Output PDF path (default: protractor_<type>_<D>mm.pdf  or  protractor_all_<D>mm.pdf)",
    )
    args = parser.parse_args()

    if args.distance <= 0:
        parser.error("Distance must be a positive number.")

    D = args.distance

    if args.all:
        output = args.output or f"protractor_all_{int(D)}mm.pdf"
        for alignment in ALIGNMENTS.values():
            geo = compute_geometry(D, alignment["r1"], alignment["r2"])
            print(f"\nAlignment       : {alignment['name']}")
            print(f"Effective length: {geo['L']:.2f} mm  |  "
                  f"Offset angle: {geo['beta']:.2f}°  |  Overhang: {geo['h']:.2f} mm")
        print()
        draw_all_pdf(D, output)
    else:
        alignment = ALIGNMENTS[args.alignment]
        output    = args.output or f"protractor_{args.alignment}_{int(D)}mm.pdf"
        geo       = compute_geometry(D, alignment["r1"], alignment["r2"])

        print(f"\nAlignment       : {alignment['name']}")
        print(f"Pivot-to-spindle: {geo['D']:.1f} mm  (input)")
        print(f"Effective length: {geo['L']:.2f} mm")
        print(f"Offset angle    : {geo['beta']:.2f}°")
        print(f"Overhang        : {geo['h']:.2f} mm")
        print(f"Null radii      : {geo['r1']:.3f} mm  /  {geo['r2']:.3f} mm")
        print(f"Null positions  : ({geo['null1'][0]:.2f}, {geo['null1'][1]:.2f}) mm")
        print(f"                  ({geo['null2'][0]:.2f}, {geo['null2'][1]:.2f}) mm\n")

        draw_protractor_pdf(geo, alignment["name"], output)


if __name__ == "__main__":
    main()
