import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple, Any
import re
import json
import logging
from .models import Product, ComponentType, Listing, CanonicalSpec
from .database import DatabaseManager

logger = logging.getLogger(__name__)

class PassmarkScraper:
    """Scrapes CPU and GPU benchmarks from Passmark Software sites with Cloudflare protection handling."""
    
    BASE_URL_CPU = "https://www.cpubenchmark.net/high_end_cpus.html"
    BASE_URL_GPU = "https://www.videocardbenchmark.net/high_end_gpus.html"
    
    def __init__(self):
        import cloudscraper
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )

    def fetch_cpu_data(self) -> List[Product]:
        """Fetches high-end CPU data."""
        return self._scrape_passmark_chart(self.BASE_URL_CPU, ComponentType.CPU)

    def fetch_gpu_data(self) -> List[Product]:
        """Fetches high-end GPU data."""
        return self._scrape_passmark_chart(self.BASE_URL_GPU, ComponentType.GPU)
    
    def _scrape_passmark_chart(self, url: str, c_type: ComponentType) -> List[Product]:
        logger.info(f"Fetching benchmark data from {url}...")
        try:
            response = self.scraper.get(url, timeout=15)
            if response.status_code != 200:
                logger.error(f"Passmark fetch returned status {response.status_code}")
                return []
                
            soup = BeautifulSoup(response.content, 'html.parser')
            products = []
            chart_list = soup.select('ul.chartlist li')
            
            for item in chart_list:
                name_el = item.select_one('.prdname')
                score_el = item.select_one('.count')
                
                if name_el and score_el:
                    name = name_el.get_text(strip=True)
                    try:
                        score = int(score_el.get_text(strip=True).replace(',', ''))
                        p_id = f"{c_type.value}_{name.replace(' ', '_')}"
                        products.append(Product(
                            id=p_id,
                            name=name,
                            type=c_type,
                            performance_score=score
                        ))
                    except ValueError:
                        continue
                        
            logger.info(f"Fetched {len(products)} {c_type.value} benchmarks from Passmark.")
            return products
            
        except Exception as e:
            logger.error(f"Error fetching Passmark {url}: {e}")
            return []

class KleinanzeigenScraper:
    """
    Resilient scraper for Kleinanzeigen supporting:
    - Modern Astro / Tailwind frontend (`article[data-adid]` & embedded Schema.org JSON-LD)
    - Legacy fallback (`article.aditem`)
    - Precision 4-tier VB price parsing (preserves '200 € VB' offers)
    """
    
    BASE_URL = "https://www.kleinanzeigen.de"
    
    def __init__(self):
        import cloudscraper
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self.db = DatabaseManager()
        self.last_error = None

    def search(self, query: str, radius: int = 0, location: str = "") -> List[Listing]:
        """Legacy search, wraps search_with_text"""
        return self._perform_search([query], radius, location)
    
    def search_for_spec(self, spec: CanonicalSpec, radius: int = 0, location: str = "") -> List[Listing]:
        """Searches using optimized queries from CanonicalSpec."""
        queries = spec.search_queries
        if not queries:
            queries = [spec.name]
            
        logger.info(f"Searching for {spec.name} with queries: {queries}")
        return self._perform_search(queries, radius, location)

    def _perform_search(self, queries: List[str], radius: int, location: str) -> List[Listing]:
        all_listings = []
        seen_urls = set()
        self.last_error = None
        
        for q in queries:
            # Clean search query URL part
            clean_q = re.sub(r'[^\w\s-]', '', q).strip().replace(' ', '-')
            url_part = f"s-anzeige:angebote/{clean_q}/k0"
            if location and radius > 0:
                url_part = f"s-anzeige:angebote/{location}/radius-{radius}/{clean_q}/k0"
                 
            url = f"{self.BASE_URL}/{url_part}"
            logger.info(f"Scraping Kleinanzeigen: {url}")
            
            try:
                response = self.scraper.get(url, timeout=15)
                if response.status_code == 429:
                    self.last_error = "HTTP_429_RATE_LIMIT"
                    logger.error(f"Rate limited by Kleinanzeigen (HTTP 429): {url}")
                    raise requests.exceptions.HTTPError(f"HTTP 429 Rate Limited: {url}")
                elif response.status_code == 403:
                    self.last_error = "HTTP_403_BOT_CHALLENGE"
                    logger.warning(f"Cloudflare bot protection challenge (HTTP 403): {url}")
                    continue
                elif response.status_code != 200:
                    self.last_error = f"HTTP_{response.status_code}"
                    logger.warning(f"Failed to fetch {url}: {response.status_code}")
                    continue
                
                # Sanitize HTML
                cleaned_html = response.text.replace('&#8203', '').replace('\u200b', '')
                soup = BeautifulSoup(cleaned_html, 'html.parser')
                
                # 1. Primary: Modern Astro articles with data-adid
                articles = soup.find_all('article', attrs={'data-adid': True})
                
                # 2. Fallback: Legacy aditem articles
                if not articles:
                    articles = soup.select('article.aditem')
                if not articles:
                    articles = soup.find_all('article')
                    
                for ad in articles:
                    try:
                        listing = self._parse_article(ad)
                        if not listing:
                            continue
                            
                        if listing.url in seen_urls:
                            continue
                        seen_urls.add(listing.url)
                        all_listings.append(listing)
                        
                    except Exception as e:
                        logger.error(f"Error parsing ad article: {e}")
                        continue
                        
            except requests.exceptions.HTTPError:
                raise
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                
        logger.info(f"Total found unique listings: {len(all_listings)}")
        return all_listings

    def _parse_article(self, ad) -> Optional[Listing]:
        """Parses a single <article> tag extracting Schema.org JSON-LD and DOM attributes."""
        # 1. URL / Link extraction
        href = ad.get('data-href')
        if not href:
            link_el = ad.select_one('a[href*="/s-anzeige/"]')
            href = link_el['href'] if link_el else None
            
        if not href:
            return None
            
        full_url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
        
        # 2. Extract Schema.org JSON-LD (Primary data source in Astro frontend)
        title = ""
        description = ""
        image_url = None
        
        sc = ad.find('script', type='application/ld+json')
        if sc and sc.string:
            try:
                ld_data = json.loads(sc.string)
                title = ld_data.get('title', '').strip()
                description = ld_data.get('description', '').strip()
                image_url = ld_data.get('contentUrl')
            except Exception:
                pass
                
        # 3. DOM Fallbacks for Title & Description
        if not title:
            title_el = ad.select_one('h2, h3, .text-module-begin a')
            title = title_el.get_text(strip=True) if title_el else "Unbekanntes Angebot"
            
        if not description:
            desc_el = ad.select_one('.aditem-main--middle--description, p[class*="onSurfaceSubdued"], p[class*="description"]')
            description = desc_el.get_text(strip=True) if desc_el else ""

        # 4. Image Fallback
        if not image_url:
            img_el = ad.select_one('img[src*="img.kleinanzeigen.de"]')
            image_url = img_el.get('src') if img_el else None

        # 5. Location extraction
        loc = "Deutschland"
        loc_match = re.search(r'\b\d{5}\b\s+[\w\s-]+', ad.get_text())
        if loc_match:
            loc = loc_match.group(0).strip()
        else:
            loc_el = ad.select_one('.aditem-main--top--left')
            if loc_el:
                loc = loc_el.get_text(strip=True)

        # 6. Date posted
        date_el = ad.select_one('.aditem-main--top--right')
        date_posted = date_el.get_text(strip=True) if date_el else None

        # 7. DOM-First Price Selection (strictly excluding description nodes)
        price_str = ""
        
        def is_desc_node(node):
            classes = " ".join(node.get('class', []))
            if re.search(r'description|onSurfaceSubdued', classes, re.I):
                return True
            if node.find_parent(class_=re.compile(r'description|onSurfaceSubdued', re.I)):
                return True
            return False

        # Target selectors in strict order of priority
        dom_selectors = [
            '[data-testid="ad-price"]',
            '.aditem-main--middle--price-shipping--price',
            '.aditem-addon--price',
            '.aditem-main--middle--price',
            'p[class*="price"]',
            'span[class*="price"]'
        ]
        
        price_el = None
        for sel in dom_selectors:
            candidates = ad.select(sel)
            for cand in candidates:
                if is_desc_node(cand):
                    continue
                price_el = cand
                break
            if price_el:
                break
                
        if not price_el:
            # Fallback scan of tags, strictly excluding description nodes
            for tag in ad.find_all(['p', 'span']):
                if is_desc_node(tag):
                    continue
                text = tag.get_text()
                if '€' in text or 'VB' in text.split():
                    price_el = tag
                    break

        if price_el:
            price_str = price_el.get_text(strip=True)

        ad_text = ad.get_text()
        has_buyer_protection = "Direkt kaufen" in ad_text or "Sicher bezahlen" in ad_text
        shipping_available = "Versand möglich" in ad_text or "+ Versand" in ad_text

        price, is_vb, needs_negotiation, is_fake_placeholder = self.parse_price_info(price_str)
        raw_attributes = {}

        # Fallback to description ONLY if DOM yields pure VB without amount (price == 0.0 / needs_negotiation == True)
        if (price == 0.0 or needs_negotiation) and description:
            wunschpreis = self._extract_wunschpreis(description)
            if wunschpreis is not None:
                price = wunschpreis
                is_vb = True
                needs_negotiation = False
                raw_attributes["price_source"] = "description_fallback"

        return Listing(
            title=title,
            price=price,
            url=full_url,
            platform="Kleinanzeigen",
            location=loc,
            description=description,
            date_posted=date_posted,
            is_vb=is_vb,
            needs_negotiation=needs_negotiation,
            is_fake_placeholder=is_fake_placeholder,
            image_url=image_url,
            has_buyer_protection=has_buyer_protection,
            shipping_available=shipping_available,
            raw_attributes=raw_attributes,
            normalized_attributes={}
        )

    def fetch_detail_page(self, listing: Listing) -> bool:
        """
        Fetches the complete ad page for a listing.
        Enriches listing with the full multi-paragraph description,
        high-res image, and verified buyer protection status.
        """
        if not listing.url or not str(listing.url).startswith("http"):
            return False
            
        try:
            resp = self.scraper.get(listing.url, timeout=10)
            if resp.status_code != 200:
                return False
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Full description - support legacy and modern Tailwind/Astro classes
            desc_el = soup.select_one(
                '#viewad-description-text, div[itemprop="description"], '
                '[data-testid="ad-description"], .description-body, .ad-description'
            )
            if desc_el:
                full_desc = desc_el.get_text("\n", strip=True)
                if full_desc and len(full_desc) > len(listing.description):
                    listing.description = full_desc
                    
            page_text = soup.get_text()
            desc_text = desc_el.get_text(" ", strip=True) if desc_el else ""

            # Check dedicated action bar / badges
            action_elements = soup.select(
                '.action-box, .viewad-actions, .viewad-sidebar, [data-testid="ad-badges"], '
                '.badge-list, .btn-buy-now, button, .shipping-info'
            )
            action_text = " ".join(el.get_text() for el in action_elements)

            # Buyer Protection Check: check badge / button first, then page text without negations
            bp_negation = bool(re.search(r'\b(kein|keine|nicht|ohne)\s+(direkt\s*kauf\w*|sicher\s*bezahlen)', desc_text, re.IGNORECASE))
            bp_badge = any(k in action_text for k in ["Direktkauf", "Direkt kaufen", "Sicher bezahlen"])
            if bp_badge or ("Direkt kaufen" in page_text or "Sicher bezahlen" in page_text):
                if not bp_negation:
                    listing.has_buyer_protection = True
                else:
                    listing.has_buyer_protection = False

            # Shipping Check: check badge / button first, then page text without negations
            shipping_negation = bool(re.search(r'\b(kein|keine|nicht|definitiv\s+kein)\s+versand', desc_text, re.IGNORECASE))
            shipping_badge = any(k in action_text for k in ["Versand möglich", "Versand ab", "+ Versand"])
            if shipping_badge or ("Versand möglich" in page_text or "Versand ab" in page_text or "+ Versand" in page_text):
                if not shipping_negation:
                    listing.shipping_available = True
                else:
                    listing.shipping_available = False
                
            # High-res image fallback
            if not listing.image_url:
                img_el = soup.select_one('#viewad-image, img[itemprop="image"]')
                if img_el and img_el.get('src'):
                    listing.image_url = img_el['src']
                    
            # If listing was pure VB without amount, check enriched full description for Wunschpreis
            if (listing.price == 0.0 or listing.needs_negotiation) and listing.description:
                wunschpreis = self._extract_wunschpreis(listing.description)
                if wunschpreis is not None:
                    listing.price = wunschpreis
                    listing.is_vb = True
                    listing.needs_negotiation = False
                    listing.raw_attributes["price_source"] = "description_fallback"

            return True
        except Exception as e:
            logger.warning(f"Failed to fetch detail page for {listing.url}: {e}")
            return False

    @staticmethod
    def _extract_wunschpreis(text: Optional[str]) -> Optional[float]:
        r"""
        Extracts asking price mentioned inside text if present:
        Regex: r'(?i)(?:wunschpreis|festpreis|hätte\s*gerne|abzugeben\s*für|preis\s*:?)\s*(\d+(?:[.,]\d+)?)\s*€'
        """
        if not text:
            return None
        m = re.search(r'(?i)(?:wunschpreis|festpreis|hätte\s*gerne|abzugeben\s*für|preis\s*:?)\s*(\d+(?:[.,]\d+)?)\s*€', text)
        if not m:
            return None
        num_str = m.group(1).strip()
        try:
            if '.' in num_str and len(num_str.split('.')[1]) == 3:
                num_str = num_str.replace('.', '')
            num_str = num_str.replace(',', '.')
            return float(num_str)
        except Exception:
            return None

    @staticmethod
    def parse_price_info(price_str: Optional[str]) -> Tuple[float, bool, bool, bool]:
        """
        Extracts price and nuance flags from Kleinanzeigen price strings:
        Returns: (price, is_vb, needs_negotiation, is_fake_placeholder)
        
        Examples:
        - "200 €" -> (200.0, False, False, False)
        - "200 € VB" -> (200.0, True, False, False)
        - "VB 150 €" -> (150.0, True, False, False)
        - "VB" -> (0.0, True, True, False)
        - "1 € VB" -> (1.0, True, False, True)
        - "Zu verschenken" -> (0.0, False, False, False)
        """
        if not price_str or not isinstance(price_str, str):
            return (0.0, False, False, True)
            
        # Clean unicode artifacts, zero-width chars, HTML entities
        clean = (
            price_str.replace('\u200b', '')
            .replace('\u200e', '')
            .replace('\ufeff', '')
            .replace('&#8203;', '')
            .replace('&#8203', '')
            .replace('&nbsp;', ' ')
            .replace('\u00a0', ' ')
            .replace('\u202f', ' ')
            .strip()
        )
        
        if not clean:
            return (0.0, False, False, True)
            
        # Check for free giveaway offers
        if re.search(r'\b(zu\s*verschenken|kostenlos|schenken)\b', clean, re.IGNORECASE):
            return (0.0, False, False, False)
            
        # Negative price check
        if re.search(r'-\s*\d+', clean):
            return (0.0, False, False, True)
            
        # Merge space-separated thousands (e.g. "1 250 €" -> "1250 €")
        clean = re.sub(r'(\d+)\s+(\d{3})(?=\b|[.,]|$)', r'\1\2', clean)
        
        # VB / VHB / Verhandlungsbasis detection
        is_vb = bool(re.search(r'(?i)(?:\b|\d|€)(?:vb|vhb|v\.b\.|verhandlungsbasis)(?:\b|\d|€|\.|\s|$)', clean))
        
        # Strip trailing/prior metadata (NP, Neupreis, UVP, ehem., zzgl. Versand, etc.)
        s = clean
        # Strip parenthesized secondary prices: "(NP: 600€)", "(ehem. 500 €)", "(zzgl. 4,99 € Versand)"
        s = re.sub(r'\(.*?(?:NP|Neupreis|UVP|ehem|Versand|zzgl).*?\)', '', s, flags=re.IGNORECASE)
        # Strip secondary price prefixes: "UVP 600€", "ehem. 500 €", "zzgl. 5 €"
        s = re.sub(r'(?:NP|Neupreis|UVP|ehem\.?|zzgl\.?|Versand)\s*:?\s*\d+(?:[.,]\d+)*\s*€?', '', s, flags=re.IGNORECASE)
        # Strip negotiation words & currency
        s = re.sub(r'(?i)\b(?:verhandlungsbasis|v\.b\.|vhb|vb)\b', '', s)
        s = re.sub(r'(?i)verhandlungsbasis|v\.b\.|vhb|vb', '', s)
        s = re.sub(r'(?i)euro|€', '', s).strip()
        
        # Normalize German standard shorthand "300,-" -> "300"
        s = re.sub(r',-\b', '', s)
        
        matches = re.findall(r'\d+(?:[.,]\d+)*', s)
        
        if not matches:
            if is_vb:
                return (0.0, True, True, False)
            return (0.0, False, False, True)
            
        # If multiple numbers remain, take the last one (e.g. "500 € 420 € VB" -> 420)
        target_num = matches[-1]
        
        # Parse number format
        val = 0.0
        try:
            if '.' in target_num and ',' in target_num:
                if target_num.find('.') < target_num.find(','):
                    # German format: 1.250,50
                    cleaned = target_num.replace('.', '').replace(',', '.')
                else:
                    # US format: 1,250.50
                    cleaned = target_num.replace(',', '')
                val = float(cleaned)
            elif ',' in target_num:
                # Comma only: either decimal (12,50) or US thousands (1,250)
                parts = target_num.split(',')
                if len(parts) == 2 and len(parts[1]) == 3 and int(parts[0]) > 0:
                    val = float(parts[0] + parts[1])
                else:
                    val = float(target_num.replace(',', '.'))
            elif '.' in target_num:
                # Dot only: either decimal (12.50) or thousands (1.250)
                parts = target_num.split('.')
                if len(parts) == 2 and len(parts[1]) == 3 and int(parts[0]) > 0:
                    val = float(parts[0] + parts[1])
                else:
                    val = float(target_num)
            else:
                val = float(target_num)
        except Exception:
            return (0.0, is_vb, False, True)
            
        if val == 0.0:
            if is_vb:
                return (0.0, True, True, False)
            return (0.0, False, False, False)
            
        is_fake = (val <= 5.0)
        return (val, is_vb, False, is_fake)

class GeizhalsScraper:
    """Placeholder for Geizhals Scraper."""
    def __init__(self):
        pass
