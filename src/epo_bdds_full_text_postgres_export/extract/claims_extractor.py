from __future__ import annotations
import xml.etree.ElementTree as ET
from typing import Any
from .text_utils import element_text
import re

_RE_WS = re.compile(r"\s+")

class ClaimsExtractor:
    def extract(self, root: ET.Element, *, lang: str) -> tuple[str | None, list[dict[str, Any]] | None]:
        """
        Returns:
          - claims_text: one big string
          - claims_json: list of {"num": "...", "id": "...", "text": "..."}
        """
        # There can be multiple <claims lang="en"> blocks (your sample has en/de/fr)
        claim_blocks = [c for c in root.findall("claims") if (c.get("lang") == lang)]
        if not claim_blocks:
            return None, None

        # Usually only one block per language; if multiple, merge
        rows: list[dict[str, Any]] = []
        texts: list[str] = []

        for block in claim_blocks:
            for claim in block.findall("claim"):
                claim_id = claim.get("id") or ""
                claim_num = claim.get("num") or ""
                # flatten nested <claim-text> structure
                t = element_text(claim)
                t = _RE_WS.sub(" ", t).strip()
                if not t:
                    continue
                rows.append({"id": claim_id, "num": claim_num, "text": t})
                texts.append(f"{claim_num}. {t}" if claim_num else t)

        if not texts:
            return None, None

        return "\n\n".join(texts).strip(), rows