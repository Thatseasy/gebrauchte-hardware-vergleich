import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
from .models import Product, ComponentType, Listing, CanonicalSpec
from .database import DatabaseManager

class PassmarkScraper:
    """Scrapes CPU and GPU benchmarks from Passmark Software sites."""
    
    BASE_URL_CPU = "https://www.cpubenchmark.net/high_end_cpus.html" # Focus on high end for gaming
    BASE_URL_GPU = "https://www.videocardbenchmark.net/high_end_gpus.html"
    
    def fetch_cpu_data(self) -> List[Product]:
        """Fetches high-end CPU data."""
        return self._scrape_passmark_chart(self.BASE_URL_CPU, ComponentType.CPU)

    def fetch_gpu_data(self) -> List[Product]:
        """Fetches high-end GPU data."""
        return self._scrape_passmark_chart(self.BASE_URL_GPU, ComponentType.GPU)
    
    def _scrape_passmark_chart(self, url: str, c_type: ComponentType) -> List[Product]:
        print(f"Fetching data from {url}...")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            products = []
            # Passmark uses a 'chart' id for the table usually, or look for class 'chartlist'
            chart_list = soup.select('ul.chartlist li')
            
            for item in chart_list:
                # Structure usually: <span class="prdname">Name</span> <span class="count">Score</span>
                name_el = item.select_one('.prdname')
                score_el = item.select_one('.count')
                
                if name_el and score_el:
                    name = name_el.get_text(strip=True)
                    try:
                        score = int(score_el.get_text(strip=True).replace(',', ''))
                        
                        # Generate a simple ID
                        p_id = f"{c_type.value}_{name.replace(' ', '_')}"
                        
                        products.append(Product(
                            id=p_id,
                            name=name,
                            type=c_type,
                            performance_score=score
                        ))
                    except ValueError:
                        continue
                        
            print(f"Found {len(products)} {c_type.value}s")
            return products
            
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return []

class KleinanzeigenScraper:
    """Scrapes Kleinanzeigen for used hardware."""
    
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

    def search(self, query: str, radius: int = 0, location: str = "") -> List[Listing]:
        """Legacy search, wraps search_with_text"""
        return self._perform_search([query], radius, location)
    
    def search_for_spec(self, spec: CanonicalSpec, radius: int = 0, location: str = "") -> List[Listing]:
        """Searches using optimized queries from CanonicalSpec."""
        # Use the compiled search queries from the spec
        queries = spec.search_queries
        if not queries:
            queries = [spec.name]
            
        print(f"Searching for {spec.name} with queries: {queries}")
        return self._perform_search(queries, radius, location)

    def _perform_search(self, queries: List[str], radius: int, location: str) -> List[Listing]:
        all_listings = []
        seen_urls = set()
        
        for q in queries:
            # Basic sleep/delay could be added here to avoid rate limits
            url_part = f"s-anzeige:angebote/{q.replace(' ', '-')}/k0"
            if location and radius > 0:
                 url_part = f"s-anzeige:angebote/{location}/radius-{radius}/{q.replace(' ', '-')}/k0"
                 
            url = f"{self.BASE_URL}/{url_part}"
            print(f"Scraping: {url}")
            
            try:
                response = self.scraper.get(url, timeout=15)
                if response.status_code != 200:
                    print(f"Failed to fetch {url}: {response.status_code}")
                    continue
                
                # Sanitize HTML to prevent html.parser int() crashes on broken &#8203 entities
                cleaned_html = response.text.replace('&#8203', '').replace('\u200b', '')
                soup = BeautifulSoup(cleaned_html, 'html.parser')
                ad_items = soup.select('article.aditem')
                
                for ad in ad_items:
                    try:
                        title_el = ad.select_one('.text-module-begin a')
                        if not title_el: continue
                        link = self.BASE_URL + title_el['href']
                        
                        if link in seen_urls:
                            continue
                        seen_urls.add(link)
                        
                        title = title_el.get_text(strip=True).replace('\u200b', '')
                        
                        price_el = ad.select_one('.aditem-main--middle--price-shipping--price')
                        price_str = price_el.get_text(strip=True).replace('\u200b', '') if price_el else "0"
                        price = self._parse_price(price_str)
                        
                        loc_el = ad.select_one('.aditem-main--top--left')
                        loc = loc_el.get_text(strip=True).replace('\u200b', '') if loc_el else "Unknown"
                        
                        desc_el = ad.select_one('.aditem-main--middle--description')
                        desc = desc_el.get_text(strip=True) if desc_el else ""
                        
                        date_el = ad.select_one('.aditem-main--top--right')
                        date_posted = date_el.get_text(strip=True) if date_el else None
                        
                        l = Listing(
                            title=title,
                            price=price,
                            url=link,
                            platform="Kleinanzeigen",
                            location=loc,
                            description=desc,
                            date_posted=date_posted,
                            # Initialize empty containers for next steps
                            raw_attributes={},
                            normalized_attributes={}
                        )
                        all_listings.append(l)
                        
                    except Exception as e:
                        print(f"Error parsing ad: {e}")
                        continue
                        
            except Exception as e:
                print(f"Error scraping {url}: {e}")
                
        print(f"Total found unique listings: {len(all_listings)}")
        return all_listings

    def _parse_price(self, price_str: str) -> float:
        # Extrahiere alle potenziellen Preisangaben (Zahlen mit optionalem Komma/Punkt)
        # Kleinanzeigen Format: "1.200 €" oder "450 € VB" oder "gesenkt 400 € 350 €"
        s = price_str.replace('VB', '').replace('€', '').replace('\u200b', '').replace('&#8203', '')
        
        matches = re.findall(r'\d+(?:[.,]\d+)*', s)
        if not matches:
            return 0.0
            
        # Nimm den letzten gefundenen Preis (oft der "neue" reduzierte Preis)
        last_match = matches[-1]
        
        # Bereinige für float()
        clean_num = last_match.replace('.', '').replace(',', '.')
        try:
            return float(clean_num)
        except:
            return 0.0

class GeizhalsScraper:
    """Placeholder for Geizhals Scraper."""
    def __init__(self):
        pass
