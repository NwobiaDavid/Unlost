"""Pull the "when" and "what kind" out of a natural-language memory like "that invoice I sent in March"."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]
# Full names plus unambiguous abbreviations ("may" is only matched in full, "mar"/"jan"... are fine).
_MONTH_RE = "|".join(MONTHS + ["jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec"])

KIND_WORDS: dict[str, list[str]] = {
    "image": ["photo", "photos", "picture", "pictures", "pic", "pics", "image", "images", "screenshot",
              "screenshots", "screen shot", "selfie", "scan", "scanned"],
    "pdf": ["pdf", "pdfs"],
    "doc": ["word doc", "word document", "docx", "essay", "cv", "resume"],
    "sheet": ["spreadsheet", "excel", "xlsx", "csv"],
    "slides": ["slides", "slide deck", "deck", "presentation", "powerpoint", "pptx"],
}


@dataclass
class ParsedQuery:
    text: str
    start: date | None = None
    end: date | None = None  # exclusive
    kinds: set[str] = field(default_factory=set)
    wants_screenshot: bool = False
    date_label: str = ""

    @property
    def has_date(self) -> bool:
        return self.start is not None


def _month_range(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year + (month == 12), month % 12 + 1, 1)


def _month_index(token: str) -> int:
    token = token.lower()[:3]
    return next(i for i, m in enumerate(MONTHS, 1) if m.startswith(token))


def parse(q: str, today: date | None = None) -> ParsedQuery:
    today = today or datetime.now().date()
    text = " ".join(q.split())
    low = text.lower()
    pq = ParsedQuery(text=text)

    for kind, words in KIND_WORDS.items():
        if any(re.search(rf"\b{re.escape(w)}\b", low) for w in words):
            pq.kinds.add(kind)
    pq.wants_screenshot = bool(re.search(r"\bscreen ?shots?\b", low))

    # Explicit "March 2024" beats everything else.
    m = re.search(rf"\b({_MONTH_RE})\.?\s+(?:of\s+)?(19\d\d|20\d\d)\b", low)
    if m:
        month = _month_index(m[1])
        pq.start, pq.end = _month_range(int(m[2]), month)
        pq.date_label = f"{MONTHS[month - 1].title()} {m[2]}"
        return pq

    # "in March" / "last March" -> the most recent March that isn't in the future.
    m = re.search(rf"\b(in|from|during|around|since|last|early|late)\s+({_MONTH_RE})\b", low)
    if m:
        month = _month_index(m[2])
        year = today.year if month <= today.month else today.year - 1
        if m[1] == "last" and month == today.month:
            year -= 1
        pq.start, pq.end = _month_range(year, month)
        pq.date_label = f"{MONTHS[month - 1].title()} {year}"
        return pq

    m = re.search(r"\b(19\d\d|20\d\d)\b", low)
    if m:
        y = int(m[1])
        pq.start, pq.end, pq.date_label = date(y, 1, 1), date(y + 1, 1, 1), str(y)
        return pq

    tomorrow = today + timedelta(days=1)
    relative = [
        (r"\btoday\b", today, tomorrow, "Today"),
        (r"\byesterday\b", today - timedelta(days=1), today, "Yesterday"),
        (r"\b(?:this|past) week\b", today - timedelta(days=7), tomorrow, "Past week"),
        (r"\blast week\b", today - timedelta(days=14), tomorrow, "Last 2 weeks"),
        (r"\b(?:recent|recently|the other day|a few days ago)\b", today - timedelta(days=30), tomorrow, "Last 30 days"),
    ]
    for pattern, start, end, label in relative:
        if re.search(pattern, low):
            pq.start, pq.end, pq.date_label = start, end, label
            return pq

    if re.search(r"\bthis month\b", low):
        pq.start, pq.end = _month_range(today.year, today.month)
        pq.date_label = "This month"
    elif re.search(r"\blast month\b", low):
        y, mth = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        pq.start, pq.end = _month_range(y, mth)
        pq.date_label = f"{MONTHS[mth - 1].title()} {y}"
    elif re.search(r"\bthis year\b", low):
        pq.start, pq.end, pq.date_label = date(today.year, 1, 1), date(today.year + 1, 1, 1), str(today.year)
    elif re.search(r"\blast year\b", low):
        y = today.year - 1
        pq.start, pq.end, pq.date_label = date(y, 1, 1), date(y + 1, 1, 1), str(y)
    return pq


def months_in_range(start: date, end: date) -> set[str]:
    out, d = set(), date(start.year, start.month, 1)
    while d < end:
        out.add(f"{d.year:04d}-{d.month:02d}")
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return out
