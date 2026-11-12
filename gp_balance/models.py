"""Data models for GP Balance Entry Report (GM-R 14.2)."""

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


ACTIVE_ACCOUNTS = [
    "GP PD Account-General Fund, 15th FC, SFC(IFMIS)",
    "State Matching Grant(TG-bPASS Account)",
    "15th Finance Commission Grant-Tied(e-Gram Swaraj)",
    "15th Finance Commission Grant-Untied(e-Gram Swaraj)",
    "VWSC(SBM)",
    "MGNREGS(Material Component)",
]

PMAGY_ACCOUNT_LABEL = "PMAGY (Adarsh Gram Yojana)"

# Optional account excluded by default (can be toggled per officer choice)
IGNORED_ACCOUNTS = [
    "Pradhan Mantri Adarsh Gram Yojana (PMAGY)",
]


@dataclass
class GPBalanceDetail:
    """Gram Panchayat level account balance entry status."""
    s_no: int
    mandal_name: str
    panchayat_name: str
    entered: bool
    gp_pd: str = "Yes"
    tgbpass: str = "Yes"
    fc15_tied: str = "Yes"
    fc15_untied: str = "Yes"
    vwsc: str = "Yes"
    mgnregs: str = "Yes"
    missing_accounts: list[str] = field(default_factory=list)
    is_pending: bool = False
    secretary_name: str = ""
    secretary_phone: str = ""
    pmagy: str = "Yes"
    raw_entered: Optional[bool] = None

    def __post_init__(self) -> None:
        if self.raw_entered is None:
            self.raw_entered = bool(self.entered)

    def evaluate_pending(self, include_pmagy: bool = False) -> None:
        """Inspect each account independently.

        When include_pmagy is True, PMAGY is evaluated alongside the 6 core accounts.
        """
        def is_val_entered(val: Any) -> bool:
            v = str(val).strip().lower()
            return v in ("yes", "1", "true", "updated", "done", "completed", "y")

        missing = []
        checks = [
            ("GP PD Account (General Fund, 15th FC, SFC)", self.gp_pd),
            ("State Matching Grant (TG-bPASS)", self.tgbpass),
            ("15th FC Tied (e-Gram Swaraj)", self.fc15_tied),
            ("15th FC Untied (e-Gram Swaraj)", self.fc15_untied),
        ]
        if include_pmagy:
            checks.append((PMAGY_ACCOUNT_LABEL, self.pmagy))
        checks.extend([
            ("VWSC (SBM)", self.vwsc),
            ("MGNREGS (Material Component)", self.mgnregs),
        ])
        for name, val in checks:
            if not is_val_entered(val):
                missing.append(name)

        self.missing_accounts = missing
        base_entered = self.raw_entered if self.raw_entered is not None else self.entered
        # GP is pending if any active account was not entered, or overall entry flag indicates pending
        self.is_pending = bool(missing) or not base_entered
        if self.is_pending and not self.missing_accounts:
            # Fallback if entered flag is 0 but account cells were non-standard
            self.missing_accounts = [name for name, _ in checks]


@dataclass
class MandalBalanceSummary:
    """Mandal level aggregated balance status."""
    s_no: int
    mandal_name: str
    total_gps: int
    entered_gps: int
    not_entered_gps: int
    pct_entered: float = 0.0

    # Account updated counts
    gp_pd_updated: int = 0
    tgbpass_updated: int = 0
    fc15_tied_updated: int = 0
    fc15_untied_updated: int = 0
    vwsc_updated: int = 0
    mgnregs_updated: int = 0

    # Calculated pending counts (Total GPs - Updated GPs)
    gp_pd_pending: int = 0
    tgbpass_pending: int = 0
    fc15_tied_pending: int = 0
    fc15_untied_pending: int = 0
    vwsc_pending: int = 0
    mgnregs_pending: int = 0

    has_pending: bool = False
    pending_gps: list[GPBalanceDetail] = field(default_factory=list)
    all_gps: list[GPBalanceDetail] = field(default_factory=list)
    pmagy_updated: int = 0
    pmagy_pending: int = 0
    raw_entered_gps: Optional[int] = None
    raw_not_entered_gps: Optional[int] = None

    def __post_init__(self) -> None:
        if self.raw_entered_gps is None:
            self.raw_entered_gps = self.entered_gps
        if self.raw_not_entered_gps is None:
            self.raw_not_entered_gps = self.not_entered_gps

    def calculate_metrics(self, include_pmagy: bool = False) -> None:
        if self.raw_entered_gps is not None:
            self.entered_gps = self.raw_entered_gps
        if self.raw_not_entered_gps is not None:
            self.not_entered_gps = self.raw_not_entered_gps

        if self.total_gps > 0:
            self.pct_entered = round((self.entered_gps / self.total_gps) * 100.0, 2)
        else:
            self.pct_entered = 0.0

        # Calculate pending for each active account
        self.gp_pd_pending = max(0, self.total_gps - self.gp_pd_updated)
        self.tgbpass_pending = max(0, self.total_gps - self.tgbpass_updated)
        self.fc15_tied_pending = max(0, self.total_gps - self.fc15_tied_updated)
        self.fc15_untied_pending = max(0, self.total_gps - self.fc15_untied_updated)
        self.vwsc_pending = max(0, self.total_gps - self.vwsc_updated)
        self.mgnregs_pending = max(0, self.total_gps - self.mgnregs_updated)
        self.pmagy_pending = max(0, self.total_gps - self.pmagy_updated) if include_pmagy else 0

        pending_counts = [
            self.gp_pd_pending,
            self.tgbpass_pending,
            self.fc15_tied_pending,
            self.fc15_untied_pending,
            self.vwsc_pending,
            self.mgnregs_pending,
        ]
        if include_pmagy:
            pending_counts.append(self.pmagy_pending)

        self.has_pending = (self.not_entered_gps > 0) or any(c > 0 for c in pending_counts)

        if self.has_pending:
            actual_pending = max(
                [self.not_entered_gps, len(self.pending_gps), *pending_counts]
            )
            if actual_pending > self.not_entered_gps:
                self.not_entered_gps = actual_pending
                self.entered_gps = max(0, self.total_gps - self.not_entered_gps)
                if self.total_gps > 0:
                    self.pct_entered = round((self.entered_gps / self.total_gps) * 100.0, 2)


@dataclass
class DistrictBalanceReport:
    """Consolidated District GP Balance Report."""
    district_name: str
    report_date_str: str  # Thursday date e.g. "29-10-2026"
    generated_at: str
    mandals: list[MandalBalanceSummary] = field(default_factory=list)
    pending_gps_all: list[GPBalanceDetail] = field(default_factory=list)

    # District Totals
    total_mandals: int = 0
    total_gps: int = 0
    total_entered_gps: int = 0
    total_not_entered_gps: int = 0
    overall_pct_entered: float = 0.0

    total_gp_pd_pending: int = 0
    total_tgbpass_pending: int = 0
    total_fc15_tied_pending: int = 0
    total_fc15_untied_pending: int = 0
    total_vwsc_pending: int = 0
    total_mgnregs_pending: int = 0
    include_pmagy: bool = False
    total_pmagy_pending: int = 0

    def compute_totals(self) -> None:
        # Strictly ensure no summary or total row is included in mandals list
        self.mandals = [m for m in self.mandals if "TOTAL" not in m.mandal_name.strip().upper() and "DISTRICT" not in m.mandal_name.strip().upper()]
        for idx, m in enumerate(self.mandals, start=1):
            m.s_no = idx
            if len(m.pending_gps) > m.not_entered_gps:
                m.not_entered_gps = len(m.pending_gps)
                m.entered_gps = max(0, m.total_gps - m.not_entered_gps)
                if m.total_gps > 0:
                    m.pct_entered = round((m.entered_gps / m.total_gps) * 100.0, 2)

        self.total_mandals = len(self.mandals)
        self.total_gps = sum(m.total_gps for m in self.mandals)
        self.total_entered_gps = sum(m.entered_gps for m in self.mandals)
        self.total_not_entered_gps = sum(m.not_entered_gps for m in self.mandals)
        if self.total_gps > 0:
            self.overall_pct_entered = round((self.total_entered_gps / self.total_gps) * 100.0, 2)
        else:
            self.overall_pct_entered = 0.0

        self.total_gp_pd_pending = sum(m.gp_pd_pending for m in self.mandals)
        self.total_tgbpass_pending = sum(m.tgbpass_pending for m in self.mandals)
        self.total_fc15_tied_pending = sum(m.fc15_tied_pending for m in self.mandals)
        self.total_fc15_untied_pending = sum(m.fc15_untied_pending for m in self.mandals)
        self.total_vwsc_pending = sum(m.vwsc_pending for m in self.mandals)
        self.total_mgnregs_pending = sum(m.mgnregs_pending for m in self.mandals)
        self.total_pmagy_pending = sum(m.pmagy_pending for m in self.mandals) if self.include_pmagy else 0

        self.pending_gps_all = []
        for m in self.mandals:
            self.pending_gps_all.extend(m.pending_gps)

        # Ensure total_not_entered_gps accurately reflects all pending GPs in the district
        if len(self.pending_gps_all) > self.total_not_entered_gps:
            self.total_not_entered_gps = len(self.pending_gps_all)
            self.total_entered_gps = max(0, self.total_gps - self.total_not_entered_gps)
            if self.total_gps > 0:
                self.overall_pct_entered = round((self.total_entered_gps / self.total_gps) * 100.0, 2)

        # Re-number S.No for the consolidated pending list
        for idx, gp in enumerate(self.pending_gps_all, start=1):
            gp.s_no = idx

    def clone_with_pmagy_option(self, include_pmagy: bool) -> "DistrictBalanceReport":
        """Return a re-evaluated copy of the report with PMAGY included or excluded."""
        cloned = copy.deepcopy(self)
        cloned.include_pmagy = bool(include_pmagy)
        for m in cloned.mandals:
            if m.all_gps:
                m.pending_gps = []
                for gp in m.all_gps:
                    gp.evaluate_pending(include_pmagy=cloned.include_pmagy)
                    if gp.is_pending:
                        m.pending_gps.append(gp)
            else:
                # Re-evaluate pending_gps if all_gps wasn't populated
                kept = []
                for gp in m.pending_gps:
                    gp.evaluate_pending(include_pmagy=cloned.include_pmagy)
                    if gp.is_pending:
                        kept.append(gp)
                m.pending_gps = kept
            m.calculate_metrics(include_pmagy=cloned.include_pmagy)
        cloned.compute_totals()
        return cloned
