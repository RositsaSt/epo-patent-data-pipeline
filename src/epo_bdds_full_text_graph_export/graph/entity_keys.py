from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .text_normalization import normalize_lower, normalize_text


@dataclass(frozen=True)
class OrganisationKeyStrategy:
    """
    Builds a stable key for Organisation nodes.

    Preference:
      - Use applicant_epo_id when present.
    Fallback:
      - Deterministic key based on name + country to avoid collapsing all empty-epo-id
        organisations into a single "" key.
    """

    def make_key(
        self,
        *,
        applicant_epo_id: Optional[str],
        applicant_name: str,
        applicant_country: Optional[str],
    ) -> str:
        epo_id = normalize_text(applicant_epo_id)
        if epo_id:
            return epo_id

        name = normalize_lower(applicant_name)
        country = normalize_text(applicant_country)
        return f"NAME:{name}|CC:{country}"


@dataclass(frozen=True)
class InventorKeyStrategy:
    """
    Builds a stable key for inventor Person nodes.
    
    Preference:
      - Deterministic key based on name + city + country to avoid colliding name-only.
    """

    def make_key(
        self,
        *,
        inventor_name: str,
        inventor_city: Optional[str],
        inventor_country: Optional[str],
    ) -> str:
        name = normalize_lower(inventor_name)
        city = normalize_lower(inventor_city)
        country = normalize_text(inventor_country)
        return f"INV:{name}|CITY:{city}|CC:{country}"


@dataclass(frozen=True)
class AttorneyKeyStrategy:
    """
    Builds a stable key for attorney Person nodes.

    Preference:
      - Use attorney_epo_id when present.
    Fallback:
      - Deterministic key based on name + city + country.
    """

    def make_key(
        self,
        *,
        attorney_epo_id: Optional[str],
        attorney_name: str,
        attorney_city: Optional[str],
        attorney_country: Optional[str],
    ) -> str:
        epo_id = normalize_text(attorney_epo_id)
        if epo_id:
            return epo_id

        name = normalize_lower(attorney_name)
        city = normalize_lower(attorney_city)
        country = normalize_text(attorney_country)
        return f"ATT:{name}|CITY:{city}|CC:{country}"