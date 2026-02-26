from hardware_crawler.scrapers import PassmarkScraper
from hardware_crawler.models import ComponentType

def test_passmark():
    scraper = PassmarkScraper()
    print("Testing CPU Fetch...")
    cpus = scraper.fetch_cpu_data()
    print(f"Fetched {len(cpus)} CPUs")
    if cpus:
        print(f"Sample: {cpus[0]}")

    print("Testing GPU Fetch...")
    gpus = scraper.fetch_gpu_data()
    print(f"Fetched {len(gpus)} GPUs")
    if gpus:
        print(f"Sample: {gpus[0]}")

def test_kleinanzeigen():
    from hardware_crawler.scrapers import KleinanzeigenScraper
    scraper = KleinanzeigenScraper()
    print("Testing Kleinanzeigen Search for 'RTX 3070'...")
    listings = scraper.search("RTX 3070", radius=50, location="10115")
    print(f"Found {len(listings)} listings")
    for l in listings[:3]:
        print(f" - {l.title} | {l.price}€ | {l.location}")

if __name__ == "__main__":
    # test_passmark()
    test_kleinanzeigen()
