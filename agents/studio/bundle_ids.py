import re

BUNDLE_PREFIX = "ELN-BUNDLE-"


def normalize_bundle_custom_id(value: str) -> str:
    """
    Collapse any number of repeated leading Bundle prefixes to exactly one.
    Preserves the suffix unchanged.
    """
    if value is None:
        raise ValueError("Value cannot be None")
    val = value.strip()
    if not val:
        raise ValueError("Value cannot be empty")

    if BUNDLE_PREFIX in val:
        idx = val.rindex(BUNDLE_PREFIX)
        suffix = val[idx + len(BUNDLE_PREFIX):]
        return BUNDLE_PREFIX + suffix

    return val


def create_bundle_custom_id(date_str: str, short_id: str) -> str:
    """
    Generate readable custom_id starting with ELN-BUNDLE- exactly once.
    """
    if not date_str or not short_id:
        raise ValueError("date_str and short_id are required")
    # Clean them up if they contain the prefix
    clean_date = date_str.replace(BUNDLE_PREFIX, "")
    clean_short = short_id.replace(BUNDLE_PREFIX, "")
    return f"{BUNDLE_PREFIX}{clean_date}-{clean_short}"
