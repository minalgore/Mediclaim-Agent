from app.pii_redactor import PIIRedactor


def test_indian_pii_redaction():
    redactor = PIIRedactor()

    text = (
        "Patient Name: Rajesh Kumar\n"
        "Aadhaar: 2345 6789 0123\n"
        "Phone: 9876543210\n"
        "ABHA ID: 12-3456-7890-1234"
    )

    result = redactor.redact_text(text)

    assert result.redaction_count >= 3

    assert "2345 6789 0123" not in result.text
    assert "9876543210" not in result.text
    assert "12-3456-7890-1234" not in result.text

    assert "[IN_AADHAAR:" in result.text
    assert "[IN_PHONE:" in result.text
    assert "[IN_ABHA:" in result.text


def test_token_map_contains_original_values():
    redactor = PIIRedactor()

    text = (
        "Aadhaar: 2345 6789 0123\n"
        "Phone: 9876543210\n"
        "ABHA ID: 12-3456-7890-1234"
    )

    result = redactor.redact_text(text)

    token_map = redactor.get_token_map()

    assert result.redaction_count >= 3
    assert len(token_map) >= 3

    assert "2345 6789 0123" in token_map.values()
    assert "9876543210" in token_map.values()
    assert "12-3456-7890-1234" in token_map.values()


def test_restore_text():
    redactor = PIIRedactor()

    original = "Aadhaar: 2345 6789 0123"

    result = redactor.redact_text(original)

    restored = redactor.restore_text(result.text)

    assert restored == original
