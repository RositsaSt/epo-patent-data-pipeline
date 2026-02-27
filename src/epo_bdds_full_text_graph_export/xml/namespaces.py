from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class XmlNamespaces:
    # Add the namespaces you actually see in your EP XML.
    # Example placeholders:
    ep: str = "http://www.epo.org/exchange"
    reg: str = "http://www.epo.org/register"

    def q(self, ns: str, tag: str) -> str:
        """Return '{namespace}tag' for ElementTree searches."""
        uri = getattr(self, ns)
        return f"{{{uri}}}{tag}"