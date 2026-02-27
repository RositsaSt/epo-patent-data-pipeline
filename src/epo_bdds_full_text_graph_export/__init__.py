"""
Graph export package for turning EPO EP full‑text XML into Neo4j‑ready CSV files.

Public entrypoint for code usage (as a library):

    from graph_export.service import GraphExportService
    from graph_export.xml_source import NestedArchiveXmlSource
    from graph_export.xml_parser import XmlPatentDocumentParser
    from graph_export.neo4j_csv_writer import Neo4jCsvGraphWriter
"""
__all__ = ["__version__"]
__version__ = "0.1.0"
