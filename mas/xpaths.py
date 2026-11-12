"""XPath Registry & Portal Navigation Selectors for MAS Automation (GM-R 5.24 & GM-R 5.23).

All XPaths and frame selectors used during live EPTS scraping inside the shared
authenticated Playwright browser session are centralized here.
"""

from __future__ import annotations

# Root portal menu item
XPATH_GP_MONITORING_MENU = (
    "//a[normalize-space(.)='GP Monitoring'] | //input[@value='GP Monitoring'] | "
    "//a[contains(normalize-space(.), 'GP Monitoring')] | //li[contains(., 'GP Monitoring')]//a"
)

# Active report iframe inside EPTS Dashboard
XPATH_MY_IFRAME = "//iframe[@name='my-iframe' or @id='my-iframe' or contains(@src, 'PSPerformance')]"

# Master Section Accordion (GM-R 5)
XPATH_GMR5_ACCORDION = (
    "//a[contains(., 'GM-R 5.')] | //a[contains(., 'GM-R 5')] | //a[contains(., 'GM-R5')] | "
    "//*[contains(text(), 'Monthly Activity Statement Reports')] | //a[contains(., '5. Monthly Activity')]"
)

# Sub-Report 5.24 (17 MAS Indicators) & Sub-Report 5.23 (Births Register)
XPATH_GMR_524_LINK = (
    "//a[contains(@href, 'Rpt_MAS_DataEntry')] | "
    "//a[contains(., '5.24') or contains(., 'Data Entry Status')]"
)
XPATH_GMR_523_LINK = (
    "//a[contains(@href, 'rpt_Pi_BirthRegistrations')] | "
    "//a[contains(., '5.23') or contains(., 'No of Births') or contains(., 'Births Register') or contains(., 'Activity Statement Summary')]"
)

# Filter Controls inside GM-R 5.24 / 5.23 Frame
XPATH_DDL_MONTH = (
    "//select[@id='ContentPlaceHolder1_ddlMonth' or contains(@id, 'ddlMonth') or contains(@name, 'Month')]"
)
XPATH_DDL_YEAR = (
    "//select[@id='ContentPlaceHolder1_ddlYear' or contains(@id, 'ddlYear') or contains(@name, 'Year')]"
)
XPATH_BTN_SUBMIT = (
    "//input[@id='ContentPlaceHolder1_btnsubmit' or @id='ContentPlaceHolder1_btnSubmit' "
    "or @type='submit' or contains(@value, 'Submit')]"
)

# Report Data Tables
XPATH_GRIDVIEW1 = "//table[@id='ContentPlaceHolder1_GridView1']"
XPATH_GRIDVIEW2 = "//table[@id='ContentPlaceHolder1_GridView2']"

XPATH_REGISTRY = {
    "gp_monitoring_menu": XPATH_GP_MONITORING_MENU,
    "iframe": XPATH_MY_IFRAME,
    "gmr5_accordion": XPATH_GMR5_ACCORDION,
    "gmr_524_link": XPATH_GMR_524_LINK,
    "gmr_523_link": XPATH_GMR_523_LINK,
    "ddl_month": XPATH_DDL_MONTH,
    "ddl_year": XPATH_DDL_YEAR,
    "btn_submit": XPATH_BTN_SUBMIT,
    "gridview1": XPATH_GRIDVIEW1,
    "gridview2": XPATH_GRIDVIEW2,
}
