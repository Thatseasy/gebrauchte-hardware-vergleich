import pytest
from bs4 import BeautifulSoup
from hardware_crawler.scrapers import KleinanzeigenScraper

def test_parse_price_info_variants():
    # 1. Fixed price
    p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info("200 €")
    assert p == 200.0
    assert not is_vb
    assert not needs_neg
    assert not is_fake

    # 2. Asking price with VB ("200 € VB") - must NOT be lost or zeroed
    p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info("200 € VB")
    assert p == 200.0
    assert is_vb
    assert not needs_neg
    assert not is_fake

    p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info("VB 350 €")
    assert p == 350.0
    assert is_vb
    assert not needs_neg
    assert not is_fake

    # Thousands separator: "1.250 € VB"
    p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info("1.250 € VB")
    assert p == 1250.0
    assert is_vb
    assert not is_fake

    # Strikethrough/price reduction: "500 € 420 € VB" -> takes last match
    p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info("500 € 420 € VB")
    assert p == 420.0
    assert is_vb

    # 3. Pure VB (no numbers)
    p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info("VB")
    assert p == 0.0
    assert is_vb
    assert needs_neg
    assert not is_fake

    # 4. Fake placeholder <= 5€
    p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info("1 € VB")
    assert p == 1.0
    assert is_vb
    assert not needs_neg
    assert is_fake

    p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info("5 €")
    assert p == 5.0
    assert is_fake

def test_parse_astro_article():
    scraper = KleinanzeigenScraper()
    html = """
    <article data-adid="291823719" data-href="/s-anzeige/rtx-3070-msi-gaming-x/291823719-225-1234">
        <script type="application/ld+json">
        {
            "title": "MSI GeForce RTX 3070 Gaming X Trio 8GB",
            "description": "Verkaufe meine einwandfreie RTX 3070 wegen Upgrade auf RTX 4080.",
            "contentUrl": "https://img.kleinanzeigen.de/api/v1/prod-ads/images/123/full.jpg"
        }
        </script>
        <div>
            <span class="price-title3">280 € VB</span>
            <span>10115 Berlin Mitte</span>
            <span>Heute, 14:30</span>
        </div>
    </article>
    """
    soup = BeautifulSoup(html, 'html.parser')
    ad = soup.find('article')
    listing = scraper._parse_article(ad)

    assert listing is not None
    assert listing.title == "MSI GeForce RTX 3070 Gaming X Trio 8GB"
    assert "RTX 4080" in listing.description
    assert listing.price == 280.0
    assert listing.is_vb is True
    assert listing.needs_negotiation is False
    assert listing.is_fake_placeholder is False
    assert listing.image_url == "https://img.kleinanzeigen.de/api/v1/prod-ads/images/123/full.jpg"
    assert "291823719" in listing.url

def test_fetch_detail_page_enrichment():
    from unittest.mock import MagicMock
    from hardware_crawler.models import Listing

    scraper = KleinanzeigenScraper()
    listing = Listing(
        title="Gaming PC",
        price=600.0,
        url="https://www.kleinanzeigen.de/s-anzeige/gaming-pc-rtx-3070/123",
        description="Teaser description..."
    )

    detail_html = """
    <html>
        <body>
            <p id="viewad-description-text">
                Ausführliche Beschreibung:
                Mainboard: MSI B550 Gaming Plus
                CPU: AMD Ryzen 5 5600X
                RAM: 32GB Corsair Vengeance DDR4-3600
                SSD: 1TB Samsung 980 Pro M.2 NVMe
                Netzteil: 750W BeQuiet Pure Power 11 FM
            </p>
            <div class="viewad-actions">
                <button>Direkt kaufen</button>
                <span>Versand möglich (+ 6,99 €)</span>
            </div>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = detail_html
    scraper.scraper.get = MagicMock(return_value=mock_resp)

    ok = scraper.fetch_detail_page(listing)
    assert ok is True
    assert "MSI B550" in listing.description
    assert "Samsung 980 Pro" in listing.description
    assert listing.has_buyer_protection is True
    assert listing.shipping_available is True

def test_dom_price_priority_over_description_currency():
    scraper = KleinanzeigenScraper()
    # Ad with description containing 'Neupreis 800 €' but dedicated price is 250 €
    html = """
    <article data-adid="998877" data-href="/s-anzeige/gpu/998877">
        <h2>GeForce RTX 3070 8GB</h2>
        <p class="aditem-main--middle--description">Verkaufe meine GPU, Neupreis 800 €, läuft super.</p>
        <span class="aditem-main--middle--price-shipping--price">250 €</span>
    </article>
    """
    soup = BeautifulSoup(html, 'html.parser')
    ad = soup.find('article')
    listing = scraper._parse_article(ad)

    assert listing is not None
    assert listing.price == 250.0
    assert listing.is_vb is False
    assert listing.raw_attributes.get("price_source") != "description_fallback"

def test_pure_vb_description_wunschpreis_fallback():
    scraper = KleinanzeigenScraper()
    # Ad with DOM price 'VB' and description mentioning Wunschpreis 220 €
    html = """
    <article data-adid="998878" data-href="/s-anzeige/gpu/998878">
        <h2>GeForce RTX 3070 8GB</h2>
        <p class="aditem-main--middle--description">Macht Angebote, mein Wunschpreis 220 € oder Tausch.</p>
        <p data-testid="ad-price">VB</p>
    </article>
    """
    soup = BeautifulSoup(html, 'html.parser')
    ad = soup.find('article')
    listing = scraper._parse_article(ad)

    assert listing is not None
    assert listing.price == 220.0
    assert listing.is_vb is True
    assert listing.needs_negotiation is False
    assert listing.raw_attributes.get("price_source") == "description_fallback"

def test_fetch_detail_page_wunschpreis_fallback():
    from unittest.mock import MagicMock
    from hardware_crawler.models import Listing

    scraper = KleinanzeigenScraper()
    listing = Listing(
        title="GeForce RTX 3070 8GB",
        price=0.0,
        url="https://www.kleinanzeigen.de/s-anzeige/gpu/998879",
        description="Teaser...",
        is_vb=True,
        needs_negotiation=True
    )

    detail_html = """
    <html>
        <body>
            <div id="viewad-description-text">
                Verkaufe meine RTX 3070 wegen Umstieg.
                Abzugeben für 230 € Festpreis oder macht mir faire Angebote.
            </div>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = detail_html
    scraper.scraper.get = MagicMock(return_value=mock_resp)

    ok = scraper.fetch_detail_page(listing)
    assert ok is True
    assert listing.price == 230.0
    assert listing.is_vb is True
    assert listing.needs_negotiation is False
    assert listing.raw_attributes.get("price_source") == "description_fallback"

