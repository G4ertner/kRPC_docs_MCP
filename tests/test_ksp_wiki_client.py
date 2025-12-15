import requests

from mcp_server.library_impl.ksp_wiki_client import API, REST_PLAIN, KspWikiClient


class _DummyResponse:
    def __init__(self, *, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON available")
        return self._json_data


class _DummySession:
    def __init__(self, handler):
        self._handler = handler
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, timeout=None):  # noqa: ARG002
        self.calls.append((url, params))
        return self._handler(url, params)


def test_get_page_prefers_parse_plain_text():
    def handler(url, params):
        if url == API and params and params.get("action") == "parse":
            return _DummyResponse(
                json_data={
                    "parse": {
                        "text": '<div class="mw-parser-output"><p>A <b>gravity turn</b> is a maneuver.</p></div>'
                    }
                }
            )
        raise AssertionError(f"Unexpected request: url={url} params={params}")

    client = KspWikiClient(throttle=0)
    client.session = _DummySession(handler)

    text = client.get_page("Gravity turn")
    assert text is not None
    assert "gravity turn" in text.lower()
    assert "<div" not in text.lower()
    assert "<!doctype html" not in text.lower()
    assert len(client.session.calls) == 1


def test_get_page_rejects_rest_html_fallback():
    def handler(url, params):
        if url == API and params and params.get("action") == "parse":
            return _DummyResponse(status_code=404, json_data={})
        if url == API and params and params.get("action") == "query":
            return _DummyResponse(
                json_data={"query": {"pages": {"-1": {"ns": 0, "title": "Gravity turn", "missing": True}}}}
            )
        if url.startswith(REST_PLAIN):
            return _DummyResponse(
                status_code=200,
                text='<!DOCTYPE html><html><head><title>Main Page</title></head><body>...</body></html>',
            )
        raise AssertionError(f"Unexpected request: url={url} params={params}")

    client = KspWikiClient(throttle=0)
    client.session = _DummySession(handler)

    text = client.get_page("Gravity turn")
    assert text is None
