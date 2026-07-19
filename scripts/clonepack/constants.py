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

PROFILES = (
    "scaffold",
    "baseline-ready",
    "spec-ready",
    "build-ready",
    "verified-mvp",
    "gap-plan",
    "gap-closure",
    "closed",
)

PROFILE_RANK = {name: index for index, name in enumerate(PROFILES)}

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
