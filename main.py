import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import email.utils
import os
from langchain_google_genai import ChatGoogleGenerativeAI

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",  # fast + free tier friendly
    temperature=0.3
)
RSS_FEEDS = [
    # Google News (broad coverage)
    "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-IN&gl=IN&ceid=IN:en",

    # Additional sources
    "https://feeds.feedburner.com/TechCrunch/artificial-intelligence",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://www.wired.com/feed/tag/ai/latest/rss"
]

KEYWORDS = [
    "ai", "artificial intelligence", "machine learning",
    "llm", "gpt", "openai", "deepmind", "anthropic", "algorithm", "neural network", "transformer", "generative ai", "ai model", "ai research", "ai breakthrough", "ai development", "ai application", "ai ethics", "ai regulation", "ai safety", "ai impact", "ai adoption", "ai innovation", "ai startup", "ai funding", "ai investment", "large language model", "ai assistant", "ai chatbot", "ai tool", "ai platform", "ai framework", "ai system", "ai technology", "ai trend", "ai news",
]

# -----------------------------
# Helpers
# -----------------------------
def filter_with_gemini(news_items):
    prompt = """You are an expert AI news curator.

From the list below, keep ONLY high-quality AI-related news.

KEEP:
- Major developments
- Product launches
- Research breakthroughs
- Policy/regulation

Return ONLY a numbered list with title and link.

News:
"""

    for i, (title, link) in enumerate(news_items, 1):
        prompt += f"{i}. {title}\n{link}\n\n"

    response = llm.invoke(prompt)

    return response.content

def summarize_with_gemini(filtered_news_text):
    prompt = f"""
Summarize the following AI news into a concise morning briefing.

Focus on:
- Key trends
- Important developments
- Keep it short and readable
- Only return plain text
News:
{filtered_news_text}
"""

    response = llm.invoke(prompt)
    return response.content

def is_recent(pub_date):
    try:
        published = email.utils.parsedate_to_datetime(pub_date)

        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        else:
            published = published.astimezone(timezone.utc)

        return datetime.now(timezone.utc) - published < timedelta(days=1)
    except:
        return False  # skip if date parsing fails


def fetch_feed(url):
    try:
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)
        return root.findall(".//item")
    except:
        return []


# -----------------------------
# Main Logic
# -----------------------------

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

    # -----------------------------
    # Step 2: Gemini filtering
    # -----------------------------
    filter_prompt = """You are an expert AI news curator.

From the list below, keep ONLY high-quality AI-related news.

KEEP:
- Major developments
- Product launches
- Research breakthroughs
- Policy/regulation

Return ONLY a clean numbered list with title and link.

News:
"""

    for i, (title, link) in enumerate(filtered_news, 1):
        filter_prompt += f"{i}. {title}\n{link}\n\n"

    filtered_response = llm.invoke(filter_prompt).content.strip()

    if not filtered_response:
        return "📰 No relevant AI news found."

    # -----------------------------
    # Step 3: Gemini summarization
    # -----------------------------
    summary_prompt = f"""
Summarize the following AI news into a concise morning briefing.

Focus on:
- Key trends
- Important developments
- Keep it short and readable

News:
{filtered_response}
"""

    summary = llm.invoke(summary_prompt).content.strip()

    # -----------------------------
    # Final output
    # -----------------------------
    return f"🧠 AI Morning Brief (Last 24h):\n\n{summary}"


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    requests.post(url=url, data=payload)


# -----------------------------
# Run
# -----------------------------

if __name__ == "__main__":
    raw_news = get_news()  # returns list of (title, link)

    if not raw_news:
        send_telegram("No news found.")
    else:
        filtered = filter_with_gemini(raw_news)
        summary = summarize_with_gemini(filtered)

        message = f"🧠 AI Morning Brief:\n\n{summary}"
        send_telegram(message)