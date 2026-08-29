"""Content moderation and legal guardrails (Requirement 13.8, SECURITY.md §12).

Two distinct jobs:

1. **Input screening** on briefs and prompts, before any provider is paid. This
   catches prohibited categories and, importantly, attempts to depict real,
   identifiable people — the biggest legal exposure in AI video.
2. **Output screening** on generated scripts, so a model that drifts into
   prohibited territory does not reach the user or the video pipeline.

The checks are deliberately conservative and explainable: a deterministic
rule layer runs first (fast, free, auditable), and a model-based check can be
layered on later without changing callers.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum


class ModerationCategory(StrEnum):
    REAL_PERSON = "real_person_likeness"
    SEXUAL = "sexual_content"
    VIOLENCE = "graphic_violence"
    HATE = "hate_speech"
    ILLEGAL = "illegal_activity"
    SELF_HARM = "self_harm"
    MEDICAL_CLAIM = "unsubstantiated_health_claim"
    FINANCIAL_CLAIM = "unsubstantiated_financial_claim"
    MINOR_SAFETY = "minor_safety"


class ModerationDecision(StrEnum):
    ALLOW = "allow"
    FLAG = "flag"  # proceed, but record for review
    BLOCK = "block"  # refuse outright


@dataclass
class ModerationFinding:
    category: ModerationCategory
    decision: ModerationDecision
    explanation: str
    matched_terms: list[str] = field(default_factory=list)


@dataclass
class ModerationResult:
    decision: ModerationDecision
    findings: list[ModerationFinding] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.decision is ModerationDecision.BLOCK

    @property
    def user_message(self) -> str:
        """Explanation safe to show the user."""
        if not self.findings:
            return "Content passed moderation."
        blocking = [f for f in self.findings if f.decision is ModerationDecision.BLOCK]
        relevant = blocking or self.findings
        return " ".join(f.explanation for f in relevant)


def _phrase_pattern(phrases: list[str]) -> re.Pattern[str]:
    """Word-boundary alternation so 'ass' does not match inside 'assets'."""
    escaped = [re.escape(p) for p in phrases]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)


# Signals that a prompt is trying to depict a specific real individual.
# Names are not enumerated (impossible to maintain and locale-biased); instead we
# detect the *intent patterns* that request a real likeness.
_REAL_PERSON_PATTERNS = [
    re.compile(
        r"\b(?:looks?|looking|appears?|appearing)\s+(?:exactly\s+)?like\s+"
        r"(?:the\s+)?(?:celebrity|actor|actress|singer|rapper|athlete|president|"
        r"prime\s+minister|influencer)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:deepfake|deep\s+fake|face\s*swap|face-?swapped|likeness\s+of)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:impersonat\w+|pretend(?:ing)?\s+to\s+be)\s+"
        r"(?:a\s+)?(?:real\s+)?(?:celebrity|politician|public\s+figure|ceo)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:portray|depict|show|feature)\s+(?:the\s+)?"
        r"(?:real|actual)\s+(?:person|celebrity|politician|public\s+figure)\b",
        re.IGNORECASE,
    ),
]

_CATEGORY_TERMS: dict[ModerationCategory, list[str]] = {
    ModerationCategory.SEXUAL: [
        "nude",
        "nudity",
        "naked",
        "explicit sex",
        "sexual act",
        "pornographic",
        "porn",
        "erotic",
        "fetish",
        "topless",
    ],
    ModerationCategory.VIOLENCE: [
        "gore",
        "gory",
        "decapitation",
        "beheading",
        "mutilation",
        "dismembered",
        "torture",
        "blood spraying",
        "graphic injury",
    ],
    ModerationCategory.HATE: [
        "racial slur",
        "ethnic cleansing",
        "white power",
        "hate group",
        "inferior race",
        "subhuman",
    ],
    ModerationCategory.ILLEGAL: [
        "how to make a bomb",
        "buy cocaine",
        "sell heroin",
        "money laundering",
        "counterfeit currency",
        "hire a hitman",
        "credit card dump",
    ],
    ModerationCategory.SELF_HARM: [
        "suicide method",
        "how to self harm",
        "kill yourself",
        "cutting yourself",
    ],
    ModerationCategory.MINOR_SAFETY: [
        "sexualized child",
        "sexual minor",
        "child in lingerie",
        "underage model",
    ],
}

_BLOCK_CATEGORIES = {
    ModerationCategory.SEXUAL,
    ModerationCategory.VIOLENCE,
    ModerationCategory.HATE,
    ModerationCategory.ILLEGAL,
    ModerationCategory.SELF_HARM,
    ModerationCategory.MINOR_SAFETY,
    ModerationCategory.REAL_PERSON,
}

_CATEGORY_PATTERNS = {
    category: _phrase_pattern(terms) for category, terms in _CATEGORY_TERMS.items()
}

_EXPLANATIONS = {
    ModerationCategory.REAL_PERSON: (
        "This appears to request the likeness of a real, identifiable person. "
        "We can only generate original characters, or people you have uploaded "
        "and confirmed you have consent to use."
    ),
    ModerationCategory.SEXUAL: "Sexual or explicit content is not permitted.",
    ModerationCategory.VIOLENCE: "Graphic violence is not permitted.",
    ModerationCategory.HATE: "Hateful or discriminatory content is not permitted.",
    ModerationCategory.ILLEGAL: "Content facilitating illegal activity is not permitted.",
    ModerationCategory.SELF_HARM: "Content relating to self-harm is not permitted.",
    ModerationCategory.MINOR_SAFETY: "This request is refused on child-safety grounds.",
    ModerationCategory.MEDICAL_CLAIM: (
        "This makes a health claim that may need substantiation. Review it against "
        "advertising rules in your market before publishing."
    ),
    ModerationCategory.FINANCIAL_CLAIM: (
        "This makes a financial or earnings claim that may need substantiation. "
        "Review it against advertising rules in your market before publishing."
    ),
}

# Advisory only: these are lawful but risky claims an advertiser should check.
_ADVISORY_TERMS: dict[ModerationCategory, list[str]] = {
    ModerationCategory.MEDICAL_CLAIM: [
        "cures",
        "cure cancer",
        "clinically proven",
        "medically proven",
        "treats disease",
        "guaranteed weight loss",
        "fda approved",
    ],
    ModerationCategory.FINANCIAL_CLAIM: [
        "guaranteed returns",
        "risk free investment",
        "double your money",
        "guaranteed income",
        "get rich quick",
    ],
}
_ADVISORY_PATTERNS = {
    category: _phrase_pattern(terms) for category, terms in _ADVISORY_TERMS.items()
}


def moderate_text(text: str) -> ModerationResult:
    """Screen a single block of text."""
    if not text or not text.strip():
        return ModerationResult(decision=ModerationDecision.ALLOW)

    findings: list[ModerationFinding] = []

    for pattern in _REAL_PERSON_PATTERNS:
        match = pattern.search(text)
        if match:
            findings.append(
                ModerationFinding(
                    category=ModerationCategory.REAL_PERSON,
                    decision=ModerationDecision.BLOCK,
                    explanation=_EXPLANATIONS[ModerationCategory.REAL_PERSON],
                    matched_terms=[match.group(0)],
                )
            )
            break

    for category, pattern in _CATEGORY_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            findings.append(
                ModerationFinding(
                    category=category,
                    decision=(
                        ModerationDecision.BLOCK
                        if category in _BLOCK_CATEGORIES
                        else ModerationDecision.FLAG
                    ),
                    explanation=_EXPLANATIONS[category],
                    matched_terms=sorted({m.lower() for m in matches}),
                )
            )

    for category, pattern in _ADVISORY_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            findings.append(
                ModerationFinding(
                    category=category,
                    decision=ModerationDecision.FLAG,
                    explanation=_EXPLANATIONS[category],
                    matched_terms=sorted({m.lower() for m in matches}),
                )
            )

    if any(f.decision is ModerationDecision.BLOCK for f in findings):
        decision = ModerationDecision.BLOCK
    elif findings:
        decision = ModerationDecision.FLAG
    else:
        decision = ModerationDecision.ALLOW
    return ModerationResult(decision=decision, findings=findings)


def _collect_strings(value: object, depth: int = 0) -> list[str]:
    """Flatten nested structures into their string values."""
    if depth > 6:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _collect_strings(v, depth + 1)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _collect_strings(v, depth + 1)]
    return []


def moderate_payload(payload: object) -> ModerationResult:
    """Screen every string in a nested structure (a brief or a script)."""
    combined = "\n".join(_collect_strings(payload))
    return moderate_text(combined)


def merge(results: list[ModerationResult]) -> ModerationResult:
    """Combine several results, taking the most severe decision."""
    findings = [f for r in results for f in r.findings]
    if any(r.decision is ModerationDecision.BLOCK for r in results):
        decision = ModerationDecision.BLOCK
    elif any(r.decision is ModerationDecision.FLAG for r in results):
        decision = ModerationDecision.FLAG
    else:
        decision = ModerationDecision.ALLOW
    return ModerationResult(decision=decision, findings=findings)
