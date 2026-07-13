"""P5 — heartbeat dead-link detection paths (PRD §5)."""

import httpx

from app.freshness import _looks_dead

URL = "https://example.com/jobs/123"


def _resp(status: int, text: str = "") -> httpx.Response:
    return httpx.Response(status_code=status, text=text, request=httpx.Request("GET", URL))


def test_404_is_dead():
    assert _looks_dead(_resp(404), URL) == "HTTP 404"


def test_410_is_dead():
    assert _looks_dead(_resp(410), URL) == "HTTP 410"


def test_filled_text_is_dead():
    reason = _looks_dead(
        _resp(200, text="<html>Sorry, this position has been filled.</html>"), URL
    )
    assert reason is not None and "filled" in reason


def test_no_longer_available_is_dead():
    assert _looks_dead(_resp(200, text="This job is no longer available"), URL) is not None


def test_healthy_page_is_alive():
    assert _looks_dead(_resp(200, text="<html>Apply now! Great AI role.</html>"), URL) is None


def test_generic_redirect_is_dead():
    """Redirect ending on a bare /careers landing page means the posting is gone."""
    hop = httpx.Response(302, request=httpx.Request("GET", URL))
    resp = httpx.Response(
        200,
        text="Browse all our open roles",
        request=httpx.Request("GET", "https://example.com/careers"),
        history=[hop],
    )
    reason = _looks_dead(resp, URL)
    assert reason is not None and "generic" in reason


def test_deep_redirect_is_alive():
    """Redirect to another specific posting URL is NOT death."""
    hop = httpx.Response(301, request=httpx.Request("GET", URL))
    resp = httpx.Response(
        200,
        text="Apply for this specific role",
        request=httpx.Request("GET", "https://example.com/jobs/123-new-slug"),
        history=[hop],
    )
    assert _looks_dead(resp, URL) is None
