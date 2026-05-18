from __future__ import annotations

from neo4j_loader.schema import ALL_CONSTRAINT_STATEMENTS, CONSTRAINTS, constraint_cypher

EXPECTED_LABELS = {
    "Publication",
    "Application",
    "IpcClassification",
    "CpcClassification",
    "Applicant",
    "Inventor",
    "Attorney",
    "SourceFile",
}


def test_all_eight_constraints_present():
    assert len(ALL_CONSTRAINT_STATEMENTS) == 8


def test_constraint_cypher_contains_required_keywords():
    stmt = constraint_cypher("Publication", "pub_id")
    assert "CREATE CONSTRAINT" in stmt
    assert "IF NOT EXISTS" in stmt
    assert "Publication" in stmt
    assert "pub_id" in stmt
    assert "IS UNIQUE" in stmt


def test_each_label_represented():
    combined = " ".join(ALL_CONSTRAINT_STATEMENTS)
    for label in EXPECTED_LABELS:
        assert label in combined, f"Label {label!r} missing from constraint statements"


def test_constraint_name_includes_label_and_prop():
    stmt = constraint_cypher("Applicant", "org_key")
    assert "applicant" in stmt.lower()
    assert "org_key" in stmt
