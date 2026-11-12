"""Gram Panchayat Inspections Automation Module (GM-R 39.1).

Sub-package for scraping, consolidating, and reporting GM-R 39.1 MPO/MPDO/DLPO/DPO/CEO
inspection data across From-To week ranges with strict 'Submitted' status filtering.
"""

from inspections.models import (
    DESIGNATION_SPECS,
    SUPPORTED_DESIGNATIONS,
    InspectionAbstractRow,
    InspectionRecord,
    InspectionReport,
    compute_designation_target,
    get_designation_spec,
)

__all__ = [
    "DESIGNATION_SPECS",
    "SUPPORTED_DESIGNATIONS",
    "InspectionAbstractRow",
    "InspectionRecord",
    "InspectionReport",
    "compute_designation_target",
    "get_designation_spec",
]
