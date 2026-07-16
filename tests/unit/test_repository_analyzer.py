import httpx

from seebot.analyzers import repository


class _RateLimitedClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        pass

    def get(self, url: str, params=None):
        request = httpx.Request("GET", url)
        response = httpx.Response(403, request=request, text="rate limit exceeded")
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)


def test_github_activity_rate_limit_becomes_unavailable_observation(monkeypatch) -> None:
    monkeypatch.setattr(repository.httpx, "Client", _RateLimitedClient)

    activity = repository.github_activity("https://github.com/example/project")

    assert activity["github_api_available"] is False
    assert "HTTP 403" in activity["github_api_error"]
    assert activity["commits_last_12_months"] is None


def test_github_headers_use_environment_token_without_gh(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(repository.shutil, "which", lambda _name: None)

    headers = repository._github_headers()

    assert headers["Authorization"] == "Bearer test-token"
