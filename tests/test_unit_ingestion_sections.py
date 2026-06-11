"""Unit tests for ingestion.extract.sections extraction logic."""
from __future__ import annotations

from ingestion.extract.sections import ExtractedSections, extract, extract_cyp_enzymes, extract_half_life


def test_cyp_enzymes_extracted_from_mechanism():
    result = extract({"mechanism_of_action": ["CYP3A4 and CYP2D6 are involved."]})
    assert "CYP3A4" in result.cyp_enzymes
    assert "CYP2D6" in result.cyp_enzymes


def test_cyp_enzymes_sorted():
    result = extract({"mechanism_of_action": ["CYP3A4 and CYP2D6 are involved."]})
    assert result.cyp_enzymes == sorted(result.cyp_enzymes)


def test_cyp_enzymes_deduplicated():
    result = extract({"mechanism_of_action": ["CYP3A4 inhibitor. CYP3A4 substrate."]})
    assert result.cyp_enzymes.count("CYP3A4") == 1


def test_cyp_enzymes_empty_when_none_present():
    result = extract({"mechanism_of_action": ["Binds the ACE receptor."]})
    assert result.cyp_enzymes == []


def test_half_life_extracted_from_pk():
    result = extract({"pharmacokinetics": ["The terminal half-life of approximately 7 hours."]})
    assert result.half_life == "7 hours"


def test_half_life_none_when_not_mentioned():
    result = extract({"pharmacokinetics": ["Renal excretion is the primary route."]})
    assert result.half_life is None


def test_indications_split_on_bullet_chars():
    result = extract({"indications_and_usage": ["Hypertension • Heart failure • Myocardial infarction"]})
    assert len(result.indications) == 3
    assert result.indications[0] == "Hypertension"
    assert result.indications[1] == "Heart failure"
    assert result.indications[2] == "Myocardial infarction"


def test_indications_split_on_subsection_refs():
    result = extract({"indications_and_usage": ["Treatment of hypertension ( 5.2 ) Management of heart failure"]})
    assert len(result.indications) == 2
    assert any("hypertension" in s.lower() for s in result.indications)
    assert any("heart failure" in s.lower() for s in result.indications)


def test_section_header_stripped_from_indications():
    result = extract({"indications_and_usage": ["1 INDICATIONS AND USAGE\nTreatment of hypertension."]})
    assert result.indications
    assert not any("INDICATIONS AND USAGE" in s for s in result.indications)
    assert any("Treatment" in s for s in result.indications)


def test_extract_cyp_enzymes_direct_deduplication():
    out = extract_cyp_enzymes("CYP3A4 substrate and CYP3A4 inhibitor")
    assert out == ["CYP3A4"]


def test_extract_cyp_enzymes_empty_text():
    assert extract_cyp_enzymes("") == []


def test_extract_half_life_range():
    result = extract_half_life("mean half-life 7 to 12 hours")
    assert result == "7 to 12 hours"


def test_extract_half_life_none_text():
    assert extract_half_life(None) is None
