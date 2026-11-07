"""Data models for Monthly Activity Statement (MAS) and Births Register (GM-R 5) Module.

Provides structured representations for:
- GM-R 5.24: Gram Panchayat & Mandal Monthly Activity Statement Metrics (17 Official Activities)
- GM-R 5.23: Gram Panchayat & Mandal Births Registration Metrics
- District MAS Master Report: Combined executive roll-up for departmental compliance
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# The 17 Official Telangana e-Panchayat Monthly Activity Statement (GM-R 5.24) Indicators
MAS_5_24_ACTIVITIES: list[str] = [
    "Nursery",
    "Plantation",
    "Vaikunta Dhamam",
    "Dump Yard",
    "Water Supply",
    "GP Meeting",
    "Gram Sabha",
    "Record Maintenance",
    "Approvals and Certificates",
    "Deaths",
    "Recipts",
    "Expenditure",
    "Cheque Details",
    "Salary Details",
    "VWSC &EGS Bank Balance",
    "MGNRE Bank Balance",
    "Payment of Electricity",
]

DEFAULT_MAS_ACTIVITIES = MAS_5_24_ACTIVITIES

# The 18 Official Consolidated Indicators (17 MAS 5.24 Activities + GM-R 5.23 Birth Details)
# Matches the Departmental Executive Matrix layout exactly
OFFICIAL_MAS_REPORT_ACTIVITIES: list[str] = [
    "Nursery",
    "Plantation",
    "Vaikunta dhamam",
    "Dump yard",
    "Water supply",
    "GP Meetings",
    "Gram Sabha",
    "Record Maintenance",
    "Approvals and Certificates",
    "Deaths",
    "Recipts",
    "Expenditure",
    "Cheque details",
    "Salary details",
    "VWSC & EGS Bank balance",
    "MGNREGS Bank balance",
    "Payment of Electricity",
    "Birth details",
]


def make_lookup_key(mandal_name: str, gp_name: str) -> str:
    """Creates a canonical normalized unique lookup key for joining Mandal + Gram Panchayat."""
    import re
    m_clean = re.sub(r"[^a-zA-Z0-9]", "", mandal_name).upper()
    g_clean = re.sub(r"[^a-zA-Z0-9]", "", gp_name).upper()
    return f"{m_clean}::{g_clean}"


def normalize_activity_key(name: str) -> str:
    """Normalizes any activity header, span ID, or column name to canonical official key."""
    import re

    cleaned = re.sub(r"[^a-zA-Z0-9]", "", name).lower()
    cleaned = cleaned.replace("contentplaceholder1", "").replace("gridview1", "").replace("lbl", "").replace("count", "").replace("not", "")

    if "nursery" in cleaned:
        return "Nursery"
    if "plantation" in cleaned:
        return "Plantation"
    if "vaikunta" in cleaned:
        return "Vaikunta dhamam"
    if "dump" in cleaned or "yard" in cleaned:
        return "Dump yard"
    if "water" in cleaned or "supply" in cleaned:
        return "Water supply"
    if "meeting" in cleaned or "gpmeeting" in cleaned:
        return "GP Meetings"
    if "gram" in cleaned and "sabha" in cleaned:
        return "Gram Sabha"
    if "record" in cleaned:
        return "Record Maintenance"
    if "approval" in cleaned or "certificate" in cleaned:
        return "Approvals and Certificates"
    if "death" in cleaned:
        return "Deaths"
    if "receipt" in cleaned or "recipt" in cleaned:
        return "Recipts"
    if "expenditure" in cleaned:
        return "Expenditure"
    if "cheque" in cleaned:
        return "Cheque details"
    if "salary" in cleaned:
        return "Salary details"
    if "vwsc" in cleaned:
        return "VWSC & EGS Bank balance"
    if "mgnreg" in cleaned or "mnreg" in cleaned or "mgnre" in cleaned:
        return "MGNREGS Bank balance"
    if "electric" in cleaned:
        return "Payment of Electricity"
    if "birth" in cleaned:
        return "Birth details"

    return name.strip()


def _is_truthy(val: Any) -> bool:
    """Helper to detect affirmative entry flags across various portal conventions."""
    if isinstance(val, bool):
        return val
    v = str(val).strip().lower()
    return v in ("yes", "1", "true", "updated", "done", "completed", "y", "submitted", "approved")


# ==============================================================================
# GM-R 5.24: MONTHLY ACTIVITY STATEMENT (MAS) MODELS
# ==============================================================================
@dataclass
class GPMASDetail:
    """Gram Panchayat level monthly activity statement detail and compliance status."""

    s_no: int
    mandal_name: str
    panchayat_name: str
    financial_year: str = ""
    month: str = ""
    entered: bool = False
    status: str = "Pending"  # 'Completed', 'Pending', 'Not Entered', 'Partial'
    activity_flags: dict[str, Any] = field(default_factory=dict)
    missing_activities: list[str] = field(default_factory=list)
    is_pending: bool = True
    secretary_name: str = ""
    secretary_phone: str = ""
    remarks: str = ""

    def evaluate_pending(self, required_activities: Optional[list[str]] = None) -> None:
        """Evaluates compliance for this Gram Panchayat.

        Inspects every required activity independently. If a GP completed all but one activity,
        `missing_activities` contains ONLY that specific unfulfilled activity.
        """
        reqs = required_activities or (list(self.activity_flags.keys()) if self.activity_flags else DEFAULT_MAS_ACTIVITIES)

        missing = []
        for act in reqs:
            val = self.activity_flags.get(act, "No" if not self.entered else "Yes")
            if not _is_truthy(val):
                missing.append(act)

        self.missing_activities = missing

        # A GP is pending if it has missing activities or its entered status is false
        if missing:
            self.is_pending = True
            self.status = "Partial" if any(_is_truthy(self.activity_flags.get(a)) for a in reqs) else "Not Entered"
        elif not self.entered:
            self.is_pending = True
            self.status = "Not Entered"
            if not self.missing_activities:
                self.missing_activities = list(reqs)
        else:
            self.is_pending = False
            self.status = "Completed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "s_no": self.s_no,
            "mandal_name": self.mandal_name,
            "panchayat_name": self.panchayat_name,
            "financial_year": self.financial_year,
            "month": self.month,
            "entered": self.entered,
            "status": self.status,
            "activity_flags": self.activity_flags,
            "missing_activities": self.missing_activities,
            "is_pending": self.is_pending,
            "secretary_name": self.secretary_name,
            "secretary_phone": self.secretary_phone,
            "remarks": self.remarks,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GPMASDetail:
        return cls(
            s_no=int(data.get("s_no", 0)),
            mandal_name=str(data.get("mandal_name", "")),
            panchayat_name=str(data.get("panchayat_name", "")),
            financial_year=str(data.get("financial_year", "")),
            month=str(data.get("month", "")),
            entered=bool(data.get("entered", False)),
            status=str(data.get("status", "Pending")),
            activity_flags=dict(data.get("activity_flags", {})),
            missing_activities=list(data.get("missing_activities", [])),
            is_pending=bool(data.get("is_pending", True)),
            secretary_name=str(data.get("secretary_name", "")),
            secretary_phone=str(data.get("secretary_phone", "")),
            remarks=str(data.get("remarks", "")),
        )


@dataclass
class MandalMASSummary:
    """Mandal level aggregated Monthly Activity Statement summary."""

    s_no: int
    mandal_name: str
    total_gps: int = 0
    completed_gps: int = 0
    pending_gps_count: int = 0
    pct_completed: float = 0.0
    overall_pct_entered: float = 0.0

    # Activity-wise completed counts across this Mandal's GPs
    activity_counts: dict[str, int] = field(default_factory=dict)

    # GM-R 5.23 Birth Details indicators for this Mandal
    birth_entered_gps: int = 0
    birth_not_entered_gps: int = 0
    birth_pct_entered: float = 0.0

    has_pending: bool = False
    pending_gps: list[GPMASDetail] = field(default_factory=list)
    all_gps: list[GPMASDetail] = field(default_factory=list)

    def get_activity_stats(self, activity_name: str) -> tuple[int, int, float]:
        """Returns (entered_count, not_entered_count, pct_entered) for given activity."""
        count = self.activity_counts.get(activity_name)
        if count is None:
            norm_key = normalize_activity_key(activity_name)
            for k, v in self.activity_counts.items():
                if normalize_activity_key(k) == norm_key:
                    count = v
                    break
        if count is None:
            if normalize_activity_key(activity_name) == "Birth details" and self.birth_entered_gps > 0:
                count = self.birth_entered_gps
            else:
                count = 0

        entered = int(count)
        not_entered = max(0, self.total_gps - entered)
        pct = round((entered / self.total_gps) * 100.0, 1) if self.total_gps > 0 else 0.0
        return (entered, not_entered, pct)

    def calculate_metrics(self) -> None:
        """Recalculates completed/pending counts and achievement percentage."""
        if self.all_gps:
            self.total_gps = len(self.all_gps)
            self.pending_gps = [gp for gp in self.all_gps if gp.is_pending]
            self.pending_gps_count = len(self.pending_gps)
            self.completed_gps = self.total_gps - self.pending_gps_count
        else:
            self.pending_gps_count = max(0, self.total_gps - self.completed_gps)

        if self.total_gps > 0:
            self.pct_completed = round((self.completed_gps / self.total_gps) * 100.0, 1)
        else:
            self.pct_completed = 0.0

        # Calculate Overall % Entered matching Departmental Executive Matrix
        if self.total_gps > 0:
            # Check activities across official indicators
            relevant_acts = [act for act in OFFICIAL_MAS_REPORT_ACTIVITIES if act in self.activity_counts or normalize_activity_key(act) in [normalize_activity_key(k) for k in self.activity_counts]]
            if not relevant_acts and self.activity_counts:
                relevant_acts = list(self.activity_counts.keys())

            if relevant_acts:
                total_entered = sum(self.get_activity_stats(act)[0] for act in relevant_acts)
                total_slots = self.total_gps * len(relevant_acts)
                self.overall_pct_entered = round((total_entered / total_slots) * 100.0, 1) if total_slots > 0 else 0.0
            else:
                self.overall_pct_entered = self.pct_completed
        else:
            self.overall_pct_entered = 0.0

        self.has_pending = self.pending_gps_count > 0

    def add_gp(self, gp: GPMASDetail) -> None:
        """Adds a GP record and updates aggregates."""
        self.all_gps.append(gp)
        if gp.is_pending:
            self.pending_gps.append(gp)
        for act, val in gp.activity_flags.items():
            if _is_truthy(val):
                self.activity_counts[act] = self.activity_counts.get(act, 0) + 1
        self.calculate_metrics()

    def to_dict(self) -> dict[str, Any]:
        return {
            "s_no": self.s_no,
            "mandal_name": self.mandal_name,
            "total_gps": self.total_gps,
            "completed_gps": self.completed_gps,
            "pending_gps_count": self.pending_gps_count,
            "pct_completed": self.pct_completed,
            "overall_pct_entered": self.overall_pct_entered,
            "activity_counts": self.activity_counts,
            "birth_entered_gps": self.birth_entered_gps,
            "birth_not_entered_gps": self.birth_not_entered_gps,
            "birth_pct_entered": self.birth_pct_entered,
            "has_pending": self.has_pending,
            "pending_gps": [gp.to_dict() for gp in self.pending_gps],
            "all_gps": [gp.to_dict() for gp in self.all_gps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MandalMASSummary:
        mand = cls(
            s_no=int(data.get("s_no", 0)),
            mandal_name=str(data.get("mandal_name", "")),
            total_gps=int(data.get("total_gps", 0)),
            completed_gps=int(data.get("completed_gps", 0)),
            pending_gps_count=int(data.get("pending_gps_count", 0)),
            pct_completed=float(data.get("pct_completed", 0.0)),
            overall_pct_entered=float(data.get("overall_pct_entered", data.get("pct_completed", 0.0))),
            activity_counts=dict(data.get("activity_counts", {})),
            birth_entered_gps=int(data.get("birth_entered_gps", 0)),
            birth_not_entered_gps=int(data.get("birth_not_entered_gps", 0)),
            birth_pct_entered=float(data.get("birth_pct_entered", 0.0)),
            has_pending=bool(data.get("has_pending", False)),
        )
        if "pending_gps" in data:
            mand.pending_gps = [GPMASDetail.from_dict(g) for g in data["pending_gps"]]
        if "all_gps" in data:
            mand.all_gps = [GPMASDetail.from_dict(g) for g in data["all_gps"]]
        return mand


# ==============================================================================
# GM-R 5.23: BIRTHS REGISTER IN GP MODELS
# ==============================================================================
@dataclass
class GPBirthRegisterDetail:
    """Gram Panchayat level Births Register (GM-R 5.23) status."""

    s_no: int
    mandal_name: str
    panchayat_name: str
    financial_year: str = ""
    month: str = ""
    entered: bool = False
    births_registered: int = 0
    certificates_issued: int = 0
    is_pending: bool = True
    secretary_name: str = ""
    secretary_phone: str = ""
    remarks: str = ""

    def evaluate_pending(self) -> None:
        self.is_pending = not self.entered

    def to_dict(self) -> dict[str, Any]:
        return {
            "s_no": self.s_no,
            "mandal_name": self.mandal_name,
            "panchayat_name": self.panchayat_name,
            "financial_year": self.financial_year,
            "month": self.month,
            "entered": self.entered,
            "births_registered": self.births_registered,
            "certificates_issued": self.certificates_issued,
            "is_pending": self.is_pending,
            "secretary_name": self.secretary_name,
            "secretary_phone": self.secretary_phone,
            "remarks": self.remarks,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GPBirthRegisterDetail:
        return cls(
            s_no=int(data.get("s_no", 0)),
            mandal_name=str(data.get("mandal_name", "")),
            panchayat_name=str(data.get("panchayat_name", "")),
            financial_year=str(data.get("financial_year", "")),
            month=str(data.get("month", "")),
            entered=bool(data.get("entered", False)),
            births_registered=int(data.get("births_registered", 0)),
            certificates_issued=int(data.get("certificates_issued", 0)),
            is_pending=bool(data.get("is_pending", True)),
            secretary_name=str(data.get("secretary_name", "")),
            secretary_phone=str(data.get("secretary_phone", "")),
            remarks=str(data.get("remarks", "")),
        )


@dataclass
class MandalBirthRegisterSummary:
    """Mandal level aggregated Births Register (GM-R 5.23) summary."""

    s_no: int
    mandal_name: str
    total_gps: int = 0
    entered_gps: int = 0
    not_entered_gps: int = 0
    pct_entered: float = 0.0
    total_births: int = 0
    has_pending: bool = False
    pending_gps: list[GPBirthRegisterDetail] = field(default_factory=list)
    all_gps: list[GPBirthRegisterDetail] = field(default_factory=list)

    def calculate_metrics(self) -> None:
        if self.all_gps:
            self.total_gps = len(self.all_gps)
            self.pending_gps = [gp for gp in self.all_gps if gp.is_pending]
            self.not_entered_gps = len(self.pending_gps)
            self.entered_gps = self.total_gps - self.not_entered_gps
            self.total_births = sum(gp.births_registered for gp in self.all_gps)
        else:
            self.not_entered_gps = max(0, self.total_gps - self.entered_gps)

        if self.total_gps > 0:
            self.pct_entered = round((self.entered_gps / self.total_gps) * 100.0, 1)
        else:
            self.pct_entered = 0.0

        self.has_pending = self.not_entered_gps > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "s_no": self.s_no,
            "mandal_name": self.mandal_name,
            "total_gps": self.total_gps,
            "entered_gps": self.entered_gps,
            "not_entered_gps": self.not_entered_gps,
            "pct_entered": self.pct_entered,
            "total_births": self.total_births,
            "has_pending": self.has_pending,
            "pending_gps": [gp.to_dict() for gp in self.pending_gps],
            "all_gps": [gp.to_dict() for gp in self.all_gps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MandalBirthRegisterSummary:
        m = cls(
            s_no=int(data.get("s_no", 0)),
            mandal_name=str(data.get("mandal_name", "")),
            total_gps=int(data.get("total_gps", 0)),
            entered_gps=int(data.get("entered_gps", 0)),
            not_entered_gps=int(data.get("not_entered_gps", 0)),
            pct_entered=float(data.get("pct_entered", 0.0)),
            total_births=int(data.get("total_births", 0)),
            has_pending=bool(data.get("has_pending", False)),
        )
        if "pending_gps" in data:
            m.pending_gps = [GPBirthRegisterDetail.from_dict(g) for g in data["pending_gps"]]
        if "all_gps" in data:
            m.all_gps = [GPBirthRegisterDetail.from_dict(g) for g in data["all_gps"]]
        return m


# ==============================================================================
# COMBINED DISTRICT MASTER REPORT
# ==============================================================================
@dataclass
class DistrictMASReport:
    """District level Combined Master Report covering both GM-R 5.24 & GM-R 5.23."""

    district_name: str
    financial_year: str
    month_name: str
    generated_at: str = field(default_factory=lambda: datetime.now().strftime("%d-%B-%Y %I:%M %p"))

    # GM-R 5.24 MAS Report Details
    mandals: list[MandalMASSummary] = field(default_factory=list)
    total_mandals: int = 0
    total_gps: int = 0
    total_completed_gps: int = 0
    total_pending_gps: int = 0
    overall_pct: float = 0.0
    overall_pct_entered: float = 0.0
    all_pending_gps: list[GPMASDetail] = field(default_factory=list)
    activity_totals: dict[str, int] = field(default_factory=dict)

    # GM-R 5.23 Births Register Details
    birth_mandals: list[MandalBirthRegisterSummary] = field(default_factory=list)
    total_birth_entered_gps: int = 0
    total_birth_pending_gps: int = 0
    births_overall_pct: float = 0.0
    total_district_births: int = 0
    all_pending_birth_gps: list[GPBirthRegisterDetail] = field(default_factory=list)

    # Combined Departmental Performance Index
    combined_compliance_index: float = 0.0

    def get_activity_totals(self, activity_name: str) -> tuple[int, int, float]:
        """Returns (district_total_entered, district_total_not_entered, district_pct_entered)."""
        clean_mandals = [m for m in self.mandals if m.mandal_name.strip().upper() not in ("TOTAL", "GRAND TOTAL")]
        total_entered = 0
        for m in clean_mandals:
            ent, _, _ = m.get_activity_stats(activity_name)
            total_entered += ent
        total_not_entered = max(0, self.total_gps - total_entered)
        pct = round((total_entered / self.total_gps) * 100.0, 1) if self.total_gps > 0 else 0.0
        return (total_entered, total_not_entered, pct)

    def calculate_totals(self) -> None:
        """Aggregates all 5.24 and 5.23 mandal summaries into master district totals."""
        import re

        def _stem(s: str) -> str:
            return re.sub(r"[^a-zA-Z0-9]", "", s).lower()

        # Synchronize GM-R 5.23 Birth Details into MAS mandals via Unique Key Lookup
        if self.birth_mandals:
            # Build fast lookup dictionary for Births GP details: [MANDAL]::[GRAM_PANCHAYAT]
            birth_gp_map: dict[str, GPBirthRegisterDetail] = {}
            for bm in self.birth_mandals:
                for bgp in bm.all_gps:
                    birth_gp_map[make_lookup_key(bm.mandal_name, bgp.panchayat_name)] = bgp
                for bgp in bm.pending_gps:
                    birth_gp_map[make_lookup_key(bm.mandal_name, bgp.panchayat_name)] = bgp

            birth_map = {_stem(bm.mandal_name): bm for bm in self.birth_mandals}
            for m in self.mandals:
                s = _stem(m.mandal_name)
                matched_bm = birth_map.get(s)
                if not matched_bm:
                    for bk, bv in birth_map.items():
                        if bk in s or s in bk:
                            matched_bm = bv
                            break
                if matched_bm:
                    m.birth_entered_gps = matched_bm.entered_gps
                    m.birth_not_entered_gps = matched_bm.not_entered_gps
                    m.birth_pct_entered = matched_bm.pct_entered
                    m.activity_counts["Birth details"] = matched_bm.entered_gps

                    # Join Births status directly into each GP in m.all_gps
                    if m.all_gps:
                        for gp in m.all_gps:
                            u_key = make_lookup_key(gp.mandal_name, gp.panchayat_name)
                            bgp = birth_gp_map.get(u_key)
                            if not bgp:
                                # Fuzzy stem fallback matching
                                g_stem = _stem(gp.panchayat_name)
                                for bk, bv in birth_gp_map.items():
                                    if _stem(bv.mandal_name) == s and (
                                        _stem(bv.panchayat_name) in g_stem or g_stem in _stem(bv.panchayat_name)
                                    ):
                                        bgp = bv
                                        break
                            if bgp and bgp.entered:
                                gp.activity_flags["Birth details"] = "Yes"
                                if not gp.remarks and bgp.births_registered > 0:
                                    gp.remarks = f"Births Registered: {bgp.births_registered}"
                            else:
                                gp.activity_flags["Birth details"] = "No"

                            # Re-evaluate compliance across all 18 official indicators
                            gp.evaluate_pending(OFFICIAL_MAS_REPORT_ACTIVITIES)

                        m.calculate_metrics()

        clean_mandals = [m for m in self.mandals if m.mandal_name.strip().upper() not in ("TOTAL", "GRAND TOTAL")]
        self.total_mandals = len(clean_mandals)
        self.total_gps = sum(m.total_gps for m in clean_mandals)
        self.total_completed_gps = sum(m.completed_gps for m in clean_mandals)
        self.total_pending_gps = sum(m.pending_gps_count for m in clean_mandals)

        if self.total_gps > 0:
            self.overall_pct = round((self.total_completed_gps / self.total_gps) * 100.0, 1)
        else:
            self.overall_pct = 0.0

        # Calculate Overall % Entered across all 18 indicators matching the user's executive layout
        if self.total_gps > 0:
            total_slots = self.total_gps * len(OFFICIAL_MAS_REPORT_ACTIVITIES)
            total_entered_all = sum(self.get_activity_totals(act)[0] for act in OFFICIAL_MAS_REPORT_ACTIVITIES)
            self.overall_pct_entered = round((total_entered_all / total_slots) * 100.0, 1) if total_slots > 0 else 0.0
        else:
            self.overall_pct_entered = 0.0

        pending_list: list[GPMASDetail] = []
        act_totals: dict[str, int] = {}
        idx = 1
        for m in clean_mandals:
            for act, cnt in m.activity_counts.items():
                act_totals[act] = act_totals.get(act, 0) + cnt
            for gp in m.pending_gps:
                gp.s_no = idx
                pending_list.append(gp)
                idx += 1

        self.all_pending_gps = pending_list
        self.activity_totals = act_totals

        # GM-R 5.23 Births Aggregations
        clean_b_mandals = [m for m in self.birth_mandals if m.mandal_name.strip().upper() not in ("TOTAL", "GRAND TOTAL")]
        if clean_b_mandals:
            self.total_birth_entered_gps = sum(m.entered_gps for m in clean_b_mandals)
            self.total_birth_pending_gps = sum(m.not_entered_gps for m in clean_b_mandals)
            b_total = self.total_birth_entered_gps + self.total_birth_pending_gps
            self.births_overall_pct = round((self.total_birth_entered_gps / b_total * 100.0), 1) if b_total > 0 else 0.0
            self.total_district_births = sum(m.total_births for m in clean_b_mandals)

            b_pending: list[GPBirthRegisterDetail] = []
            b_idx = 1
            for m in clean_b_mandals:
                for gp in m.pending_gps:
                    gp.s_no = b_idx
                    b_pending.append(gp)
                    b_idx += 1
            self.all_pending_birth_gps = b_pending

        # Combined Weighted Compliance Index (60% MAS Activity Statement + 40% Births Registration)
        if clean_b_mandals and self.births_overall_pct > 0:
            self.combined_compliance_index = round((0.6 * self.overall_pct) + (0.4 * self.births_overall_pct), 1)
        else:
            self.combined_compliance_index = self.overall_pct

    def to_dict(self) -> dict[str, Any]:
        return {
            "district_name": self.district_name,
            "financial_year": self.financial_year,
            "month_name": self.month_name,
            "generated_at": self.generated_at,
            "total_mandals": self.total_mandals,
            "total_gps": self.total_gps,
            "total_completed_gps": self.total_completed_gps,
            "total_pending_gps": self.total_pending_gps,
            "overall_pct": self.overall_pct,
            "overall_pct_entered": self.overall_pct_entered,
            "activity_totals": self.activity_totals,
            "total_birth_entered_gps": self.total_birth_entered_gps,
            "total_birth_pending_gps": self.total_birth_pending_gps,
            "births_overall_pct": self.births_overall_pct,
            "total_district_births": self.total_district_births,
            "combined_compliance_index": self.combined_compliance_index,
            "mandals": [m.to_dict() for m in self.mandals],
            "birth_mandals": [m.to_dict() for m in self.birth_mandals],
            "all_pending_gps": [gp.to_dict() for gp in self.all_pending_gps],
            "all_pending_birth_gps": [gp.to_dict() for gp in self.all_pending_birth_gps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DistrictMASReport:
        rep = cls(
            district_name=str(data.get("district_name", "")),
            financial_year=str(data.get("financial_year", "")),
            month_name=str(data.get("month_name", "")),
            generated_at=str(data.get("generated_at", "")),
            total_mandals=int(data.get("total_mandals", 0)),
            total_gps=int(data.get("total_gps", 0)),
            total_completed_gps=int(data.get("total_completed_gps", 0)),
            total_pending_gps=int(data.get("total_pending_gps", 0)),
            overall_pct=float(data.get("overall_pct", 0.0)),
            overall_pct_entered=float(data.get("overall_pct_entered", data.get("overall_pct", 0.0))),
            activity_totals=dict(data.get("activity_totals", {})),
            total_birth_entered_gps=int(data.get("total_birth_entered_gps", 0)),
            total_birth_pending_gps=int(data.get("total_birth_pending_gps", 0)),
            births_overall_pct=float(data.get("births_overall_pct", 0.0)),
            total_district_births=int(data.get("total_district_births", 0)),
            combined_compliance_index=float(data.get("combined_compliance_index", 0.0)),
        )
        if "mandals" in data:
            rep.mandals = [MandalMASSummary.from_dict(m) for m in data["mandals"]]
        if "birth_mandals" in data:
            rep.birth_mandals = [MandalBirthRegisterSummary.from_dict(m) for m in data["birth_mandals"]]
        if "all_pending_gps" in data:
            rep.all_pending_gps = [GPMASDetail.from_dict(g) for g in data["all_pending_gps"]]
        if "all_pending_birth_gps" in data:
            rep.all_pending_birth_gps = [GPBirthRegisterDetail.from_dict(g) for g in data["all_pending_birth_gps"]]
        return rep
