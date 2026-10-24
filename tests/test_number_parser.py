import pytest
from src.number_parser import parse_number, normalize_date_to_iso


@pytest.mark.parametrize(
    "raw,expected_status,expected_val",
    [
        # Plain numbers
        ("2,002,429", "present", 2002429),
        ("608,281", "present", 608281),
        ("0", "present", 0),
        ("4553", "present", 4553),
        
        # △ negative numbers
        ("△2,979", "present", -2979),
        ("△1,923,585", "present", -1923585),
        ("△147,599", "present", -147599),
        ("△0", "present", 0),  # Special case: △0 is present with value 0
        
        # ▲ negative numbers
        ("▲500", "present", -500),
        ("▲12,345", "present", -12345),
        
        # Parentheses negatives
        ("(1,234)", "present", -1234),
        ("（1,234）", "present", -1234),
        ("（50）", "present", -50),
        
        # Full-width digits and commas
        ("２，００２，４２９", "present", 2002429),
        ("△１，９２３，５８５", "present", -1923585),
        ("（２５０）", "present", -250),
        
        # Standard minus sign
        ("-100", "present", -100),
        ("−100", "present", -100),
        
        # Nil markers
        ("－", "nil", None),
        ("-", "nil", None),
        ("—", "nil", None),
        ("―", "nil", None),
        
        # Unreadable / Empty / Non-numeric
        (None, "unreadable", None),
        ("", "unreadable", None),
        ("   ", "unreadable", None),
        ("abc", "unreadable", None),
        ("N/A", "unreadable", None),
    ],
)
def test_parse_number(raw, expected_status, expected_val):
    status, val = parse_number(raw)
    assert status == expected_status
    assert val == expected_val


@pytest.mark.parametrize(
    "raw_date,expected_iso",
    [
        ("2025 年３月 31 日", "2025-03-31"),
        ("(2025 年３月 31 日)", "2025-03-31"),
        ("2026年3月31日", "2026-03-31"),
        ("(2026 年３月 31 日)", "2026-03-31"),
        ("２０２５年３月３１日", "2025-03-31"),
        ("2025-03-31", "2025-03-31"),
        ("Invalid Date", None),
        ("", None),
    ],
)
def test_normalize_date_to_iso(raw_date, expected_iso):
    assert normalize_date_to_iso(raw_date) == expected_iso
