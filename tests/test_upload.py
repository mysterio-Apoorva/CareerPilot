import base64
import pytest
from careerpilot.upload import decode_upload, MAX_BYTES


def test_upload_preserves_actual_bytes():
    data = b"%PDF-1.4 synthetic test bytes"
    result = decode_upload({"name":"test.pdf", "data":base64.b64encode(data).decode()})
    assert result.getvalue() == data
    assert result.name == "test.pdf"


@pytest.mark.parametrize("value", [
    {"name":"malware.exe", "data":"dGVzdA=="},
    {"name":"test.pdf", "data":"not valid base64"},
    {"name":"test.pdf", "data":""},
    {"name":"test.pdf", "data":"A" * (4 * MAX_BYTES // 3 + 10)},
])
def test_upload_rejects_invalid_or_oversized_values(value):
    with pytest.raises(ValueError):
        decode_upload(value)


def test_cleared_upload_is_none():
    assert decode_upload(None) is None
