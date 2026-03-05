from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from .text_utils import element_text, normalize_whitespace


class ClaimsExtractor:
    """
    Extract claims text + a structured JSON representation for one language.

    Typical structure:
      <claims lang="en">
         <claim id="..." num="1"> ... </claim>
      </claims>
    """
    def extract_claims(self, root: ET.Element, *, lang: str) -> tuple[str | None, list[dict[str, Any]] | None]:
        """
        Returns:
          - claims_text: claims joined as a readable string
          - claims_json: list of {"id": "...", "num": "...", "text": "..."} or None
        """
        # Some XMLs may include multiple <claims> blocks for different languages.
        claim_blocks = [block for block in root.findall("claims") if (block.get("lang") == lang)]
        if not claim_blocks:
            return None, None

        # Usually only one block per language; if multiple, merge
        claims_rows: list[dict[str, Any]] = []
        claims_text_parts: list[str] = []

        for claim_block in claim_blocks:
            for claim in claim_block.findall("claim"):
                claim_id = (claim.get("id") or "").strip()
                claim_num = (claim.get("num") or "").strip()
                
                raw_text = element_text(claim)
                claim_text = normalize_whitespace(raw_text)
                if not claim_text:
                    continue
                
                claims_rows.append({"id": claim_id, "num": claim_num, "text": claim_text})
                
                if claim_num:
                    claims_text_parts.append(f"{claim_num}. {claim_text}")
                else:
                    claims_text_parts.append(claim_text)

        if not claims_text_parts:
            return None, None

        return "\n\n".join(claims_text_parts).strip(), claims_rows