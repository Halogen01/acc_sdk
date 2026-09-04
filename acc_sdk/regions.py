"""Current Autodesk Platform Services data-region identifiers."""

from enum import StrEnum


class ApsRegion(StrEnum):
    """Regions currently documented by Autodesk Data Management and OSS."""

    US = "US"
    EMEA = "EMEA"
    AUS = "AUS"
    CAN = "CAN"
    DEU = "DEU"
    IND = "IND"
    JPN = "JPN"
    GBR = "GBR"


def normalize_aps_region(
    region: str | ApsRegion | None = None,
    *,
    default: str | ApsRegion = ApsRegion.US,
) -> ApsRegion:
    """Return a validated APS region, defaulting to the US data center.

    Region strings are normalized to uppercase. Deprecated or undocumented
    aliases such as ``APAC`` and ``EU`` are intentionally rejected so callers
    cannot accidentally route data to an assumed location.
    """
    candidate = default if region is None else region
    if isinstance(candidate, ApsRegion):
        return candidate
    if not isinstance(candidate, str) or not candidate.strip():
        raise ValueError("An Autodesk region must be a non-empty string")
    try:
        return ApsRegion(candidate.strip().upper())
    except ValueError as error:
        supported = ", ".join(member.value for member in ApsRegion)
        raise ValueError(
            f"Unsupported Autodesk region {candidate!r}; expected one of {supported}"
        ) from error
