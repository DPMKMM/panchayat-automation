# DCB module

This package owns live House Tax Demand, Collection, and Balance retrieval and report generation.

- `tax_service.py` fetches and parses live e-Panchayat data in memory.
- `dcb_pdf_generator.py` creates the official district PDF.
- `powerbi_pdf_generator.py` creates the visual analytics PDF.
- `tax_dcb_html.py` contains the standalone DCB screen template retained with the module.

Runtime downloads and generated reports are written under the configured `DATA_DIR` using `shared.paths`.
