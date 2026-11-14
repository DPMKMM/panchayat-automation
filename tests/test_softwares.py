"""End-to-end regression tests for the Softwares module in e-Panchayat Automation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import app
from core.branding import PLATFORM_NAME

client = TestClient(app)


def test_softwares_health_and_cards_wired():
    """Verify health check includes SOFTWARES and portal shell renders Softwares cards."""
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert "SOFTWARES" in health["modules"]

    html = client.get("/").text
    assert 'id="card-choose-softwares"' in html
    assert 'id="softwares-modules-section"' in html
    assert 'id="login-link-softwares"' in html
    assert 'id="btn-choose-softwares"' in html
    assert 'selectWorkspaceMode(\'softwares\')' in html
    assert 'id="software-search-input"' in html
    assert 'id="software-help-modal"' in html
    assert 'All (13)' in html
    assert '🔑 DSC &amp; Java (5)' in html
    assert '⌨️ Telugu Typing (2)' in html
    assert '🛠️ System &amp; Remote IT (2)' in html
    assert "TrustKey / mToken CryptoID" not in html
    assert "Baraha Telugu Software" not in html
    assert "AnyDesk Remote Desktop" not in html
    assert "Anu Script Manager" not in html


def test_softwares_route_direct_access():
    """Verify /softwares and /software routes render cleanly."""
    resp = client.get("/softwares")
    assert resp.status_code == 200
    html = resp.text
    assert 'id="card-choose-softwares"' in html
    assert 'id="softwares-modules-section"' in html
    assert 'Mantra MFS100 RD Service' in html

    resp2 = client.get("/software")
    assert resp2.status_code == 200
    assert 'id="softwares-modules-section"' in resp2.text


def test_all_13_software_cards_rendered():
    """Verify all 13 official software cards are present in the HTML."""
    html = client.get("/").text
    expected_softwares = [
        "Mantra MFS100 RD Service &amp; Driver",
        "Morpho Safran MSO 1300 E2/E3 RD Service",
        "Startek FM220 / FM220U RD Service",
        "SecuGen Hamster Pro 20 RD Service",
        "Java Runtime Environment 8 (JRE)",
        "ePass2003 / HYP2003 PKI Client",
        "WatchData ProxKey Token Driver",
        "NIC nicDSign Component (eGramSwaraj)",
        "UBD NIC DigiSigner Component",
        "Google Input Tools Telugu (Offline Installer)",
        "Official Telugu Fonts Pack (Pothana &amp; Gautami)",
        "Adobe Acrobat Reader DC",
        "Open Internet Explorer Utility (Windows 10 / 11)",
    ]
    for s in expected_softwares:
        assert s in html, f"Missing software card: {s}"

    assert "TrustKey / mToken CryptoID PKI Client" not in html
    assert "Baraha Telugu Software" not in html
    assert "AnyDesk Remote Desktop" not in html
    assert "Anu Script Manager" not in html


def test_softwares_subdomain_branding():
    """Verify custom domain branding when accessing via softwares.panchayatautomation.in."""
    resp = client.get("/", headers={"Host": "softwares.panchayatautomation.in"})
    assert resp.status_code == 200
    html = resp.text
    assert f'<title id="doc-page-title">Official Softwares | {PLATFORM_NAME}</title>' in html
    assert "e-Panchayat Official Softwares & Utilities" in html
    assert 'id="hero-console-chip" style="display:inline-flex;' in html


def test_all_1_click_download_links_wired():
    """Verify official direct 1-click download links are present in the HTML."""
    html = client.get("/softwares").text

    # External 1-click download links
    hyp2003_url = "https://www.vsign.in/vsign/repository/HYP2003-Setup-FIPS140-3.zip"
    proxkey_url = "https://www.vsign.in/vsign/repository/WD_PROXKey-FIPS140-3.zip"
    nicdsign_url = "https://egramswaraj.gov.in/FileRedirect.jsp?FD=nicDSign&name=nicDSign.zip"

    assert hyp2003_url in html
    assert proxkey_url in html
    assert nicdsign_url in html

    # Hosted 1-click download links (Static files & GitHub CDN Releases)
    assert "/static/softwares/UBD_newdigisigncomp.zip" in html
    assert "/static/softwares/GoogleInputTelugu.zip" in html
    assert "/static/softwares/OpenInternetExplorer.zip" in html
    assert "releases/download/softwares-v1/AdbeRdr11007_en_US.zip" in html
    assert "releases/download/softwares-v1/jdk-8u351-windows-x32bit.zip" in html
    assert "releases/download/softwares-v1/jdk-8u191-windows-x64.zip" in html

    # Ensure 1-click download attributes exist
    assert 'download="HYP2003-Setup-FIPS140-3.zip"' in html
    assert 'download="WD_PROXKey-FIPS140-3.zip"' in html
    assert 'download="nicDSign.zip"' in html
    assert 'download="UBD_newdigisigncomp.zip"' in html
    assert 'download="GoogleInputTelugu.zip"' in html
    assert 'download="OpenInternetExplorer.zip"' in html
    assert 'download="AdbeRdr11007_en_US.zip"' in html
    assert 'download="jdk-8u351-windows-x32bit.zip"' in html
    assert 'download="jdk-8u191-windows-x64.zip"' in html


def test_hosted_software_static_file_downloads():
    """Verify git-tracked hosted software packages are accessible and downloadable via static files."""
    # Test UBD_newdigisigncomp.zip
    resp_ubd = client.get("/static/softwares/UBD_newdigisigncomp.zip")
    assert resp_ubd.status_code == 200
    assert len(resp_ubd.content) == 159744

    # Test GoogleInputTelugu.zip
    resp_git = client.get("/static/softwares/GoogleInputTelugu.zip")
    assert resp_git.status_code == 200
    assert len(resp_git.content) == 9775875

    # Test OpenInternetExplorer.zip
    resp_ie = client.get("/static/softwares/OpenInternetExplorer.zip")
    assert resp_ie.status_code == 200
    assert len(resp_ie.content) == 4494

    # Test AdbeRdr11007_en_US.zip (Adobe Reader 11.0.07 offline setup on local disk)
    resp_adobe = client.get("/static/softwares/AdbeRdr11007_en_US.zip")
    assert resp_adobe.status_code == 200
    assert len(resp_adobe.content) == 74456741

    # Test jdk-8u351-windows-x32bit.zip (Java 8 32-bit offline setup)
    resp_java32 = client.get("/static/softwares/jdk-8u351-windows-x32bit.zip")
    assert resp_java32.status_code == 200
    assert len(resp_java32.content) == 167692349

    # Test jdk-8u191-windows-x64.zip (Java 8 64-bit offline setup)
    resp_java64 = client.get("/static/softwares/jdk-8u191-windows-x64.zip")
    assert resp_java64.status_code == 200
    assert len(resp_java64.content) == 215444577


def test_biometrics_cards_and_category_order_last():
    """Verify that Biometrics filter is last and Biometric driver cards appear at the end."""
    from bs4 import BeautifulSoup

    html = client.get("/softwares").text
    soup = BeautifulSoup(html, "html.parser")

    # 1. Verify category filter buttons order: Biometrics must be last
    buttons = [b.get_text(strip=True) for b in soup.select("#software-category-filters button")]
    assert buttons[-1] == "👆 Biometrics (4)"

    # 2. Verify software cards order: Biometric drivers must be at the end
    cards = [c.find("h3").get_text(strip=True) for c in soup.select("#softwares-grid .software-card")]
    assert len(cards) == 13
    biometric_cards = cards[-4:]
    assert biometric_cards == [
        "Mantra MFS100 RD Service & Driver",
        "Morpho Safran MSO 1300 E2/E3 RD Service",
        "Startek FM220 / FM220U RD Service",
        "SecuGen Hamster Pro 20 RD Service",
    ]

