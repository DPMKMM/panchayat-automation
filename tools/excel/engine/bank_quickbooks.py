"""
Bank & QuickBooks Financial Tools
Supports:
  - Statement to Excel / CSV
  - CSV to QBO (QuickBooks Online WebConnect OFX)
  - CSV to IIF (QuickBooks Desktop Interchange Format)
  - OFX to Excel / CSV
"""

import os
import re
import csv
import datetime
from pathlib import Path
from typing import List, Dict, Any

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def parse_bank_statement_lines(text_lines: List[str]) -> List[Dict[str, str]]:
    """Intelligently detects Date, Description, Debit/Credit, and Balance from statement lines."""
    transactions = []
    # Regex pattern for typical dates: DD/MM/YYYY, MM/DD/YYYY, DD-MMM-YYYY, YYYY-MM-DD
    date_regex = re.compile(r'(\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{1,2}-[A-Za-z]{3}-\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b)')
    # Currency pattern: 1,234.56 or 1234.56
    amount_regex = re.compile(r'[\d,]+\.\d{2}')

    for line in text_lines:
        line = line.strip()
        if not line:
            continue
        date_match = date_regex.search(line)
        if not date_match:
            continue

        tx_date = date_match.group(0)
        # Find all monetary amounts in the line
        amounts = amount_regex.findall(line)
        if not amounts:
            continue

        # Text between date and first amount is typically the description
        line_after_date = line[date_match.end():]
        first_amt = amounts[0]
        desc_part = line_after_date[:line_after_date.find(first_amt)].strip()
        desc = re.sub(r'\s{2,}', ' ', desc_part) or "Transaction"

        debit = ""
        credit = ""
        balance = ""

        if len(amounts) == 1:
            # Check for DR/CR indicators
            if 'dr' in line.lower() or 'debit' in line.lower() or '-' in line:
                debit = amounts[0]
            else:
                credit = amounts[0]
        elif len(amounts) == 2:
            debit = amounts[0]
            balance = amounts[1]
        elif len(amounts) >= 3:
            debit = amounts[0]
            credit = amounts[1]
            balance = amounts[2]

        transactions.append({
            "Date": tx_date,
            "Description": desc,
            "Debit": debit,
            "Credit": credit,
            "Balance": balance
        })

    return transactions


def statement_to_excel(src_path: str, dest_path: str) -> None:
    """Parses bank statement text/CSV into a clean, formatted Excel ledger."""
    with open(src_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    txs = parse_bank_statement_lines(lines)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Bank Statement"

    headers = ["Date", "Description", "Debit / Withdrawal", "Credit / Deposit", "Balance"]
    ws.append(headers)

    # Style header
    fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center")

    for t in txs:
        ws.append([t["Date"], t["Description"], t["Debit"], t["Credit"], t["Balance"]])

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    wb.save(dest_path)


def statement_to_csv(src_path: str, dest_path: str) -> None:
    with open(src_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    txs = parse_bank_statement_lines(lines)

    with open(dest_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Description", "Debit", "Credit", "Balance"])
        for t in txs:
            writer.writerow([t["Date"], t["Description"], t["Debit"], t["Credit"], t["Balance"]])


def csv_to_qbo(src_path: str, dest_path: str, account_id: str = "123456789") -> None:
    """Converts a CSV of bank transactions into QuickBooks Online WebConnect (.qbo) format."""
    tx_list = []
    with open(src_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 2:
        raise ValueError("CSV must contain a header and at least one transaction row.")

    headers = [h.strip().lower() for h in rows[0]]
    date_idx = next((i for i, h in enumerate(headers) if 'date' in h), 0)
    desc_idx = next((i for i, h in enumerate(headers) if any(k in h for k in ['desc', 'memo', 'detail', 'payee', 'name'])), 1)
    amt_idx = next((i for i, h in enumerate(headers) if 'amount' in h), None)
    debit_idx = next((i for i, h in enumerate(headers) if 'debit' in h or 'withdrawal' in h), None)
    credit_idx = next((i for i, h in enumerate(headers) if 'credit' in h or 'deposit' in h), None)

    today = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    qbo_lines = [
        "OFXHEADER:100",
        "DATA:OFXSGML",
        "VERSION:102",
        "SECURITY:NONE",
        "ENCODING:USASCII",
        "CHARSET:1252",
        "COMPRESSION:NONE",
        "OLDFILEUID:NONE",
        "NEWFILEUID:NONE",
        "",
        "<OFX>",
        "<SIGNONMSGSRSV1>",
        "<SONRS>",
        "<STATUS><CODE>0<SEVERITY>INFO</STATUS>",
        f"<DTSERVER>{today}",
        "<LANGUAGE>ENG",
        "<FI><ORG>Bank<FID>12345</FI>",
        "</SONRS>",
        "</SIGNONMSGSRSV1>",
        "<BANKMSGSRSV1>",
        "<STMTTRNRS>",
        "<TRNUID>1",
        "<STATUS><CODE>0<SEVERITY>INFO</STATUS>",
        "<STMTRS>",
        "<CURDEF>USD",
        f"<BANKACCTFROM><BANKID>123456789<ACCTID>{account_id}<ACCTTYPE>CHECKING</BANKACCTFROM>",
        "<BANKTRANLIST>",
        f"<DTSTART>{today}",
        f"<DTEND>{today}"
    ]

    for idx, r in enumerate(rows[1:], 1):
        if not any(r): continue
        dt_raw = re.sub(r'\D', '', str(r[date_idx]))[:8] if date_idx < len(r) else "20260101"
        if len(dt_raw) < 8: dt_raw = "20260101"
        desc = r[desc_idx] if desc_idx < len(r) else f"Tx {idx}"

        amount = 0.0
        if amt_idx is not None and amt_idx < len(r):
            try: amount = float(re.sub(r'[^\d.-]', '', r[amt_idx]))
            except ValueError: amount = 0.0
        else:
            deb = float(re.sub(r'[^\d.-]', '', r[debit_idx])) if (debit_idx and debit_idx < len(r) and r[debit_idx]) else 0.0
            crd = float(re.sub(r'[^\d.-]', '', r[credit_idx])) if (credit_idx and credit_idx < len(r) and r[credit_idx]) else 0.0
            amount = crd if crd > 0 else -deb

        trntype = "CREDIT" if amount >= 0 else "DEBIT"
        qbo_lines.extend([
            "<STMTTRN>",
            f"<TRNTYPE>{trntype}",
            f"<DTPOSTED>{dt_raw}",
            f"<TRNAMT>{amount:.2f}",
            f"<FITID>{idx}-{dt_raw}",
            f"<NAME>{desc[:32]}",
            f"<MEMO>{desc[:64]}",
            "</STMTTRN>"
        ])

    qbo_lines.extend([
        "</BANKTRANLIST>",
        "<LEDGERBAL><BALAMT>0.00<DTASOF>" + today + "</LEDGERBAL>",
        "</STMTRS>",
        "</STMTTRNRS>",
        "</BANKMSGSRSV1>",
        "</OFX>"
    ])

    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(qbo_lines))


def csv_to_iif(src_path: str, dest_path: str) -> None:
    """Converts CSV bank transactions into QuickBooks Desktop (.iif) format."""
    with open(src_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 2:
        raise ValueError("CSV must contain a header and at least one transaction row.")

    iif_lines = [
        "!TRNS\tTRNSID\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tDOCNUM\tMEMO",
        "!SPL\tSPLID\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tDOCNUM\tMEMO",
        "!ENDTRNS"
    ]

    for idx, r in enumerate(rows[1:], 1):
        if not any(r): continue
        dt = r[0] if len(r) > 0 else "01/01/2026"
        desc = r[1] if len(r) > 1 else f"Tx {idx}"
        amt = r[2] if len(r) > 2 else "0.00"

        iif_lines.append(f"TRNS\t{idx}\tCHECK\t{dt}\tBank Account\t{desc}\t{amt}\t\t{desc}")
        iif_lines.append(f"SPL\t{idx}\tCHECK\t{dt}\tExpense Account\t{desc}\t-{amt}\t\t{desc}")
        iif_lines.append("ENDTRNS")

    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(iif_lines))


def ofx_to_excel(src_path: str, dest_path: str) -> None:
    """Parses OFX / QBO bank files into clean Excel sheet."""
    with open(src_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    tx_blocks = re.findall(r'<STMTTRN>(.*?)</STMTTRN>', content, re.DOTALL | re.IGNORECASE)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "OFX Transactions"

    headers = ["Type", "Date", "Amount", "FITID", "Name", "Memo"]
    ws.append(headers)

    fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
    font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font

    def get_tag(block, tag):
        m = re.search(rf'<{tag}>([^<\r\n]+)', block, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    for block in tx_blocks:
        trntype = get_tag(block, "TRNTYPE")
        dtposted = get_tag(block, "DTPOSTED")
        trnamt = get_tag(block, "TRNAMT")
        fitid = get_tag(block, "FITID")
        name = get_tag(block, "NAME")
        memo = get_tag(block, "MEMO")
        ws.append([trntype, dtposted, trnamt, fitid, name, memo])

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    wb.save(dest_path)


def ofx_to_csv(src_path: str, dest_path: str) -> None:
    tmp_xlsx = dest_path + ".tmp.xlsx"
    ofx_to_excel(src_path, tmp_xlsx)
    from tools.excel.engine.converters_from_excel import excel_to_csv
    excel_to_csv(tmp_xlsx, dest_path)
    if os.path.exists(tmp_xlsx):
        os.remove(tmp_xlsx)
