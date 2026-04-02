import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import email.utils
import os
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from typing import List, Tuple

load_dotenv()

BOT_TOKEN = os.getenv(key="TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv(key="TELEGRAM_CHAT_ID")
GOOGLE_API_KEY = os.getenv(key="GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv(key="OPENAI_API_KEY")

RSS_FEEDS = [
    # Google News (broad coverage)
    "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-IN&gl=IN&ceid=IN:en",
    # Additional sources
    "https://feeds.feedburner.com/TechCrunch/artificial-intelligence",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://www.wired.com/feed/tag/ai/latest/rss",
]


def get_llm():
    provider = os.getenv(key="LLM_PROVIDER", default="gemini")

    if provider == "openai":
        return ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

    elif provider == "gemini":
        return ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.3)

    else:
        raise ValueError(f"Unsupported provider: {provider}")


llm = get_llm()


def is_recent(pub_date):
    try:
        published = email.utils.parsedate_to_datetime(pub_date)

        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        else:
            published = published.astimezone(timezone.utc)

        return datetime.now(timezone.utc) - published < timedelta(days=1)
    except Exception as e:
        print(f"Error parsing date: {e}")
        return False  # skip if date parsing fails


def fetch_feed(url):
    try:
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)
        return root.findall(".//item")
    except Exception as e:
        print(f"Error fetching feed: {e}")
        return []


def ai_link_filter(news: List[Tuple[str, str]]) -> str:
    base_filter_prompt = """You are an expert AI news curator.

From the list below, keep ONLY high-quality AI-related news.

KEEP:
- Major developments
- Product launches
- Research breakthroughs
- Policy/regulation

Return ONLY a clean numbered list with title and link.

News:
"""

    chunk_size = 5
    filtered_chunks = []

    for start in range(0, len(news), chunk_size):
        chunk = news[start : start + chunk_size]
        filter_prompt = base_filter_prompt

        for i, (title, link) in enumerate(chunk, 1):
            filter_prompt += f"{i}. {title}\n{link}\n\n"

        chunk_response = llm.invoke(input=filter_prompt).content.strip()
        if chunk_response:
            filtered_chunks.append(chunk_response)

    filtered_response = "\n\n".join(filtered_chunks).strip()

    if not filtered_response:
        return "😭😭 No relevant AI news found. 😭😭"

    return filtered_response


def get_news():
    seen_titles = set()
    filtered_news = []

    # -----------------------------
    # Step 1: Collect + basic filtering
    # -----------------------------
    for feed in RSS_FEEDS:
        items = fetch_feed(feed)

        for item in items:
            title_elem = item.find("title")
            link_elem = item.find("link")
            date_elem = item.find("pubDate")

            if title_elem is None or link_elem is None:
                continue

            title_text = title_elem.text
            link_text = link_elem.text

            if not title_text or not link_text:
                continue

            title = title_text.strip()
            link = link_text.strip()
            pub_date = date_elem.text if date_elem is not None else None

            # Filter: Last 24 hours
            if pub_date and not is_recent(pub_date):
                continue

            # Deduplication
            if title in seen_titles:
                continue
            seen_titles.add(title)

            filtered_news.append((title, link))

    # Limit raw items (before Gemini to save tokens)
    filtered_news = filtered_news[:20]

    if not filtered_news:
        return "📰 No recent news found."

    # Get AI related links
    filtered_response: str = ai_link_filter(news=filtered_news)

    summary_prompt = f"""
Summarize the following AI news.

Focus on:
- Key trends
- Important developments
- Make it easy to understand for a busy professional
- Give plain text, not markdown

News:
{filtered_response}
"""

    summary = llm.invoke(input=summary_prompt).content.strip()

    return f"🧠 AI Morning Brief (Last 24h):\n\n{summary}"


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url=url, data=payload)


if __name__ == "__main__":
    summary = get_news()  # returns list of (title, link)

    if not summary:
        send_telegram(message="No news found.")
    else:
        send_telegram(message=summary)
