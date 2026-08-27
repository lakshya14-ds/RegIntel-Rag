import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any

class MoneycontrolScraper:
    BASE_URL = "https://www.moneycontrol.com"
    REGULATORY_NEWS_URL = "https://www.moneycontrol.com/news/business/economy/"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def fetch_latest_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        articles = []
        try:
            response = self.session.get(self.REGULATORY_NEWS_URL, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            news_items = soup.find_all("li", {"class": "clearfix"})
            for item in news_items[:limit]:
                h2 = item.find("h2")
                if not h2:
                    continue
                a_tag = h2.find("a")
                if not a_tag:
                    continue
                
                title = a_tag.get_text(strip=True)
                url = a_tag["href"] if a_tag.has_attr("href") else ""
                span_date = item.find("span")
                date_text = span_date.get_text(strip=True) if span_date else ""

                articles.append({
                    "source": "Moneycontrol",
                    "title": title,
                    "date": date_text,
                    "url": url
                })
        except Exception as e:
            print(f"Error scraping Moneycontrol news: {e}")

        return articles

    def fetch_article_content(self, url: str) -> str:
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            article_body = soup.find("div", {"class": "content_wrapper"}) or soup.find("article")
            return article_body.get_text(separator=" ", strip=True) if article_body else ""
        except Exception as e:
            print(f"Error fetching article from {url}: {e}")
            return ""
