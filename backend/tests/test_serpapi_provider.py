
from app.catalog.providers.serpapi_shopping import (
    SerpApiShoppingProductProvider,
)
from app.core.config import Settings


def test_provider_disabled():
    s = Settings(serpapi_api_key=None, serpapi_enabled=False)
    p = SerpApiShoppingProductProvider(settings=s)
    assert not p.is_configured
    assert not p.is_available

def test_configured_provider():
    s = Settings(serpapi_api_key='test_key', serpapi_enabled=True)
    p = SerpApiShoppingProductProvider(settings=s)
    assert p.is_configured
    assert p.is_available
