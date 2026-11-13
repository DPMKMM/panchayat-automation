import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def test_subtext_removed_from_portal_shell():
    portal_html = (ROOT / "templates" / "portal_shell.html").read_text(encoding="utf-8")
    assert "Zero Duplicate Login • Reuses active Departmental Playwright session to download GM-R 1.2.7 daily raw files." not in portal_html, \
        "The deprecated zero duplicate login text must be removed from portal_shell.html"

def test_progress_cards_present_across_all_modules():
    portal_html = (ROOT / "templates" / "portal_shell.html").read_text(encoding="utf-8")
    mas_views = (ROOT / "mas" / "views.py").read_text(encoding="utf-8")

    # 1. Automated Multi-Days DSR
    assert 'id="auto-multi-progress-card"' in portal_html
    # 2. Inspections
    assert 'id="insp-progress-strip"' in portal_html
    # 3. Daily DSR
    assert 'id="auto-daily-progress-card"' in portal_html
    # 4. GP Balance Entry
    assert 'id="balance-progress-card"' in portal_html
    # 5. House Tax DCB
    assert 'id="tax-progress-card"' in portal_html
    # 6. MAS
    assert 'id="mas-progress-card"' in mas_views

def test_progress_bar_styling_matches_reference():
    portal_html = (ROOT / "templates" / "portal_shell.html").read_text(encoding="utf-8")
    common_css = (ROOT / "static" / "css" / "common.css").read_text(encoding="utf-8")

    # Check common CSS definitions
    assert ".robot-progress-card" in common_css
    assert "border: 1.5px solid #38bdf8" in common_css
    assert "linear-gradient(90deg, #0284c7, #10b981)" in common_css
    assert ".progress-pct-badge" in common_css
    assert ".robot-sonar-dot" in common_css

    # Check that progress fills have gradient across modules in portal_shell
    assert "linear-gradient(90deg, #0284c7, #10b981)" in portal_html

def test_download_buttons_and_icons_constrained():
    portal_html = (ROOT / "templates" / "portal_shell.html").read_text(encoding="utf-8")
    multiday_html = (ROOT / "templates" / "multiday_dsr.html").read_text(encoding="utf-8")

    # Check button inline styling in portal_shell
    assert 'id="btn-auto-multi-dl-full-pdf"' in portal_html
    assert 'id="btn-auto-multi-dl-excel"' in portal_html
    assert 'id="btn-auto-multi-dl-dist-pdf"' in portal_html

    # Ensure SVGs inside download buttons have explicit inline width/height constraints
    for html in [portal_html, multiday_html]:
        assert 'width="16"' in html or 'width="15"' in html
        assert 'max-width:16px' in html or 'max-width:15px' in html
