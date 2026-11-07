import sys
from playwright.sync_api import sync_playwright
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    page = browser.contexts[0].pages[0]
    iframe = page.frame('my-iframe')
    
    print('Clicking Chinthakani in Births table...')
    iframe.click("a[id*='lblLevelNameMandal_1']")
    print('Clicked! Waiting 6s...')
    time.sleep(6)
    
    tables = iframe.evaluate('''() => {
        return Array.from(document.querySelectorAll('table')).map((t, idx) => ({
            index: idx,
            id: t.id,
            rows: t.querySelectorAll('tr').length,
            sample: Array.from(t.querySelectorAll('tr')).slice(0, 4).map(r => Array.from(r.querySelectorAll('td, th')).map(c => c.innerText.trim()))
        }));
    }''')
    for t in tables:
        print(f"Table {t['index']}: ID={t['id']} | Rows={t['rows']}")
        for s in t['sample']:
            print("  ", s)
    
    back_btn = iframe.locator("input[value='Back'], #ContentPlaceHolder1_btnback").first
    print('Back button visible?', back_btn.is_visible())
