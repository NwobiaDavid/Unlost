from datetime import date

from unlost.extract import months_mentioned
from unlost.query_parse import parse

TODAY = date(2026, 9, 24)


def test_month_resolves_to_most_recent_past():
    pq = parse("that invoice I sent in March", TODAY)
    assert (pq.start, pq.end) == (date(2026, 3, 1), date(2026, 4, 1))
    pq = parse("that invoice I sent in November", TODAY)
    assert pq.start == date(2025, 11, 1)


def test_explicit_month_year_and_year():
    assert parse("bank statement March 2024", TODAY).start == date(2024, 3, 1)
    pq = parse("tax documents from 2023", TODAY)
    assert (pq.start, pq.end) == (date(2023, 1, 1), date(2024, 1, 1))


def test_relative_ranges():
    pq = parse("How much did I pay for rent last year?", TODAY)
    assert (pq.start, pq.end, pq.date_label) == (date(2025, 1, 1), date(2026, 1, 1), "2025")
    assert parse("the pdf I downloaded last month", TODAY).start == date(2026, 8, 1)
    assert parse("screenshot from yesterday", TODAY).start == date(2026, 9, 23)


def test_may_is_not_a_month_as_a_verb():
    assert not parse("a file that may contain my address", TODAY).has_date
    assert parse("receipt from May", TODAY).start == date(2026, 5, 1)


def test_kinds():
    assert parse("the photo of my WAEC certificate").kinds == {"image"}
    assert parse("the PDF about my car insurance").kinds == {"pdf"}
    pq = parse("screenshot of the flight booking")
    assert pq.kinds == {"image"} and pq.wants_screenshot
    assert parse("my budget spreadsheet").kinds == {"sheet"}


def test_months_mentioned():
    text = "Invoice date: 14/03/2025. Due April 30, 2025. Period 2024-12-01 to 2024-12-31."
    assert set(months_mentioned(text)) == {"2025-03", "2025-04", "2024-12"}
