"""
epo_bdds_full_text_graph_export

Tools to stream EPO BDDS EP full-text XML documents and export them into
Neo4j-ready CSV tables.

The package is designed to:
- read XML either from a filesystem directory OR nested BDDS delivery archives
- parse each XML into node/relationship rows
- append rows into CSV tables (Neo4j LOAD CSV compatible)
- track processed documents via a checkpoint store (SQLite)
"""

__all__ = ["__version__"]
__version__ = "0.1.0"

