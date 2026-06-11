"""Unit tests for ingestion.normalize.text string helpers."""
from __future__ import annotations

from ingestion.normalize.text import make_slug, title_case_atc, title_case_drug


def test_make_slug_lowercases():
    assert make_slug("Lisinopril") == "lisinopril"


def test_make_slug_replaces_spaces_with_hyphens():
    assert make_slug("ACE Inhibitors") == "ace-inhibitors"


def test_make_slug_replaces_slashes_with_hyphens():
    assert make_slug("Amoxicillin/Clavulanate") == "amoxicillin-clavulanate"


def test_make_slug_strips_leading_trailing_whitespace():
    assert make_slug("  Lisinopril  ") == "lisinopril"


def test_title_case_atc_connector_words_lowercase():
    assert title_case_atc("AGENTS ACTING ON THE RENIN") == "Agents Acting on the Renin"


def test_title_case_atc_single_word():
    assert title_case_atc("ANTIBIOTICS") == "Antibiotics"


def test_title_case_atc_empty_string():
    assert title_case_atc("") == ""


def test_title_case_drug_preserves_hyphens():
    assert title_case_drug("lisinopril-hydrochlorothiazide") == "Lisinopril-Hydrochlorothiazide"


def test_title_case_drug_empty_string():
    assert title_case_drug("") == ""


def test_title_case_drug_strips_whitespace():
    assert title_case_drug("  lisinopril  ") == "Lisinopril"
