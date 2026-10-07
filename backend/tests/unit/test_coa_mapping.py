from src.services.reporting.coa_mapping import REPORT_GROUPS


def test_fixed_assets_prefix_is_15():
    assert REPORT_GROUPS["FIXED_ASSETS"]["prefix_match"] == ["15"]
