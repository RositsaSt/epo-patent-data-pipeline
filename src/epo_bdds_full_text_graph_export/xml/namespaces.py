from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class XmlNamespaces:
    """
    Namespace registry for ElementTree searches.

    Example:
        ns = XmlNamespaces()
        root.find(ns.q("ep", "bibliographic-data"))
    """
    ep: str = "http://www.epo.org/exchange"
    reg: str = "http://www.epo.org/register"

    def q(self, namespace: str, tag: str) -> str:
        """Return '{namespace-uri}tag' for ElementTree."""
        uri = getattr(self, namespace)
        return f"{{{uri}}}{tag}"