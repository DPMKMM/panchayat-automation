"""Telangana e-Panchayat Monthly Activity Statement (MAS) Module.

Provides end-to-end automation, auditing, and official departmental reporting
for the Monthly Activity Statement (MAS) from the Telangana e-Panchayat portal.
"""

from mas.models import (
    DEFAULT_MAS_ACTIVITIES,
    DistrictMASReport,
    GPMASDetail,
    MandalMASSummary,
)
from mas.router import router

__all__ = [
    "DEFAULT_MAS_ACTIVITIES",
    "DistrictMASReport",
    "GPMASDetail",
    "MandalMASSummary",
    "router",
]
