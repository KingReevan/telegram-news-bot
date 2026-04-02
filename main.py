import requests
import xml.etree.ElementTree as ET

BOT_TOKEN = "8646608685:AAGMjzH-2vPjbS6J0zreHGiUZCLJTojJou4"
CHAT_ID = "1702051217"

RSS_URL = "http://feeds.bbci.co.uk/news/rss.xml"

def get_news():
    response = requests.get(RSS_URL)
    root = ET.fromstring(response.content)

    items = root.findall(".//item")[:5]

    news_list = []
    for i, item in enumerate(items, 1):
        title = item.find("title").text
        link = item.find("link").text
        news_list.append(f"{i}. {title}\n{link}")

    return "\n\n".join(news_list)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    requests.post(url, data=payload)

if __name__ == "__main__":
    news = get_news()
    message = f"📰 Morning News:\n\n{news}"
    send_telegram(message)