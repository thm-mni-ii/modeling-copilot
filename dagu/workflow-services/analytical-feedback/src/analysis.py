"""Build new analytical feedback only from matcher-owned facts."""

from analysis_contract import require
from fact_projection import build_evidence_report


def build(bundle, indices, comparison):
    require(comparison.get("propertyFacts", {}).get("version") in ("1.1", "1.2"),
            "legacy comparison requires regeneration with the current matcher; stored analyses remain readable")
    return build_evidence_report(bundle, indices, comparison)
