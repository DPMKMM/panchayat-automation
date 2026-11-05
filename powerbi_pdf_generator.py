"""Power BI PDF Generator module for PR & RD Analytics Portal.
Generates an official multi-page A4 Landscape Power BI Visual Report:
- Page 1: District Executive Dashboard (Mandal Abstract Table with Data Bars,
  Clustered DCB Column Chart, Percentage of Collection Ranking, Overall DCB Donut,
  and District Tax Collection % Radial Gauge).
- Pages 2 to N: Mandal-wise Executive Dashboards for all mandals in the district
  (GP Table with Data Bars, MANDAL % Gauge, GP Wise Collection % Chart,
  and Panchayat wise Demand, Collection, and Balance Chart).
Each page strictly fits onto a single A4 Landscape canvas (841.89 x 595.28 pt).
"""

from __future__ import annotations

import io
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib.utils import ImageReader

import tax_service

PAGE_W, PAGE_H = landscape(A4)  # 841.89 x 595.28 pt


def format_inr(val: float | int) -> str:
    """Format integer with Indian number grouping."""
    try:
        n = int(round(float(val)))
    except (ValueError, TypeError):
        return "0"
    s = str(abs(n))
    if len(s) <= 3:
        res = s
    else:
        last3 = s[-3:]
        rem = s[:-3]
        parts = []
        while len(rem) > 2:
            parts.append(rem[-2:])
            rem = rem[:-2]
        if rem:
            parts.append(rem)
        parts.reverse()
        res = ",".join(parts) + "," + last3
    return f"-{res}" if n < 0 else res


def get_pbi_heatmap_style(pct: float | int) -> tuple[str, str]:
    """Calculate heat map background color and contrasting text color matching Power BI conditional formatting.
    Gradient:
      0% - 25%: #D83B01 (Orange-Red) -> White text
      26% - 35%: #E27F05 (Bright Orange) -> Black text
      36% - 60%: #E9AD09 (Golden Amber) -> Black text
      61% - 100%: #107C41 (Forest Green) -> White text
    """
    try:
        p = max(0.0, min(100.0, float(pct)))
    except (ValueError, TypeError):
        p = 0.0

    c_min = (216, 59, 1)    # #D83B01
    c_mid = (233, 173, 9)   # #E9AD09
    c_max = (16, 124, 65)   # #107C41

    if p <= 50.0:
        t = p / 50.0
        rgb = tuple(int(c_min[i] + (c_mid[i] - c_min[i]) * t) for i in range(3))
    else:
        t = (p - 50.0) / 50.0
        rgb = tuple(int(c_mid[i] + (c_max[i] - c_mid[i]) * t) for i in range(3))

    bg_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    fg_hex = "#000000" if lum >= 138 else "#FFFFFF"
    return bg_hex, fg_hex


def make_pbi_databar(pct: float | int, width: float = 48.0, height: float = 9.5) -> Drawing:
    """Draw a soft-blue Power BI style horizontal data bar with bold percentage text."""
    try:
        p = max(0.0, min(100.0, float(pct)))
    except (ValueError, TypeError):
        p = 0.0
    d = Drawing(width, height)
    fill_w = max(1.0, min(width, width * (p / 100.0)))
    # Soft blue data bar
    d.add(Rect(0, 0.5, fill_w, height - 1.0, fillColor=colors.HexColor("#60A5FA"), strokeColor=None, rx=1, ry=1))
    # Text on top
    text_val = f"{p:.1f}" if p < 100 else "100"
    d.add(String(width - 2.0, 1.8, text_val, fontName="Helvetica-Bold", fontSize=6.2, textAnchor="end", fillColor=colors.HexColor("#0F172A")))
    return d


def create_gauge_img(pct: float | int, title: str, title_col: str = "#DC2626", min_val: str = "0", max_val: str = "100") -> ImageReader:
    """Render a semi-circle radial gauge matching Power BI Desktop visual."""
    fig, ax = plt.subplots(figsize=(2.5, 1.8), dpi=150)
    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-0.25, 1.35)
    ax.axis("off")

    # Background track arc
    bg_wedge = patches.Wedge((0, 0), 1.0, 0, 180, width=0.28, facecolor="#E9EDF2", edgecolor="none")
    ax.add_patch(bg_wedge)

    # Foreground progress arc
    p = max(0.0, min(100.0, float(pct)))
    theta1 = 180.0 - (p / 100.0) * 180.0
    val_wedge = patches.Wedge((0, 0), 1.0, theta1, 180, width=0.28, facecolor="#0078D4", edgecolor="none")
    ax.add_patch(val_wedge)

    # Title
    ax.text(0, 1.18, title, ha="center", va="center", fontsize=8.5, fontweight="bold", color=title_col)
    # Huge center number
    ax.text(0, 0.22, f"{p:.2f}", ha="center", va="center", fontsize=18, fontweight="bold", color="#2E0854")
    # Min / Max labels
    ax.text(-0.85, -0.10, min_val, ha="center", va="center", fontsize=8, fontweight="bold", color="#1E293B")
    ax.text(0.85, -0.10, max_val, ha="center", va="center", fontsize=8, fontweight="bold", color="#1E293B")

    plt.tight_layout(pad=0.1)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return ImageReader(buf)


def create_donut_img(demand: float, coll: float, bal: float) -> ImageReader:
    """Render the DCB breakdown donut chart with title on top and legend moved comfortably down."""
    fig, ax = plt.subplots(figsize=(2.5, 2.3), dpi=150)
    labels = ["Demand", "Collection", "Balance"]
    vals = [max(1.0, float(demand)), max(1.0, float(coll)), max(1.0, float(bal))]
    cols = ["#002060", "#008000", "#ED7D31"]
    wedges, _ = ax.pie(vals, colors=cols, startangle=90, wedgeprops=dict(width=0.45, edgecolor="w"))
    fig.suptitle("Overall DCB Breakdown", fontsize=8.2, fontweight="bold", y=0.98)
    ax.legend(
        wedges,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.05),
        ncol=3,
        fontsize=6.5,
        frameon=False,
        handlelength=1.0,
        handletextpad=0.35,
        columnspacing=0.9,
    )
    fig.subplots_adjust(top=0.82, bottom=0.04, left=0.04, right=0.96)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return ImageReader(buf)


def create_ranking_chart_img(names: list[str], pcts: list[float | int], title: str) -> ImageReader:
    """Render the single-series column chart sorted descending with values on top."""
    fig, ax = plt.subplots(figsize=(4.5, 2.3), dpi=150)
    max_p = max(pcts) if pcts else 100
    bars = ax.bar(names, pcts, color="#0078D4", width=0.65)
    ax.set_ylim(0, max(100, max_p) * 1.18)
    ax.set_title(title, fontsize=8, fontweight="bold", pad=6)
    fsize = 5.0 if len(names) > 25 else 5.8 if len(names) > 15 else 6.5
    ax.tick_params(axis="x", rotation=50, labelsize=fsize)
    ax.tick_params(axis="y", labelsize=6.5)
    for bar in bars:
        y = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2.0, y + 1.2, f"{int(round(y))}", ha="center", va="bottom", fontsize=5.0 if len(names) > 25 else 5.8, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.subplots_adjust(bottom=0.34)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return ImageReader(buf)


def create_clustered_chart_img(names: list[str], d_vals: list[float], c_vals: list[float], b_vals: list[float], title: str, cols: list[str]) -> ImageReader:
    """Render the 3-series clustered column chart."""
    fig, ax = plt.subplots(figsize=(5.2, 3.1), dpi=150)
    x = np.arange(len(names))
    w = 0.26
    # Convert to Lakhs or Crores for cleaner Y-axis scale
    max_v = max(d_vals + c_vals + b_vals) if (d_vals and c_vals and b_vals) else 1
    if max_v >= 10_000_000:
        scale = 10_000_000.0
        y_label = "In Crores (₹)"
    elif max_v >= 100_000:
        scale = 100_000.0
        y_label = "In Lakhs (₹)"
    else:
        scale = 1.0
        y_label = "Amount (₹)"

    d_scaled = [v / scale for v in d_vals]
    c_scaled = [v / scale for v in c_vals]
    b_scaled = [v / scale for v in b_vals]

    ax.bar(x - w, d_scaled, width=w, label="Demand", color=cols[0])
    ax.bar(x, c_scaled, width=w, label="Collection", color=cols[1])
    ax.bar(x + w, b_scaled, width=w, label="Balance", color=cols[2])

    ax.set_title(title, loc="left", fontsize=8.5, fontweight="bold", pad=6)
    ax.set_xticks(x)
    fsize = 4.8 if len(names) > 28 else 5.8 if len(names) > 18 else 6.5
    ax.set_xticklabels(names, rotation=50, ha="right", fontsize=fsize)
    ax.set_ylabel(y_label, fontsize=6.5)
    ax.tick_params(axis="y", labelsize=6.5)
    ax.legend(loc="upper right", fontsize=6.5, ncol=3, frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.subplots_adjust(bottom=0.34)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return ImageReader(buf)


def draw_district_page(c: canvas.Canvas, district_name: str, data: dict[str, Any]) -> None:
    """Render Page 1: District Executive Power BI Dashboard."""
    s = data["summary"]
    mandals = data.get("mandal_abstract", [])
    tot_pct = float(s.get("overall_percentage", 0))

    # Top Header Banner (Soft Blue)
    c.setFillColor(colors.HexColor("#D2E3FC"))
    c.setStrokeColor(colors.HexColor("#7FA4D7"))
    c.rect(20, 550, 802, 32, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(20 + 802 / 2.0, 561, f"DEMAND, COLLECTION, BALANCE OF {district_name.upper()} DISTRICT")

    # Card 1 (Top Left): Mandal Summary Table (with Data Bars)
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(20, 260, 385, 278, fill=1, stroke=1)

    # Sort mandals ascending by percentage
    sorted_m = sorted(mandals, key=lambda m: float(m.get("percentage", 0)))
    table_data = [["Mandal Name", "GPs", "Demand", "Collection", "Balance", "%"]]
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#000000")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-2, -1), "RIGHT"),
        ("ALIGN", (-1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
        ("TOPPADDING", (0, 0), (-1, -1), 0.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
        ("TEXTCOLOR", (3, 1), (3, -1), colors.HexColor("#107C41")),  # Collection column green
        ("TEXTCOLOR", (4, 1), (4, -1), colors.HexColor("#D83B01")),  # Balance column orange
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),  # Total row
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]

    for idx, m in enumerate(sorted_m, start=1):
        p = float(m.get("percentage", 0))
        bg_hex, fg_hex = get_pbi_heatmap_style(p)
        table_data.append([
            m.get("mandal", ""),
            str(m.get("total_gps", "")),
            format_inr(m.get("demand_total", 0)),
            format_inr(m.get("collection_total", 0)),
            format_inr(m.get("balance_total", 0)),
            f"{p:.1f}%",
        ])
        style_cmds.append(("BACKGROUND", (5, idx), (5, idx), colors.HexColor(bg_hex)))
        style_cmds.append(("TEXTCOLOR", (5, idx), (5, idx), colors.HexColor(fg_hex)))
        style_cmds.append(("FONTNAME", (5, idx), (5, idx), "Helvetica-Bold"))

    # Total row
    tot_row_idx = len(table_data)
    tot_bg, tot_fg = get_pbi_heatmap_style(tot_pct)
    table_data.append([
        "Total",
        str(s.get("total_gps", "")),
        format_inr(s.get("total_demand", 0)),
        format_inr(s.get("total_collection", 0)),
        format_inr(s.get("total_balance", 0)),
        f"{tot_pct:.1f}%",
    ])
    style_cmds.append(("BACKGROUND", (5, tot_row_idx), (5, tot_row_idx), colors.HexColor(tot_bg)))
    style_cmds.append(("TEXTCOLOR", (5, tot_row_idx), (5, tot_row_idx), colors.HexColor(tot_fg)))
    style_cmds.append(("FONTNAME", (5, tot_row_idx), (5, tot_row_idx), "Helvetica-Bold"))

    n_rows = len(table_data)
    row_h = 278.0 / n_rows
    fsize = 6.0 if n_rows > 25 else 6.6
    style_cmds.append(("FONTSIZE", (0, 0), (-1, -1), fsize))

    t_style = TableStyle(style_cmds)
    col_w = [96, 26, 73, 73, 73, 44]
    table = Table(table_data, colWidths=col_w, rowHeights=[row_h] * n_rows, style=t_style)
    table.wrapOn(c, 385, 278)
    table.drawOn(c, 20, 260)

    # Card 2 (Top Right): Demand, Collection and Balance by Mandal Clustered Column
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(415, 260, 407, 278, fill=1, stroke=1)

    m_names_alpha = sorted(mandals, key=lambda m: m.get("mandal", ""))
    names = [m.get("mandal", "") for m in m_names_alpha]
    d_vals = [float(m.get("demand_total", 0)) for m in m_names_alpha]
    c_vals = [float(m.get("collection_total", 0)) for m in m_names_alpha]
    b_vals = [float(m.get("balance_total", 0)) for m in m_names_alpha]
    img_clustered = create_clustered_chart_img(names, d_vals, c_vals, b_vals, "Demand, Collection and Balance by Mandal", ["#0078D4", "#107C41", "#D83B01"])
    c.drawImage(img_clustered, 417, 262, width=403, height=274)

    # Card 3 (Bottom Left): PERCENTAGE OF COLLECTION BY MANDAL
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(20, 16, 360, 234, fill=1, stroke=1)
    m_ranked = sorted(mandals, key=lambda m: float(m.get("percentage", 0)), reverse=True)
    r_names = [m.get("mandal", "") for m in m_ranked]
    r_pcts = [float(m.get("percentage", 0)) for m in m_ranked]
    img_ranking = create_ranking_chart_img(r_names, r_pcts, "PERCENTAGE OF COLLECTION BY MANDAL")
    c.drawImage(img_ranking, 22, 18, width=356, height=230)

    # Card 4 (Bottom Middle): Overall DCB Breakdown Donut
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(390, 16, 210, 234, fill=1, stroke=1)
    img_donut = create_donut_img(float(s.get("total_demand", 0)), float(s.get("total_collection", 0)), float(s.get("total_balance", 0)))
    c.drawImage(img_donut, 392, 18, width=206, height=230)

    # Card 5 (Bottom Right): DISTRICT TAX COLLECTION % Gauge
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(610, 16, 212, 234, fill=1, stroke=1)
    img_gauge = create_gauge_img(tot_pct, "DISTRICT TAX COLLECTION %", title_col="#DC2626", min_val="0", max_val="100")
    c.drawImage(img_gauge, 612, 24, width=208, height=216)


def draw_mandal_page(c: canvas.Canvas, mandal_name: str, m_data: dict[str, Any]) -> None:
    """Render a Mandal Executive Power BI Dashboard page."""
    s = m_data["summary"]
    gps = m_data.get("records", [])
    m_pct = float(s.get("overall_percentage", 0))

    # Top Header Banner (Pastel Yellow with Red Title & Slicer)
    c.setFillColor(colors.HexColor("#FEF9C3"))
    c.setStrokeColor(colors.HexColor("#FACC15"))
    c.rect(20, 550, 802, 32, fill=1, stroke=1)

    c.setFillColor(colors.HexColor("#DC2626"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(32, 561, f"DEMAND - COLLECTION - BALANCE OF {mandal_name.upper()} MANDAL")

    # Slicer badge on top right
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#94A3B8"))
    c.roundRect(680, 555, 132, 22, 3, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(692, 562, f"{mandal_name}   ∨")

    # Left Column (width = 320 pt):
    # Top Card: GP DCB Table with Data Bars
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(20, 192, 320, 346, fill=1, stroke=1)

    sorted_gps = sorted(gps, key=lambda r: float(r.get("calc_percentage", r.get("percentage", 0))))
    table_data = [["Panchayat", "Demand", "Collection", "Balance", "%"]]
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#000000")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-2, -1), "RIGHT"),
        ("ALIGN", (-1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.2),
        ("TOPPADDING", (0, 0), (-1, -1), 0.3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.3),
        ("TEXTCOLOR", (2, 1), (2, -1), colors.HexColor("#107C41")),
        ("TEXTCOLOR", (3, 1), (3, -1), colors.HexColor("#D83B01")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]

    for idx, r in enumerate(sorted_gps, start=1):
        p = float(r.get("calc_percentage", r.get("percentage", 0)))
        bg_hex, fg_hex = get_pbi_heatmap_style(p)
        table_data.append([
            r.get("panchayat", ""),
            format_inr(r.get("demand_total", 0)),
            format_inr(r.get("collection_total", 0)),
            format_inr(r.get("balance_total", 0)),
            f"{p:.1f}%",
        ])
        style_cmds.append(("BACKGROUND", (4, idx), (4, idx), colors.HexColor(bg_hex)))
        style_cmds.append(("TEXTCOLOR", (4, idx), (4, idx), colors.HexColor(fg_hex)))
        style_cmds.append(("FONTNAME", (4, idx), (4, idx), "Helvetica-Bold"))

    # Total row
    tot_row_idx = len(table_data)
    m_tot_bg, m_tot_fg = get_pbi_heatmap_style(m_pct)
    table_data.append([
        "Total",
        format_inr(s.get("total_demand", 0)),
        format_inr(s.get("total_collection", 0)),
        format_inr(s.get("total_balance", 0)),
        f"{m_pct:.1f}%",
    ])
    style_cmds.append(("BACKGROUND", (4, tot_row_idx), (4, tot_row_idx), colors.HexColor(m_tot_bg)))
    style_cmds.append(("TEXTCOLOR", (4, tot_row_idx), (4, tot_row_idx), colors.HexColor(m_tot_fg)))
    style_cmds.append(("FONTNAME", (4, tot_row_idx), (4, tot_row_idx), "Helvetica-Bold"))

    n_rows = len(table_data)
    row_h = 346.0 / n_rows
    fsize = 5.2 if n_rows > 30 else 6.2
    style_cmds.append(("FONTSIZE", (0, 0), (-1, -1), fsize))

    t_style = TableStyle(style_cmds)
    col_w = [106, 58, 58, 58, 40]
    table = Table(table_data, colWidths=col_w, rowHeights=[row_h] * n_rows, style=t_style)
    table.wrapOn(c, 320, 346)
    table.drawOn(c, 20, 192)

    # Bottom Card: MANDAL % Gauge
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(20, 16, 320, 166, fill=1, stroke=1)
    img_gauge = create_gauge_img(m_pct, "MANDAL %", title_col="#0F172A", min_val="0.00", max_val="100.00")
    c.drawImage(img_gauge, 45, 18, width=270, height=162)

    # Right Column (width = 472 pt):
    # Top Card: GP Wise Collection percentage
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(350, 280, 472, 258, fill=1, stroke=1)

    gp_ranked = sorted(gps, key=lambda r: float(r.get("calc_percentage", r.get("percentage", 0))), reverse=True)
    gp_names = [r.get("panchayat", "") for r in gp_ranked]
    gp_pcts = [float(r.get("calc_percentage", r.get("percentage", 0))) for r in gp_ranked]
    img_ranking = create_ranking_chart_img(gp_names, gp_pcts, "GP Wise Collection percentage")
    c.drawImage(img_ranking, 352, 282, width=468, height=254)

    # Bottom Card: Panchayat wise Demand, Collection and Balance (Demand=Red, Coll=Green, Bal=Blue)
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(350, 16, 472, 254, fill=1, stroke=1)

    gp_alpha = sorted(gps, key=lambda r: r.get("panchayat", ""))
    names = [r.get("panchayat", "") for r in gp_alpha]
    d_vals = [float(r.get("demand_total", 0)) for r in gp_alpha]
    c_vals = [float(r.get("collection_total", 0)) for r in gp_alpha]
    b_vals = [float(r.get("balance_total", 0)) for r in gp_alpha]
    img_clustered = create_clustered_chart_img(names, d_vals, c_vals, b_vals, "Panchayat wise Demand, Collection and Balance", ["#DC2626", "#16A34A", "#2563EB"])
    c.drawImage(img_clustered, 352, 18, width=468, height=250)


def generate_powerbi_pdf(
    district_name: str = "District",
    mandal_name: Optional[str] = None,
    output_path_or_buffer: Any = None,
) -> bytes:
    """Generate the Power BI A4 Landscape PDF Report:
    - If district level: Page 1 (District) + Pages 2 to 21 (All Mandals).
    - If single mandal: Page 1 (that Mandal).
    """
    buffer = io.BytesIO()
    target = output_path_or_buffer if isinstance(output_path_or_buffer, (str, Path)) else buffer
    c = canvas.Canvas(str(target) if isinstance(target, (str, Path)) else target, pagesize=landscape(A4))

    is_single_mandal = bool(mandal_name and mandal_name.strip().lower() not in ("all", "all mandals", ""))

    if is_single_mandal and mandal_name:
        # Generate single mandal report (1 page)
        m_data = tax_service.get_filtered_data(district_name, mandal_name)
        draw_mandal_page(c, mandal_name.strip().title(), m_data)
        c.showPage()
    else:
        # Generate District Report (Page 1) + All Mandals (Pages 2 to 21)
        dist_data = tax_service.get_filtered_data(district_name, "all")
        draw_district_page(c, district_name.strip().title(), dist_data)
        c.showPage()

        # Load all mandals in this district (sorted alphabetically)
        mandals = dist_data.get("mandal_abstract", [])
        m_names = sorted([m.get("mandal") for m in mandals if m.get("mandal")])
        for m_name in m_names:
            m_data = tax_service.get_filtered_data(district_name, m_name)
            draw_mandal_page(c, m_name.strip().title(), m_data)
            c.showPage()

    c.save()

    if isinstance(target, (str, Path)):
        return Path(target).read_bytes()
    return buffer.getvalue()


def get_or_generate_powerbi_pdf(
    district_name: str = "District",
    mandal_name: Optional[str] = None,
    force_regenerate: bool = True,
) -> tuple[str, bytes]:
    """Return filename and bytes of the Power BI report for district or mandal."""
    safe_dist = district_name.strip().replace(" ", "_").title()
    is_single_mandal = bool(mandal_name and mandal_name.strip().lower() not in ("all", "all mandals", ""))
    safe_mandal = f"_{mandal_name.strip().replace(' ', '_').title()}" if (is_single_mandal and mandal_name) else ""

    india_now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    date_str = india_now.strftime("%d-%m-%Y")

    import sys
    base_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    reports_dir = base_dir / "data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    pdf_filename = f"{safe_dist}{safe_mandal}_PowerBI_DCB_Report_{date_str}.pdf"
    cache_path = reports_dir / f"{safe_dist}{safe_mandal}_PowerBI_DCB_Report_{date_str}_v5.pdf"

    if not force_regenerate and cache_path.exists() and cache_path.stat().st_size > 10_000:
        return pdf_filename, cache_path.read_bytes()

    content = generate_powerbi_pdf(district_name, mandal_name, output_path_or_buffer=cache_path)
    return pdf_filename, content
