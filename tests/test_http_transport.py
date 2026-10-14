import io
import json
from unittest.mock import patch
import pytest
from careerpilot.tinyfish_client import TinyFish, TinyFishError


def response(value):
    return io.BytesIO(json.dumps(value).encode())


def test_http_search_uses_official_gateway_and_header():
    client = TinyFish(key="test-key", transport="http")
    with patch("careerpilot.tinyfish_client.urlopen", return_value=response({"results": []})) as call:
        assert client.search("AI internship", "microsoft.com") == {"results": []}
        request = call.call_args.args[0]
        assert request.full_url.startswith("https://api.search.tinyfish.ai/?query=")
        assert "include_domains=microsoft.com" in request.full_url
        assert request.get_header("X-api-key") == "test-key"


def test_http_fetch_is_bounded_and_checks_urls():
    client = TinyFish(key="test-key", transport="http")
    with patch("careerpilot.tinyfish_client.urlopen", return_value=response({"results": []})) as call:
        client.fetch(["https://example.com/course"])
        assert json.loads(call.call_args.args[0].data)["format"] == "markdown"
        with pytest.raises(ValueError):
            client.fetch(["http://127.0.0.1"])
        assert call.call_count == 1


def test_automation_timeout_is_never_retried():
    with patch("careerpilot.tinyfish_client.urlopen", side_effect=TimeoutError) as call:
        with pytest.raises(TinyFishError, match="Inspect runs"):
            TinyFish(key="test-key", transport="http").automate("https://example.com", "Expand FAQ")
        assert call.call_count == 1


def test_error_redacts_key():
    with patch("careerpilot.tinyfish_client.urlopen", return_value=response({"error": "bad test-secret"})):
        with pytest.raises(TinyFishError) as exc:
            TinyFish(key="test-secret", transport="http").search("test")
        assert "test-secret" not in str(exc.value)
