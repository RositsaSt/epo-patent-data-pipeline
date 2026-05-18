from __future__ import annotations

CONSTRAINTS: list[tuple[str, str]] = [
    ("Publication", "pub_id"),
    ("Application", "appln_id"),
    ("IpcClassification", "ipc_long_code"),
    ("CpcClassification", "cpc_long_code"),
    ("Applicant", "org_key"),
    ("Inventor", "person_key"),
    ("Attorney", "person_key"),
    ("SourceFile", "source_id"),
]


def constraint_cypher(label: str, prop: str) -> str:
    name = f"constraint_{label.lower()}_{prop}"
    return (
        f"CREATE CONSTRAINT {name} IF NOT EXISTS "
        f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
    )


ALL_CONSTRAINT_STATEMENTS: list[str] = [
    constraint_cypher(label, prop) for label, prop in CONSTRAINTS
]
