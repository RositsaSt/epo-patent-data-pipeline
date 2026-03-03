from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


Row = Dict[str, object]


@dataclass(frozen=True)
class GraphRows:
    """
    Container for rows destined for Neo4j CSV tables.
    """
    publications: List[Row] = field(default_factory=list)
    applications: List[Row] = field(default_factory=list)
    ipc_classifications: List[Row] = field(default_factory=list)
    cpc_classifications: List[Row] = field(default_factory=list)
    persons: List[Row] = field(default_factory=list)
    citations: List[Row] = field(default_factory=list)
    relationships: List[Row] = field(default_factory=list)
    
    # how to use:
    # rows = GraphRows()
    # rows.publications.append({"pub_id": "EP1234567A1", "country": "EP", "pub_number": "1234567", "kind_code": "A1", "publication_date": "20200101", "pub_language": "EN", "source_id": source_id})
    # rows.applications.append({"appln_id": "EP1234567A1", "appln_country": "EP", "appln_number": "1234567", "appln_kind_code": "A1", "appln_filing_date": "20190101", "gazette_date": "20200201", "gazette_issue": "5/2020", "source_id": source_id})        
    # graph_exporter.write_rows(rows)
    
    # def write_rows(self, rows: GraphRows) -> None:
    #     self.publications_sink.write_rows(rows.publications)
    #     self.applications_sink.write_rows(rows.applications)
    #     self.ipc_classifications_sink.write_rows(rows.ipc_classifications)
    #     self.cpc_classifications_sink.write_rows(rows.cpc_classifications)
    #     self.persons_sink.write_rows(rows.persons)
    #     self.citations_sink.write_rows(rows.citations)
    #     self.relationships_sink.write_rows(rows.relationships)
        
    # def graph