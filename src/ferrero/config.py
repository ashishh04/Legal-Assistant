"""Runtime settings, read once from environment variables (and an optional .env file)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
PROVIDERS = ("anthropic", "foundry", "bedrock")
OCR_ENGINES = ("auto", "server", "local", "off")

# Models that accept a mid-conversation {"role": "system"} message (not Claude Sonnet 5; not on Microsoft Foundry).
MID_CONVERSATION_SYSTEM_MODELS = frozenset({
    "claude-opus-5", "claude-opus-5-5", "claude-opus-4-8", "claude-fable-5", "claude-fable-5-1", "claude-fable-5-2",
    "claude-mythos-5", "claude-mythos-5-1", "claude-mythos-5-2", "claude-sonnet-5-5", "claude-haiku-5-5",
})


def base_model_id(model: str) -> str:
    """'us.anthropic.claude-sonnet-5', 'anthropic.claude-sonnet-5' or an inference-profile ARN -> 'claude-sonnet-5'."""
    m = model.rsplit("/", 1)[-1]
    m = re.sub(r"^(?:[a-z]{2,6}\.)?anthropic\.", "", m)
    return re.sub(r"-v\d+(?::\d+)?$", "", m)


def bedrock_model_id(model: str) -> str:
    """Bedrock model IDs carry an 'anthropic.' prefix (or a region / ARN form, which is kept as given)."""
    if model.startswith(("anthropic.", "arn:")) or re.match(r"^[a-z]{2,6}\.anthropic\.", model):
        return model
    return f"anthropic.{model}"


def load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE lines). Variables already in the environment win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)


@dataclass(frozen=True)
class Settings:
    pack_dir: Path
    data_dir: Path
    demo_today: date
    org_name: str = "Dolce Group International S.A."
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    provider: str = "anthropic"
    foundry_resource: str | None = None
    aws_region: str | None = None
    fallback_model: str | None = None  # client-side refusal fallback on Foundry / Bedrock (first-party uses "default")
    max_tool_rounds: int = 8
    documents_path: Path | None = None  # FERRERO_DOCUMENTS_DIR; default: documents_full, then documents_150, then documents
    # Text recognition for scans (Unlimited-OCR-2; see ferrero.ocr)
    ocr_engine: str = "auto"            # auto: the OCR server if FERRERO_OCR_URL is set, else the cache only
    ocr_url: str | None = None          # OpenAI-compatible endpoint serving Unlimited-OCR-2 (e.g. Baidu's SGLang build)
    ocr_model_path: Path | None = None  # local model folder; default models/Unlimited-OCR-2
    ocr_mode: str = "gundam"            # local engine: page plus detail tiles (the model's default) or "base" (faster)
    ocr_experts: str = "auto"           # local engine on a CPU: how the routed experts are held (see ocr.local)
    ocr_min_confidence: float = 0.80
    ocr_review_confidence: float = 0.90
    # Case records (ferrero.records): what users add - case changes, evidence, follow-ups, notifications, audit trail
    records_path: Path | None = None    # FERRERO_RECORDS_DIR; default data/records
    evidence_max_mb: int = 25           # largest evidence file accepted
    reminder_minutes: int = 15          # how often deadlines are checked for reminders (0: only at start and on changes)
    reminder_lead_days: int = 7         # "due soon" reminder this many days before a deadline (default for follow-ups)
    escalate_days: int = 3              # a deadline still open this many days after it passed is escalated
    # Sign-in (ferrero.auth)
    demo_password: str | None = None    # FERRERO_DEMO_PASSWORD: starting password for accounts without their own
    session_hours: int = 12             # a session ends after this long without activity
    session_remember_days: int = 14     # ... or this long with "keep me signed in"
    login_show_accounts: bool = False   # list the accounts on the sign-in page (a convenience for test environments)
    cookie_secure: str = "auto"         # Secure flag on the session cookie: auto (when the request is HTTPS), true, false

    def __post_init__(self) -> None:
        if self.effort not in EFFORT_LEVELS:
            raise ValueError(f"FERRERO_EFFORT must be one of {', '.join(EFFORT_LEVELS)}, not {self.effort!r}")
        if self.provider not in PROVIDERS:
            raise ValueError(f"FERRERO_LLM_PROVIDER must be one of {', '.join(PROVIDERS)}, not {self.provider!r}")
        if self.max_tool_rounds < 1:
            raise ValueError("FERRERO_MAX_TOOL_ROUNDS must be at least 1")
        if self.ocr_engine not in OCR_ENGINES:
            raise ValueError(f"FERRERO_OCR_ENGINE must be one of {', '.join(OCR_ENGINES)}, not {self.ocr_engine!r}")
        if self.ocr_mode not in ("gundam", "base"):
            raise ValueError(f"FERRERO_OCR_MODE must be gundam or base, not {self.ocr_mode!r}")
        if self.ocr_experts not in ("auto", "ram", "mapped", "int8"):
            raise ValueError(f"FERRERO_OCR_EXPERTS must be auto, ram, mapped or int8, not {self.ocr_experts!r}")
        if not 0 <= self.ocr_min_confidence <= self.ocr_review_confidence <= 1:
            raise ValueError("OCR thresholds need 0 <= FERRERO_OCR_MIN_CONFIDENCE <= FERRERO_OCR_REVIEW_CONFIDENCE <= 1")
        if not 1 <= self.evidence_max_mb <= 500:
            raise ValueError("FERRERO_EVIDENCE_MAX_MB must be between 1 and 500")
        if not 1 <= self.session_hours <= 24 * 30 or not 1 <= self.session_remember_days <= 365:
            raise ValueError("FERRERO_SESSION_HOURS must be 1-720 and FERRERO_SESSION_REMEMBER_DAYS 1-365")
        if self.cookie_secure not in ("auto", "true", "false"):
            raise ValueError("FERRERO_COOKIE_SECURE must be auto, true or false")
        if self.reminder_minutes < 0 or not 0 <= self.reminder_lead_days <= 90 or not 1 <= self.escalate_days <= 90:
            raise ValueError("Reminder settings: FERRERO_REMINDER_MINUTES >= 0, FERRERO_REMINDER_LEAD_DAYS 0-90, "
                             "FERRERO_ESCALATE_DAYS 1-90")

    @property
    def mid_conversation_system(self) -> bool:
        """Whether per-user context can go in an appended system message (else it leads the first user message)."""
        return self.provider != "foundry" and base_model_id(self.model) in MID_CONVERSATION_SYSTEM_MODELS

    @property
    def csv_dir(self) -> Path:
        return self.pack_dir / "csv"

    @property
    def documents_dir(self) -> Path:
        if self.documents_path is not None:
            return self.documents_path
        # documents_full: a file for every catalogue row (508), once its build has written the manifest;
        # documents_150: the original 150-PDF demo corpus; documents: the pack's 12 samples
        if (self.pack_dir / "documents_full_meta" / "manifest.csv").is_file():
            return self.pack_dir / "documents_full"
        corpus = self.pack_dir / "documents_150"
        return corpus if corpus.is_dir() else self.pack_dir / "documents"

    @property
    def catalogue_path(self) -> Path | None:
        """The document corpus's own fact_document.csv (real file names and dates), when it ships one."""
        p = self.documents_dir.parent / f"{self.documents_dir.name}_meta" / "fact_document.csv"
        return p if p.is_file() else None

    @property
    def golden_set_path(self) -> Path:
        """The corpus's own golden set when it has one (its sources name the corpus files), else the pack's."""
        corpus_golden = self.documents_dir.parent / f"{self.documents_dir.name}_meta" / "golden_set.csv"
        return corpus_golden if corpus_golden.is_file() else self.csv_dir / "golden_set.csv"

    @property
    def index_path(self) -> Path:
        return self.data_dir / "index.sqlite"

    @property
    def ocr_dir(self) -> Path:
        return self.data_dir / "ocr"

    @property
    def records_dir(self) -> Path:
        return self.records_path or self.data_dir / "records"

    @property
    def ocr_model_dir(self) -> Path:
        return self.ocr_model_path or PROJECT_ROOT / "models" / "Unlimited-OCR-2"


def _path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    p = Path(value)
    return p if p.is_absolute() else PROJECT_ROOT / p


def detect_provider(env=os.environ.get) -> str:
    """FERRERO_LLM_PROVIDER if set; otherwise inferred from which credentials are configured."""
    explicit = env("FERRERO_LLM_PROVIDER")
    if explicit:
        return explicit.lower()
    if env("ANTHROPIC_API_KEY") or env("ANTHROPIC_AUTH_TOKEN"):
        return "anthropic"
    if env("BEDROCK_MODEL_ID") or env("AWS_BEARER_TOKEN_BEDROCK"):
        return "bedrock"
    if env("ANTHROPIC_FOUNDRY_RESOURCE"):
        return "foundry"
    return "anthropic"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    env = os.environ.get
    provider = detect_provider(env)
    model = env("FERRERO_MODEL") or (env("BEDROCK_MODEL_ID") if provider == "bedrock" else None) or "claude-opus-5-5"
    if provider == "bedrock":
        model = bedrock_model_id(model)
    return Settings(
        pack_dir=_path(env("FERRERO_PACK_DIR"), PROJECT_ROOT / "docs" / "Ferrero_Demo_Pack"),
        data_dir=_path(env("FERRERO_DATA_DIR"), PROJECT_ROOT / "data"),
        demo_today=date.fromisoformat(env("FERRERO_DEMO_TODAY", "2026-11-05")),
        org_name=env("FERRERO_ORG_NAME", "Dolce Group International S.A."),
        model=model,
        effort=env("FERRERO_EFFORT", "medium").lower(),
        provider=provider,
        foundry_resource=env("ANTHROPIC_FOUNDRY_RESOURCE") or None,
        aws_region=env("AWS_REGION") or env("AWS_DEFAULT_REGION") or None,
        fallback_model=env("FERRERO_FALLBACK_MODEL") or ("claude-opus-4-8" if provider == "foundry" else None),
        max_tool_rounds=int(env("FERRERO_MAX_TOOL_ROUNDS", "8")),
        documents_path=_path(env("FERRERO_DOCUMENTS_DIR"), None) if env("FERRERO_DOCUMENTS_DIR") else None,
        ocr_engine=env("FERRERO_OCR_ENGINE", "auto").lower(),
        ocr_url=env("FERRERO_OCR_URL") or None,
        ocr_model_path=_path(env("FERRERO_OCR_MODEL_DIR"), None) if env("FERRERO_OCR_MODEL_DIR") else None,
        ocr_mode=env("FERRERO_OCR_MODE", "gundam").lower(),
        ocr_experts=env("FERRERO_OCR_EXPERTS", "auto").lower(),
        ocr_min_confidence=float(env("FERRERO_OCR_MIN_CONFIDENCE", "0.80")),
        ocr_review_confidence=float(env("FERRERO_OCR_REVIEW_CONFIDENCE", "0.90")),
        records_path=_path(env("FERRERO_RECORDS_DIR"), None) if env("FERRERO_RECORDS_DIR") else None,
        evidence_max_mb=int(env("FERRERO_EVIDENCE_MAX_MB", "25")),
        reminder_minutes=int(env("FERRERO_REMINDER_MINUTES", "15")),
        reminder_lead_days=int(env("FERRERO_REMINDER_LEAD_DAYS", "7")),
        escalate_days=int(env("FERRERO_ESCALATE_DAYS", "3")),
        demo_password=env("FERRERO_DEMO_PASSWORD") or None,
        session_hours=int(env("FERRERO_SESSION_HOURS", "12")),
        session_remember_days=int(env("FERRERO_SESSION_REMEMBER_DAYS", "14")),
        login_show_accounts=env("FERRERO_LOGIN_SHOW_ACCOUNTS", "false").lower() in ("true", "1", "yes"),
        cookie_secure=env("FERRERO_COOKIE_SECURE", "auto").lower(),
    )
