from __future__ import annotations

V2_SCHEMA = "clone-pack/v2"

V2_DOCUMENTS = {
    "clone_brief.md": "clone-brief/v2",
    "evidence_ledger.md": "clone-evidence/v2",
    "clone_specification.md": "clone-spec/v2",
    "mvp_build_plan.md": "clone-mvp-plan/v2",
    "acceptance_matrix.md": "clone-acceptance/v2",
    "gaps_analysis.md": "clone-gaps/v2",
    "gap_implementation_plan.md": "clone-gap-plan/v2",
    "architecture_decisions.md": "clone-architecture-decisions/v2",
    "security_assurance.md": "clone-security-assurance/v2",
    "provenance_ledger.md": "clone-provenance-ledger/v2",
}

PLAN_FILES = {
    "capture": "capture_plan.json",
    "parity": "parity_plan.json",
    "scaffold": "scaffold_plan.json",
    "assurance": "assurance_plan.json",
}

OPTIONAL_PLAN_FILES = {
    "full_stack_qa": "full_stack_qa_plan.json",
}

ENHANCEMENT_PLAN_FILES = {
    "repository_inventory": "repository_inventory.json",
    "enhancement": "enhancement_plan.json",
}

PRODUCT_TYPES = {
    "website",
    "web-app-saas",
    "api-service-server",
    "client-app",
    "library-sdk",
    "cli",
    "browser-extension",
    "ai-ml-system",
    "data-pipeline",
    "database-storage",
    "distributed-realtime",
    "game-simulation",
    "embedded-iot",
    "hybrid",
}

PLAYBOOKS = PRODUCT_TYPES - {"hybrid"}

LEGACY_PROFILES = (
    "scaffold",
    "baseline-ready",
    "spec-ready",
    "build-ready",
    "verified-mvp",
    "gap-plan",
    "gap-closure",
    "closed",
)

ENHANCEMENT_PROFILES = (
    "repository-adopted",
    "enhancement-ready",
    "implementation",
    "verified-enhancement",
)

PROFILES = (*LEGACY_PROFILES, *ENHANCEMENT_PROFILES)

# Retained for API compatibility with 2.0 callers. New validation code uses
# PROFILE_ANCESTORS; enhancement profiles never inherit clone-MVP milestones.
PROFILE_RANK = {name: index for index, name in enumerate(LEGACY_PROFILES)}

PROFILE_ANCESTORS = {
    profile: frozenset(LEGACY_PROFILES[: index + 1])
    for index, profile in enumerate(LEGACY_PROFILES)
}
PROFILE_ANCESTORS.update(
    {
        "repository-adopted": frozenset({"scaffold", "repository-adopted"}),
        "enhancement-ready": frozenset({"scaffold", "repository-adopted", "enhancement-ready"}),
        "implementation": frozenset(
            {"scaffold", "repository-adopted", "enhancement-ready", "implementation"}
        ),
        "verified-enhancement": frozenset(
            {
                "scaffold",
                "repository-adopted",
                "enhancement-ready",
                "implementation",
                "verified-enhancement",
            }
        ),
    }
)


def profile_requires(profile: str, milestone: str) -> bool:
    return milestone in PROFILE_ANCESTORS.get(profile, frozenset())

RECORD_KINDS = {
    "BASE",
    "BLOCK",
    "ENV",
    "ART",
    "E",
    "CONFLICT",
    "DEC",
    "ADR",
    "ACT",
    "WF",
    "SURF",
    "REQ",
    "IF",
    "DATA",
    "SEC",
    "NFR",
    "EXC",
    "AC",
    "TEST",
    "GATE",
    "RUN",
    "GAP",
    "INV",
    "CHANGE",
    "STEP",
    "CAP",
    "PAR",
    "ASSURE",
    "PROV",
    "ASSET",
    "THREAT",
    "CTRL",
    "FIND",
    "GAPDEC",
    "COMP",
    "SBOM",
    "BUILD",
    "PROVBLOCK",
    "STACK",
    "SCF",
    "DEP",
    "SLICE",
    "HALT",
    "MIG",
    "ENH",
    "PRES",
    "SNAP",
    "SCOPE",
}

GAP_STATUSES = {"OPEN", "BLOCKED", "IN_PROGRESS", "IMPLEMENTED", "VERIFIED", "DECLINED"}
TERMINAL_GAP_STATUSES = {"VERIFIED", "DECLINED"}

LEGAL_GAP_TRANSITIONS = {
    ("OPEN", "IN_PROGRESS"),
    ("OPEN", "BLOCKED"),
    ("BLOCKED", "OPEN"),
    ("OPEN", "DECLINED"),
    ("BLOCKED", "DECLINED"),
    ("IN_PROGRESS", "IMPLEMENTED"),
    ("IMPLEMENTED", "VERIFIED"),
    ("IMPLEMENTED", "IN_PROGRESS"),
    ("VERIFIED", "OPEN"),
}

ARTIFACT_ID_PATTERN = (
    r"ART-(?:\d{3,}|(?:CAP|RUN|PAR|ASSURE)-\d{3,}-\d{2,}|PAR-DRIVER-\d{2,}-\d{2,})"
)

ID_PATTERNS = {
    "BASE": r"BASE-\d{3,}",
    "BLOCK": r"BLOCK-\d{3,}",
    "ENV": r"ENV-\d{3,}",
    "ART": ARTIFACT_ID_PATTERN,
    "E": r"E-\d{3,}",
    "CONFLICT": r"CONFLICT-\d{3,}",
    "DEC": r"DEC-\d{3,}",
    "ADR": r"ADR-\d{3,}",
    "ACT": r"ACT-\d{3,}",
    "WF": r"WF-\d{3,}",
    "SURF": r"SURF-\d{3,}",
    "REQ": r"(?:REQ-\d{3,}|REQ-GAP-\d{3,}-\d{2,})",
    "IF": r"IF-\d{3,}",
    "DATA": r"DATA-\d{3,}",
    "SEC": r"SEC-\d{3,}",
    "NFR": r"NFR-\d{3,}",
    "EXC": r"EXC-\d{3,}",
    "AC": r"(?:AC-\d{3,}|AC-GAP-\d{3,}-\d{2,})",
    "TEST": r"(?:TEST-\d{3,}|TEST-GAP-\d{3,}-\d{2,})",
    "GATE": r"GATE-\d{3,}",
    "RUN": r"RUN-\d{3,}",
    "GAP": r"GAP-\d{3,}",
    "INV": r"INV-\d{3,}",
    "CHANGE": r"(?:CHANGE-\d{3,}|CHANGE-GAP-\d{3,}-\d{2,})",
    "STEP": r"(?:STEP-\d{3,}|STEP-GAP-\d{3,}-\d{2,})",
    "CAP": r"CAP-\d{3,}",
    "PAR": r"PAR-\d{3,}",
    "ASSURE": r"ASSURE-\d{3,}",
    "PROV": r"PROV-\d{3,}",
    "ASSET": r"ASSET-\d{3,}",
    "THREAT": r"THREAT-\d{3,}",
    "CTRL": r"CTRL-\d{3,}",
    "FIND": r"FIND-\d{3,}",
    "GAPDEC": r"GAPDEC-\d{3,}",
    "COMP": r"COMP-\d{3,}",
    "SBOM": r"SBOM-\d{3,}",
    "BUILD": r"BUILD-\d{3,}",
    "PROVBLOCK": r"PROVBLOCK-\d{3,}",
    "STACK": r"STACK-\d{3,}",
    "SCF": r"SCF-\d{3,}",
    "DEP": r"DEP-\d{3,}",
    "SLICE": r"SLICE-\d{3,}",
    "HALT": r"HALT-\d{3,}",
    "MIG": r"MIG-\d{3,}",
    "ENH": r"ENH-\d{3,}",
    "PRES": r"PRES-\d{3,}",
    "SNAP": r"SNAP-\d{3,}",
    "SCOPE": r"SCOPE-\d{3,}",
}

# Full-stack plans use local identities that are not clone-index record kinds.
# Keep them separate so record references cannot silently accept plan-local IDs.
PLAN_LOCAL_ID_PATTERNS = {
    "QA": r"QA-\d{3,}",
    "BIND": r"BIND-\d{3,}",
    "SERVICE": r"SERVICE-\d{3,}",
    "EXTERNAL": r"EXTERNAL-\d{3,}",
}

CHANGE_TYPES = {
    "feature",
    "behavior-change",
    "refactor",
    "dependency-upgrade",
    "data-migration",
    "security-hardening",
    "operations",
}

COMPATIBILITY_DISPOSITIONS = {"PRESERVE", "ADDITIVE", "BREAK_APPROVED", "NOT_APPLICABLE"}
DELIVERY_STRATEGIES = {"in-place", "parallel-path", "feature-flag", "expand-contract"}
ENHANCEMENT_STATUSES = {"DRAFT", "READY", "BLOCKED", "IN_PROGRESS", "IMPLEMENTED", "VERIFIED", "DECLINED"}
TERMINAL_ENHANCEMENT_STATUSES = {"VERIFIED", "DECLINED"}
LEGAL_ENHANCEMENT_TRANSITIONS = {
    ("DRAFT", "READY"),
    ("DRAFT", "BLOCKED"),
    ("DRAFT", "DECLINED"),
    ("READY", "IN_PROGRESS"),
    ("READY", "BLOCKED"),
    ("READY", "DECLINED"),
    ("IN_PROGRESS", "IMPLEMENTED"),
    ("IN_PROGRESS", "BLOCKED"),
    ("IMPLEMENTED", "VERIFIED"),
    ("IMPLEMENTED", "IN_PROGRESS"),
    ("VERIFIED", "IN_PROGRESS"),
}

EXIT_OK = 0
EXIT_CONTRACT = 1
EXIT_USAGE = 2
EXIT_UNSUPPORTED = 3
EXIT_INTEGRITY = 4
EXIT_HOLD = 5
EXIT_MIGRATION = 6
EXIT_INFRASTRUCTURE = 7
EXIT_INTERNAL = 70
