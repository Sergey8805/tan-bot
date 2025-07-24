# news_bot.py (Версия 2.0 - на RSS-каналах)

import os
import requests
import google.generativeai as genai
import feedparser # Новая библиотека для работы с RSS
import time
from html import unescape # Для очистки HTML-тегов из описаний

# --- 1. Функция для сбора новостей из списка RSS-каналов ---
def get_news_from_rss(rss_urls):
    print("Этап 1: Получение новостей из RSS-каналов...")
    articles = []
    seen_titles = set() # Множество для отслеживания дубликатов заголовков

    for url in rss_urls:
        try:
            print(f"  -> Загружаю канал: {url}")
            feed = feedparser.parse(url)
            
            for entry in feed.entries:
                # Проверяем на дубликаты по заголовку
                if entry.title not in seen_titles:
                    # Очищаем описание от HTML-тегов, если они есть
                    description = unescape(entry.summary) if 'summary' in entry else ''
                    
                    articles.append({
                        'title': entry.title,
                        'description': description,
                        'url': entry.link,
                        'source': feed.feed.title # Используем название самого канала как источник
                    })
                    seen_titles.add(entry.title)
        except Exception as e:
            print(f"    !! Ошибка при обработке канала {url}: {e}")

    print(f"Собрано уникальных новостей для анализа: {len(articles)}")
    return articles

# --- Функции summarize_with_gemini и send_to_telegram остаются без изменений ---

# --- 2. Функция для анализа и суммаризации с помощью Gemini (без изменений) ---
def summarize_with_gemini(articles, api_key):
    print("\nЭтап 2: Фильтрация и суммаризация с помощью Gemini...")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

    summarized_articles = []
    # Так как мы уже отобрали источники, можно немного ослабить промпт Gemini
    # и просто просить его делать саммари.
    for article in articles:
        title = article.get('title')
        description = article.get('description', '')
        url = article.get('url')
        source = article.get('source')

        # Теперь Gemini не нужно фильтровать, а только делать саммари
        prompt = f"""
        Сделай краткую выжимку (саммари) на РУССКОМ языке в 1-2 предложениях для следующей новости.
        Передай только главную суть.

        Заголовок: "{title}"
        Описание: "{description}"

        Твой ответ должен быть только текстом саммари.
        """
        try:
            print(f"Анализирую: {title[:60]}...")
            response = model.generate_content(prompt)
            summary = response.text.strip()

            if summary: # Просто проверяем, что ответ не пустой
                summarized_articles.append({
                    'title': title, 'summary_ru': summary,
                    'url': url, 'source': source
                })
        except Exception as e:
            print(f"Ошибка Gemini API: {e}")
        time.sleep(1)

    print(f"Анализ завершен. Обработано новостей: {len(summarized_articles)}")
    return summarized_articles


# --- 3. Функция для отправки сообщений в Telegram (без изменений) ---
def send_to_telegram(articles, bot_token, channel_id):
    print("\nЭтап 3: Отправка новостей в Telegram...")
    total_sent = 0
    # Отправляем не больше 15 новостей, чтобы не спамить в канал
    for article in articles[:15]:
        title = article['title'].replace('-', '\\-').replace('.', '\\.').replace('!', '\\!').replace('(', '\\(').replace(')', '\\)')
        summary = article['summary_ru'].replace('-', '\\-').replace('.', '\\.').replace('!', '\\!').replace('(', '\\(').replace(')', '\\)')
        source = str(article['source']).replace('-', '\\-').replace('.', '\\.').replace('!', '\\!').replace('(', '\\(').replace(')', '\\)')
        url = article['url']

        message_text = (
            f"*{title}*\n\n"
            f"{summary}\n\n"
            f"Источник: {source}\n"
            f"[Читать оригинал]({url})"
        )

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        params = {'chat_id': channel_id, 'text': message_text, 'parse_mode': 'MarkdownV2', 'disable_web_page_preview': True}
        
        response = requests.post(url, data=params)
        if response.status_code == 200:
            print(f"  -> Новость '{title[:30]}...' успешно отправлена.")
            total_sent += 1
        else:
            print(f"  -> Ошибка отправки: {response.status_code}, {response.text}")
        time.sleep(2)

    print(f"Отправка завершена. Всего отправлено: {total_sent}")

# --- Основной блок для запуска ---
if __name__ == "__main__":
    print("Запуск AI-новостного бота (v2.0 - RSS)...")

    # !!! ВСТАВЬТЕ СЮДА ВАШ СПИСОК RSS-КАНАЛОВ !!!
    RSS_FEEDS = [
	"https://feeds.reuters.com/reuters/technologyNews"
	"https://feeds.bloomberg.com/technology/news.rss"
	"https://www.theverge.com/rss/index.xml"
	"http://feeds.arstechnica.com/arstechnica/index/"
	"https://www.technologyreview.com/topic/artificial-intelligence/feed/"
	"https://www.kdnuggets.com/feed"
	"https://www.analyticsinsight.net/feed/"
	"https://www.rcrwireless.com/feed"
	"http://feeds.feedburner.com/TeleGeographyBlog"
	"http://feeds.google.com/googleaiblog/"
	"https://openai.com/blog.rss"
	"https://blogs.nvidia.com/blog/category/artificial-intelligence/feed/"
	"https://a16z.com/feed/"
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.wired.com/feed/category/artificial-intelligence/latest/rss",
        "https://feeds.feedburner.com/Venturebeat/AI",
        "https://www.lightreading.com/rss_feed.asp",
        "https://www.fiercetelecom.com/rss.xml",
        # Добавьте сюда остальные найденные вами каналы
    ]
    
    GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHANNEL = os.environ.get('TELEGRAM_CHANNEL_ID')

    if not all([GEMINI_KEY, TELEGRAM_TOKEN, TELEGRAM_CHANNEL]):
        print("Ошибка: Один или несколько API-ключей не найдены в переменных окружения.")
    else:
        raw_articles = get_news_from_rss(RSS_FEEDS)
        if raw_articles:
            # Перемешиваем статьи, чтобы в топе были новости из разных источников
            import random
            random.shuffle(raw_articles)
            
            summarized = summarize_with_gemini(raw_articles, GEMINI_KEY)
            if summarized:
                send_to_telegram(summarized, TELEGRAM_TOKEN, TELEGRAM_CHANNEL)
    
    print("\nРабота бота завершена.")
