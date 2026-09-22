import pytest

from kataribe.config import Settings
from tests.live import speech


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("live") and not speech.available():
        pytest.skip("fixture audio needs macOS `say` and `afconvert`")


@pytest.fixture(scope="session")
def settings() -> Settings:
    configured = Settings()
    if not configured.gemini_api_key:
        pytest.skip("KATARIBE_GEMINI_API_KEY is not set")
    return configured
