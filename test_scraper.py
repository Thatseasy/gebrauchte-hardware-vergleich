import cloudscraper
from bs4 import BeautifulSoup

url = "https://www.kleinanzeigen.de/s-7800X3D/k0"
# url = "https://www.kleinanzeigen.de/s-gaming-pc/k0"
print(f"Fetching {url} with cloudscraper...")

scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

response = scraper.get(url)

print(f"Status Code: {response.status_code}")
soup = BeautifulSoup(response.text, 'html.parser')

articles = soup.find_all('article', class_='aditem')
print(f"Total articles found: {len(articles)}")

if len(articles) == 0:
    for h1 in soup.find_all('h1'):
         print("H1 text:", h1.text.strip())
