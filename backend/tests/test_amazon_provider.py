"""Tests for the Amazon Creators API provider.

**No test in this file touches the network.** Every response is a recorded fixture
shaped like the published `SearchItems` / `GetItems` payloads, served by a
`httpx.MockTransport`. That is deliberate on two counts: the Creators API is
rate-limited and billed against an Associates account, and a test that silently
depended on live inventory would fail whenever Amazon reshuffles its catalogue.

What these tests protect:

* the OAuth client-credentials flow, including that a token is minted once, reused,
  and never logged;
* request construction - the `partnerTag`, the `x-marketplace` header, the paise
  price unit, the price sort;
* normalisation - and above all that nothing is invented. A response with no offer
  produces a product with no price and no retailer, and a response with no image
  produces a product that cannot be rendered;
* that the provider reports itself unavailable, rather than pretending, when
  credentials are missing.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from app.catalog.providers import (
    AMAZON_PROVIDER_ID,
    AmazonCreatorsClient,
    AmazonProductProvider,
    AmazonProviderError,
    ProductQuery,
)
from app.core.config import Settings

# --------------------------------------------------------------------------- #
# Fixtures: recorded payloads in the shape the docs publish.
# --------------------------------------------------------------------------- #

TOKEN_URL = "https://api.amazon.co.uk/auth/o2/token"

CREDS = {
    "amazon_enabled": True,
    "amazon_client_id": "amzn1.application-oa2.abc123",
    "amazon_client_secret": "shhh",
    "amazon_partner_tag": "looklock-21",
    "amazon_marketplace": "www.amazon.in",
}


def _settings(**overrides: Any) -> Settings:
    return Settings(**{**CREDS, **overrides})


def _item(
    asin: str = "B0TESTASIN",
    *,
    title: str = "Ivory Silk Sherwani for Wedding",
    brand: str = "Test Brand",
    amount: int | None = 4999,
    currency: str = "INR",
    availability: str | None = "IN_STOCK",
    condition: str = "New",
    image: bool = True,
    url: str = "https://www.amazon.in/dp/B0TESTASIN?tag=looklock-21",
    browse: str | None = "Clothing & Accessories Men Ethnic Wear Sherwani",
) -> dict[str, Any]:
    """One `SearchItems` item, built field by field like the real payload."""
    item: dict[str, Any] = {
        "asin": asin,
        "detailPageURL": url,
        "itemInfo": {
            "title": {"displayValue": title, "label": "title", "locale": "en_IN"},
            "byLineInfo": {"brand": {"displayValue": brand}},
        },
    }
    if browse is not None:
        item["browseNodeInfo"] = {
            "browseNodes": [{"id": "1234", "displayName": browse, "ancestor": []}]
        }
    if image:
        item["images"] = {
            "primary": {
                "medium": {"url": "https://m.media-amazon.com/images/I/TEST._SL160_.jpg"},
                "large": {"url": "https://m.media-amazon.com/images/I/TEST._SL500_.jpg"},
            }
        }
    if amount is not None or availability is not None:
        listing: dict[str, Any] = {"condition": {"value": condition, "subCondition": "New"}}
        if amount is not None:
            listing["price"] = {
                "money": {"amount": amount, "currency": currency, "displayAmount": "₹4999"}
            }
        if availability is not None:
            listing["availability"] = {"type": availability, "maxOrderQuantity": 1}
        item["offersV2"] = {"listings": [listing]}
    return item


def _search_payload(*items: dict[str, Any]) -> dict[str, Any]:
    return {"searchResult": {"items": list(items), "totalResultCount": len(items)}}


def _items_payload(*items: dict[str, Any]) -> dict[str, Any]:
    return {"itemsResult": {"items": list(items)}}


# --------------------------------------------------------------------------- #
# Test transport
# --------------------------------------------------------------------------- #


class _Recorder:
    """Captures requests and serves token + catalogue responses."""

    def __init__(
        self,
        *,
        search: dict[str, Any] | None = None,
        items: dict[str, Any] | None = None,
        token_status: int = 200,
        search_status: int = 200,
        token_body: dict[str, Any] | None = None,
        search_by_keyword: Callable[[str], dict[str, Any] | None] | None = None,
        fail_keywords: tuple[str, ...] = (),
        fail_status: int = 503,
    ) -> None:
        self.search = search if search is not None else _search_payload()
        self.items = items if items is not None else _items_payload()
        self.token_status = token_status
        self.search_status = search_status
        self.token_body = token_body or {"access_token": "tok-1", "expires_in": 3600}
        #: Lets a test answer differently per keyword, which is what the
        #: per-slot fan-out needs in order to be observable at all.
        self.search_by_keyword = search_by_keyword
        #: Keywords whose page should fail, to exercise partial-outage handling.
        self.fail_keywords = fail_keywords
        self.fail_status = fail_status
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.endswith("/auth/o2/token"):
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": "invalid_client"})
            return httpx.Response(200, json=self.token_body)
        if request.url.path.endswith("/searchItems"):
            keywords = json.loads(request.content).get("keywords", "")
            if keywords in self.fail_keywords:
                return httpx.Response(self.fail_status, json={"errors": []})
            if self.search_status != 200:
                return httpx.Response(self.search_status, json={"errors": []})
            if self.search_by_keyword is not None:
                payload = self.search_by_keyword(keywords)
                if payload is not None:
                    return httpx.Response(200, json=payload)
            return httpx.Response(200, json=self.search)
        if request.url.path.endswith("/getItems"):
            return httpx.Response(200, json=self.items)
        return httpx.Response(404, json={})

    @property
    def catalogue_calls(self) -> list[httpx.Request]:
        return [r for r in self.requests if "/auth/o2/token" not in r.url.path]


def _provider(recorder: _Recorder, **settings_overrides: Any) -> AmazonProductProvider:
    """A provider whose client talks to `recorder` instead of Amazon."""
    provider = AmazonProductProvider(_settings(**settings_overrides))
    transport = httpx.MockTransport(recorder.handler)
    provider._client._client = httpx.AsyncClient(
        base_url=provider._settings.amazon_catalog_url,
        transport=transport,
    )
    return provider


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


def test_amazon_is_not_configured_until_every_credential_is_present() -> None:
    """A blank value counts as missing, not as present.

    Environment files and CI both deliver `FOO=` for unset, and treating that as a
    real credential would report a broken deployment as ready.
    """
    blank = Settings(
        amazon_enabled=True,
        amazon_client_id="",
        amazon_client_secret="   ",
        amazon_partner_tag=None,
    )
    assert blank.amazon_is_configured is False
    assert blank.amazon_missing_settings == (
        "AMAZON_CLIENT_ID",
        "AMAZON_CLIENT_SECRET",
        "AMAZON_PARTNER_TAG",
    )


def test_a_configured_but_disabled_amazon_says_only_that_it_is_disabled() -> None:
    """Once credentials exist, the remaining problem is the enable flag alone."""
    settings = Settings(**{**CREDS, "amazon_enabled": False})
    assert settings.amazon_is_configured is False
    assert settings.amazon_missing_settings == ("AMAZON_ENABLED",)


def test_a_fully_configured_amazon_reports_ready() -> None:
    assert _settings().amazon_is_configured is True
    assert _settings().amazon_missing_settings == ()


def test_amazon_provider_reports_unavailable_when_credentials_are_absent() -> None:
    """Unavailability must be stated, never silently replaced with demo data."""
    provider = AmazonProductProvider(
        Settings(product_provider="amazon", amazon_enabled=False)
    )
    assert provider.is_available is False
    assert "AMAZON_CLIENT_ID" in provider.unavailable_reason
    assert provider.info.supports_shopping is True


@pytest.mark.asyncio
async def test_an_unconfigured_provider_returns_nothing_rather_than_raising() -> None:
    provider = AmazonProductProvider(Settings(product_provider="amazon"))
    assert await provider.search_products(ProductQuery(search_hint="sherwani")) == ()
    assert await provider.all_products() == ()
    assert await provider.get_product("amazon-B0TESTASIN") is None


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_the_client_mints_a_token_with_the_documented_grant() -> None:
    recorder = _Recorder()
    client = AmazonCreatorsClient(
        _settings(), client=httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler))
    )
    await client.search_items("sherwani")

    token_requests = [r for r in recorder.requests if "/auth/o2/token" in r.url.path]
    assert len(token_requests) == 1
    body = parse_qs(token_requests[0].content.decode())
    assert body["grant_type"] == ["client_credentials"]
    assert body["client_id"] == [CREDS["amazon_client_id"]]
    assert body["client_secret"] == [CREDS["amazon_client_secret"]]
    assert body["scope"] == ["creatorsapi::default"]


@pytest.mark.asyncio
async def test_a_token_is_reused_across_calls_rather_than_re_minted() -> None:
    """Re-minting per request would triple the auth traffic Amazon sees."""
    recorder = _Recorder()
    client = AmazonCreatorsClient(
        _settings(), client=httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler))
    )
    await client.search_items("sherwani")
    await client.search_items("kurta")

    token_requests = [r for r in recorder.requests if "/auth/o2/token" in r.url.path]
    assert len(token_requests) == 1


@pytest.mark.asyncio
async def test_rejected_credentials_raise_a_distinguishable_error() -> None:
    """The caller must be able to tell "not authorised" from "throttled"."""
    recorder = _Recorder(token_status=403)
    client = AmazonCreatorsClient(
        _settings(), client=httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler))
    )
    with pytest.raises(AmazonProviderError) as excinfo:
        await client.search_items("sherwani")
    assert excinfo.value.reason == "unauthorised"


@pytest.mark.asyncio
async def test_throttling_is_reported_as_throttling_and_not_as_a_crash() -> None:
    recorder = _Recorder(search_status=429)
    client = AmazonCreatorsClient(
        _settings(), client=httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler))
    )
    with pytest.raises(AmazonProviderError) as excinfo:
        await client.search_items("sherwani")
    assert excinfo.value.reason == "throttled"


@pytest.mark.asyncio
async def test_a_response_with_no_access_token_is_a_malformed_response() -> None:
    recorder = _Recorder(token_body={"expires_in": 3600})
    client = AmazonCreatorsClient(
        _settings(), client=httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler))
    )
    with pytest.raises(AmazonProviderError) as excinfo:
        await client.search_items("sherwani")
    assert excinfo.value.reason == "malformed_response"


@pytest.mark.asyncio
async def test_an_error_message_never_contains_the_client_secret() -> None:
    """A credential must not be reachable through an exception or a log line."""
    recorder = _Recorder(token_status=401)
    client = AmazonCreatorsClient(
        _settings(), client=httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler))
    )
    with pytest.raises(AmazonProviderError) as excinfo:
        await client.search_items("sherwani")
    assert CREDS["amazon_client_secret"] not in str(excinfo.value)
    assert CREDS["amazon_client_secret"] not in excinfo.value.reason


# --------------------------------------------------------------------------- #
# Request construction
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_search_sends_the_partner_tag_marketplace_and_resources() -> None:
    recorder = _Recorder()
    provider = _provider(recorder)
    await provider.search_products(ProductQuery(search_hint="wedding sherwani"))

    request = recorder.catalogue_calls[0]
    assert request.headers["x-marketplace"] == "www.amazon.in"
    assert request.headers["Authorization"] == "Bearer tok-1"
    body = json.loads(request.content)
    assert body["partnerTag"] == CREDS["amazon_partner_tag"]
    assert body["keywords"] == "wedding sherwani"
    assert body["searchIndex"] == "Apparel"
    assert "images.primary.large" in body["resources"]
    assert "offersV2.listings.price" in body["resources"]


@pytest.mark.asyncio
async def test_a_budget_biases_the_sort_rather_than_filtering_items_out() -> None:
    """Filtering on price would delete the fallbacks budget relaxation needs.

    `recommend` relaxes its constraints in a stated order to cope with thin
    inventory; a pool that has already been price-filtered has nothing left to
    relax toward, so a low budget becomes a hard failure instead of a worse look.
    """
    recorder = _Recorder()
    provider = _provider(recorder)
    await provider.search_products(ProductQuery(budget_hint_inr=5000))

    body = json.loads(recorder.catalogue_calls[0].content)
    assert body["sortBy"] == "Price:LowToHigh"
    assert "maxPrice" not in body


@pytest.mark.asyncio
async def test_a_minimum_price_is_sent_in_paise_not_rupees() -> None:
    """The documented API expects prices in the lowest currency denomination."""
    recorder = _Recorder()
    provider = _provider(recorder)
    await provider.search_products(ProductQuery(min_price_inr=1500))

    body = json.loads(recorder.catalogue_calls[0].content)
    assert body["minPrice"] == 150000


@pytest.mark.asyncio
async def test_a_get_items_lookup_keys_on_the_asin_with_condition_new() -> None:
    recorder = _Recorder(items=_items_payload(_item()))
    provider = _provider(recorder)
    await provider.get_product("amazon-B0TESTASIN")

    body = json.loads(recorder.catalogue_calls[0].content)
    assert body["itemIds"] == ["B0TESTASIN"]
    assert body["itemIdType"] == "ASIN"
    assert body["condition"] == "New"


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_listing_becomes_a_shoppable_product_with_amazon_s_own_url() -> None:
    recorder = _Recorder(search=_search_payload(_item()))
    provider = _provider(recorder)
    (product,) = await provider.search_products(ProductQuery(search_hint="sherwani"))

    assert product.product_id == "amazon-B0TESTASIN"
    assert product.source == AMAZON_PROVIDER_ID
    assert product.source_product_id == "B0TESTASIN"
    assert product.price_inr == 4999
    assert product.currency == "INR"
    assert product.retailer == "Amazon"
    assert product.purchase_url == (
        "https://www.amazon.in/dp/B0TESTASIN?tag=looklock-21"
    )
    assert product.can_shop is True
    assert product.is_demo is False
    assert product.availability == "in_stock"


@pytest.mark.asyncio
async def test_the_largest_available_image_is_used() -> None:
    recorder = _Recorder(search=_search_payload(_item()))
    provider = _provider(recorder)
    (product,) = await provider.search_products(ProductQuery(search_hint="sherwani"))
    assert product.image.url is not None
    assert product.image.url.endswith("_SL500_.jpg")


@pytest.mark.asyncio
async def test_a_sherwani_is_classified_as_a_top_from_its_browse_node() -> None:
    recorder = _Recorder(search=_search_payload(_item()))
    provider = _provider(recorder)
    (product,) = await provider.search_products(ProductQuery(search_hint="sherwani"))
    assert product.slot == "top"
    assert product.garment_category == "upper_body"


@pytest.mark.asyncio
async def test_a_jacket_browse_node_classifies_as_outerwear_not_top() -> None:
    """A jacket contains no top keyword, so only the browse ladder gets this right."""
    recorder = _Recorder(
        search=_search_payload(
            _item(
                "B0JACKET",
                title="Navy Wool Blazer Jacket",
                browse="Clothing & Accessories Men Jackets Blazers",
            )
        )
    )
    provider = _provider(recorder)
    (product,) = await provider.search_products(ProductQuery(search_hint="blazer jacket"))
    assert product.slot == "outerwear"
    assert product.garment_category == "outer"


@pytest.mark.asyncio
async def test_a_title_without_a_browse_ladder_still_classifies() -> None:
    recorder = _Recorder(
        search=_search_payload(
            _item("B0SHOE", title="Tan Leather Mojari Shoes", browse=None)
        )
    )
    provider = _provider(recorder)
    (product,) = await provider.search_products(ProductQuery(search_hint="mojari"))
    assert product.slot == "footwear"


@pytest.mark.asyncio
async def test_occasion_and_style_are_our_judgement_from_the_listing_text() -> None:
    """Amazon has no occasion field; the tags are derived, and therefore ours.

    This test pins that derivation so a change to the keyword tables is a visible
    decision rather than a silent change in what the recommender does.
    """
    recorder = _Recorder(search=_search_payload(_item()))
    provider = _provider(recorder)
    (product,) = await provider.search_products(
        ProductQuery(search_hint="sherwani", occasions=("Wedding",), styles=("Classic",))
    )
    assert "Wedding" in product.occasions
    assert product.primary_style == "Classic"


@pytest.mark.asyncio
async def test_the_requested_occasion_is_ordered_first_so_the_engine_sees_it_first() -> None:
    recorder = _Recorder(
        search=_search_payload(
            _item("B0PARTY", title="Sequin Party Dress", browse="Women Dresses Party")
        )
    )
    provider = _provider(recorder)
    (product,) = await provider.search_products(
        ProductQuery(search_hint="party dress", occasions=("Party",))
    )
    assert product.occasions[0] == "Party"


# --------------------------------------------------------------------------- #
# Nothing is invented
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_listing_with_no_offer_is_excluded_rather_than_counted_as_free() -> None:
    """A priceless listing must not enter a budget-scored pool at ₹0.

    `price_inr` is compared numerically by the engine, so carrying an unpriced item
    as zero would make a ₹40,000 look look like it fits a ₹500 budget. Dropping it is
    the only honest option: guessing a price would put a fabricated number in front
    of the shopper.
    """
    recorder = _Recorder(search=_search_payload(_item(amount=None)))
    provider = _provider(recorder)
    assert await provider.search_products(ProductQuery(search_hint="sherwani")) == ()


@pytest.mark.asyncio
async def test_a_used_offer_is_ignored_rather_than_recommended() -> None:
    recorder = _Recorder(
        search=_search_payload(_item(condition="Used", amount=1500))
    )
    provider = _provider(recorder)
    assert await provider.search_products(ProductQuery(search_hint="sherwani")) == ()


@pytest.mark.asyncio
async def test_a_listing_with_neither_price_nor_image_is_dropped() -> None:
    """Nothing to show and nothing to price means nothing to recommend."""
    recorder = _Recorder(search=_search_payload(_item(amount=None, image=False)))
    provider = _provider(recorder)
    assert await provider.search_products(ProductQuery(search_hint="sherwani")) == ()


@pytest.mark.asyncio
async def test_an_unclassifiable_listing_is_dropped_rather_than_forced_into_a_slot() -> None:
    recorder = _Recorder(
        search=_search_payload(
            _item("B0MYSTERY", title="Ceramic Table Planter Pot", browse="Home & Kitchen")
        )
    )
    provider = _provider(recorder)
    assert await provider.search_products(ProductQuery(search_hint="planter")) == ()


@pytest.mark.asyncio
async def test_a_detail_url_is_used_verbatim_and_never_rebuilt() -> None:
    """A hand-built `/dp/<asin>` link asserts a page this code never read."""
    recorder = _Recorder(
        search=_search_payload(
            _item("B0ODD", url="https://www.amazon.in/gp/product/B0ODD?psc=1&tag=looklock-21")
        )
    )
    provider = _provider(recorder)
    (product,) = await provider.search_products(ProductQuery(search_hint="sherwani"))
    assert product.purchase_url == (
        "https://www.amazon.in/gp/product/B0ODD?psc=1&tag=looklock-21"
    )


@pytest.mark.asyncio
async def test_a_non_https_detail_url_is_rejected() -> None:
    recorder = _Recorder(search=_search_payload(_item(url="http://www.amazon.in/dp/B0TEST")))
    provider = _provider(recorder)
    (product,) = await provider.search_products(ProductQuery(search_hint="sherwani"))
    assert product.purchase_url is None
    assert product.can_shop is False


@pytest.mark.asyncio
async def test_an_out_of_stock_listing_is_kept_but_marked() -> None:
    """Hiding it is the provider's call; mislabelling it would be a lie.

    Availability is reported as the source states it and the UI decides what to do,
    so an out-of-stock item is dimmed rather than silently purchasable or hidden.
    """
    recorder = _Recorder(search=_search_payload(_item(availability="OUT_OF_STOCK")))
    provider = _provider(recorder)
    (product,) = await provider.search_products(ProductQuery(search_hint="sherwani"))
    assert product.availability == "out_of_stock"
    assert product.can_shop is True


@pytest.mark.asyncio
async def test_a_listing_with_no_availability_resource_is_unknown_not_out_of_stock() -> None:
    """Absent data is not a negative claim about a real listing."""
    recorder = _Recorder(search=_search_payload(_item(availability=None, amount=None)))
    recorder.search["searchResult"]["items"][0]["offersV2"] = {
        "listings": [
            {"condition": {"value": "New"}, "price": {"money": {"amount": 2000, "currency": "INR"}}}
        ]
    }
    provider = _provider(recorder)
    (product,) = await provider.search_products(ProductQuery(search_hint="sherwani"))
    assert product.availability == "unknown"


@pytest.mark.asyncio
async def test_a_packshot_is_never_reported_as_a_worn_shot() -> None:
    """A marketplace search result is product photography, not an outfit photo.

    Treating one as the other would attribute whatever else the model in the shot
    happens to be wearing to this listing.
    """
    recorder = _Recorder(search=_search_payload(_item()))
    provider = _provider(recorder)
    (product,) = await provider.search_products(ProductQuery(search_hint="sherwani"))
    assert product.styled_image is None
    assert product.has_styled_shot is None


@pytest.mark.asyncio
async def test_an_api_failure_yields_no_products_and_no_exception() -> None:
    """A throttled upstream must not surface as a 500 to the shopper."""
    recorder = _Recorder(search_status=500)
    provider = _provider(recorder)
    assert await provider.search_products(ProductQuery(search_hint="sherwani")) == ()


@pytest.mark.asyncio
async def test_a_duplicate_asin_is_returned_once() -> None:
    recorder = _Recorder(search=_search_payload(_item(), _item()))
    provider = _provider(recorder)
    products = await provider.search_products(ProductQuery(search_hint="sherwani"))
    assert len(products) == 1


@pytest.mark.asyncio
async def test_the_limit_is_honoured_after_normalisation() -> None:
    recorder = _Recorder(
        search=_search_payload(*[_item(f"B0A{i}", title=f"Ivory Sherwani {i}") for i in range(10)])
    )
    provider = _provider(recorder)
    products = await provider.search_products(ProductQuery(search_hint="sherwani", limit=3))
    assert len(products) == 3


@pytest.mark.asyncio
async def test_cached_searches_do_not_repeat_the_upstream_call() -> None:
    """`SearchItems` is rate-limited; a repeated round must not re-bill it."""
    recorder = _Recorder(search=_search_payload(_item()))
    provider = _provider(recorder)
    await provider.search_products(ProductQuery(search_hint="sherwani"))
    await provider.search_products(ProductQuery(search_hint="sherwani"))
    assert len(recorder.catalogue_calls) == 1


def test_every_amazon_product_carries_its_source_identity() -> None:
    """Provenance has to survive normalisation, or a bad link is untraceable."""
    provider = AmazonProductProvider(_settings())
    product = provider._normalise_one(_item(), requested_occasions=(), requested_styles=())
    assert product is not None
    assert product.source == "amazon"
    assert product.source_product_id == "B0TESTASIN"
    assert product.product_id == "amazon-B0TESTASIN"

# --------------------------------------------------------------------------- #
# Slot classification without browse nodes
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_jacket_with_no_browse_node_is_outerwear_not_a_top() -> None:
    """Regression: the title ladder listed jacket/coat/hoodie under `top` and was
    checked first, so a denim jacket was offered as the top of a look and the
    engine could never find an outer layer for it."""
    provider = AmazonProductProvider(_settings())
    product = provider._normalise_one(
        _item(asin="B0JACKET", title="Men's Denim Jacket", browse=None),
        requested_occasions=(),
        requested_styles=(),
    )
    assert product is not None
    assert product.slot == "outerwear"


@pytest.mark.asyncio
async def test_a_nehru_jacket_is_still_a_top() -> None:
    """The specific form must win over the generic `jacket` in `outerwear`."""
    provider = AmazonProductProvider(_settings())
    product = provider._normalise_one(
        _item(asin="B0NEHRU", title="Nehru Jacket for Wedding", browse=None),
        requested_occasions=(),
        requested_styles=(),
    )
    assert product is not None
    assert product.slot == "top"


# --------------------------------------------------------------------------- #
# Candidate pool coverage
# --------------------------------------------------------------------------- #


def _slot_search(keywords: str) -> dict[str, Any] | None:
    """Answer a keyword search with a page of the slot it was aimed at.

    Mirrors the real failure mode: Amazon returns whatever the keywords ranked
    highest, so a single broad wedding query yields one slot over and over.
    """
    if "trousers" in keywords or "jeans" in keywords:
        return _search_payload(
            _item(
                asin="B0PANT1",
                title="Charcoal Wool Trousers",
                amount=3999,
                browse="Clothing & Accessories Men Trousers",
            )
        )
    if "jacket" in keywords or "blazer" in keywords:
        return _search_payload(
            _item(
                asin="B0JACK1",
                title="Navy Blazer Suit Jacket",
                amount=5499,
                browse="Clothing & Accessories Men Jackets",
            )
        )
    if "shirt" in keywords or "kurta" in keywords:
        return _search_payload(
            _item(
                asin="B0SHIRT",
                title="Ivory Silk Sherwani",
                amount=4999,
                browse="Clothing & Accessories Men Ethnic Wear Sherwani",
            )
        )
    return None


@pytest.mark.asyncio
async def test_the_candidate_pool_asks_for_every_slot_the_look_needs() -> None:
    """One page of ten cannot cover a look, so each required slot gets a query."""
    recorder = _Recorder(search_by_keyword=_slot_search)
    provider = _provider(recorder)
    products = await provider.search_products(
        ProductQuery(
            priority_slots=("top", "bottom", "outerwear"),
            search_hint="wedding",
        )
    )
    assert {p.slot for p in products} == {"top", "bottom", "outerwear"}
    keywords = [
        json.loads(r.content)["keywords"] for r in recorder.catalogue_calls
    ]
    assert any("shirt kurta" in k for k in keywords)
    assert any("trousers jeans" in k for k in keywords)
    assert any("jacket blazer" in k for k in keywords)


@pytest.mark.asyncio
async def test_priority_slots_do_not_narrow_the_pool() -> None:
    """They are a coverage hint, so optional pieces a search happens to surface
    must still reach the engine - that is what enriches a look."""
    # The leftover broad budget goes back on the bare intent, which is where an
    # incidental blazer would realistically turn up.
    def search(keywords: str) -> dict[str, Any] | None:
        if keywords == "wedding":
            return _search_payload(
                _item(
                    asin="B0JACK1",
                    title="Navy Blazer Suit Jacket",
                    amount=5499,
                    browse="Clothing & Accessories Men Jackets",
                )
            )
        return _slot_search(keywords)

    recorder = _Recorder(search_by_keyword=search)
    provider = _provider(recorder)
    products = await provider.search_products(
        ProductQuery(priority_slots=("top", "bottom"), search_hint="wedding")
    )
    assert {p.slot for p in products} == {"top", "bottom", "outerwear"}


@pytest.mark.asyncio
async def test_the_slot_searches_respect_the_configured_query_budget() -> None:
    """The fan-out must not turn one shopper request into unbounded upstream
    traffic against a rate-limited, billed API."""
    recorder = _Recorder(search_by_keyword=_slot_search)
    provider = _provider(recorder, amazon_max_queries_per_request=2)
    await provider.search_products(
        ProductQuery(
            priority_slots=("top", "bottom", "outerwear", "footwear"),
            search_hint="wedding",
        )
    )
    assert len(recorder.catalogue_calls) == 2


@pytest.mark.asyncio
async def test_the_page_limit_cannot_drop_a_whole_slot() -> None:
    """Truncation happens after slot interleaving, so a limit never amputates a
    garment position and leave the engine unable to build a look."""
    recorder = _Recorder(
        search_by_keyword=lambda keywords: _search_payload(
            *(
                [
                    _item(asin=f"B0TOP{i}", title="Ivory Silk Kurta", amount=2000 + i)
                    for i in range(6)
                ]
                if "shirt" in keywords
                else [
                    _item(
                        asin=f"B0BOT{i}",
                        title="Charcoal Trousers",
                        amount=3000 + i,
                        browse="Clothing & Accessories Men Trousers",
                    )
                    for i in range(2)
                ]
            )
        )
    )
    provider = _provider(recorder)
    products = await provider.search_products(
        ProductQuery(priority_slots=("top", "bottom"), search_hint="wedding", limit=4)
    )
    assert {p.slot for p in products} == {"top", "bottom"}


@pytest.mark.asyncio
async def test_the_same_listing_found_twice_is_offered_once() -> None:
    """Overlapping searches legitimately return the same garment; a duplicate
    would appear twice in a single look."""
    recorder = _Recorder(search_by_keyword=lambda keywords: _slot_search("shirt kurta"))
    provider = _provider(recorder)
    products = await provider.search_products(
        ProductQuery(priority_slots=("top", "bottom"), search_hint="wedding")
    )
    ids = [p.product_id for p in products]
    assert len(ids) == len(set(ids))


# --------------------------------------------------------------------------- #
# Upstream failures stay visible
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_failed_page_does_not_discard_the_pages_that_worked() -> None:
    """A partial outage must not empty the wardrobe, but it must not be hidden
    either - the provider reports itself degraded while serving what it has."""
    recorder = _Recorder(search_by_keyword=_slot_search, fail_keywords=("trousers jeans wedding",))
    provider = _provider(recorder)
    products = await provider.search_products(
        ProductQuery(
            slots=("top", "bottom", "outerwear"),
            occasions=("Wedding",),
            styles=("Classic",),
            search_hint="wedding",
        )
    )
    assert products, "the searches that succeeded should still yield products"
    assert "top" in {p.slot for p in products}
    assert provider.is_available is False
    assert provider.unavailable_reason


@pytest.mark.asyncio
async def test_an_outage_recovers_on_the_next_successful_call() -> None:
    """Gating requests on health rather than on configuration would let one error
    wedge the provider off permanently, so a retry must still reach Amazon."""
    recorder = _Recorder(search_by_keyword=_slot_search, fail_keywords=("trousers jeans wedding",))
    provider = _provider(recorder)
    query = ProductQuery(
        priority_slots=("top", "bottom"), search_hint="wedding"
    )
    await provider.search_products(query)
    assert provider.is_available is False

    recorder.fail_keywords = ()
    products = await provider.search_products(query)
    assert products
    assert provider.is_available is True
    assert provider.unavailable_reason == ""


@pytest.mark.asyncio
async def test_a_configured_provider_that_amazon_rejects_is_not_available() -> None:
    """`/ready` must not claim a live catalogue that renders empty."""
    recorder = _Recorder(search_status=503)
    provider = _provider(recorder)
    assert await provider.search_products(ProductQuery(search_hint="sherwani")) == ()
    assert provider.is_available is False
    assert "503" in provider.unavailable_reason

@pytest.mark.asyncio
async def test_closing_releases_an_owned_client_and_its_token() -> None:
    """Shutdown must not leave a socket open or carry a token into a restart."""
    client = AmazonCreatorsClient(_settings())
    client._http()
    client._token = "tok-secret"
    client._token_expires_at = client._clock() + 3600
    await client.aclose()
    assert client._client is None
    assert client._token is None
    assert client._cache == {}


@pytest.mark.asyncio
async def test_closing_leaves_an_injected_client_alone() -> None:
    """An injected client belongs to whoever created it - a shared pool or a
    test's transport - so shutting the app down must not close it."""
    injected = httpx.AsyncClient(transport=httpx.MockTransport(_Recorder().handler))
    client = AmazonCreatorsClient(_settings(), client=injected)
    await client.aclose()
    assert not injected.is_closed


@pytest.mark.asyncio
async def test_a_provider_can_be_closed_through_the_catalog_service() -> None:
    from app.catalog.service import close_provider_state

    await close_provider_state()
