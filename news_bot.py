# news_bot.py - Наш автоматизированный AI-новостной бот

import os
import requests
import google.generativeai as genai
import time

# --- 1. Функция для получения новостей из Mediastack ---
def get_news(api_key):
    print("Этап 1: Получение новостей из Mediastack...")
    params = {
        'access_key': api_key,
        'categories': 'technology',
        'languages': 'en',
        'sort': 'published_desc',
        'limit': 30  # Возьмем чуть больше, чтобы было из чего фильтровать
    }
    API_URL = 'http://api.mediastack.com/v1/news'
    response = requests.get(API_URL, params=params)

    if response.status_code == 200:
        articles = response.json().get('data', [])
        print(f"Найдено {len(articles)} новостей для анализа.")
        return articles
    else:
        print(f"Ошибка Mediastack: {response.status_code}, {response.text}")
        return None

# --- 2. Функция для анализа и суммаризации с помощью Gemini ---
def summarize_with_gemini(articles, api_key):
    print("\nЭтап 2: Фильтрация и суммаризация с помощью Gemini...")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

    summarized_articles = []
    for article in articles:
        title = article.get('title')
        description = article.get('description')
        url = article.get('url')
        source = article.get('source')

        if not title or not description:
            continue

        prompt = f"""
        Проанализируй следующий заголовок и описание новости.
        Заголовок: "{title}"
        Описание: "{description}"
        Твои задачи:
        1. Определи, относится ли эта новость к сфере искусственного интеллекта (AI, machine learning) ИЛИ к сфере телекоммуникаций (telecom, 5G, satellites).
        2. Если новость НЕ относится к этим сферам, ответь одним словом: НЕРЕЛЕВАНТНО.
        3. Если относится, сделай краткую выжимку (саммари) на РУССКОМ языке в 1-2 предложениях.
        Твой ответ должен быть только саммари или словом "НЕРЕЛЕВАНТНО".
        """
        try:
            print(f"Анализирую: {title[:50]}...")
            response = model.generate_content(prompt)
            summary = response.text.strip()

            if "НЕРЕЛЕВАНТНО" not in summary and summary:
                print("  -> Релевантно. Добавляю в список.")
                summarized_articles.append({
                    'title': title, 'summary_ru': summary,
                    'url': url, 'source': source
                })
            else:
                print("  -> Нерелевантно.")

        except Exception as e:
            print(f"Ошибка Gemini API: {e}")
        time.sleep(1) # Пауза между запросами к API

    print(f"Анализ завершен. Релевантных новостей: {len(summarized_articles)}")
    return summarized_articles

# --- 3. Функция для отправки сообщений в Telegram ---
def send_to_telegram(articles, bot_token, channel_id):
    print("\nЭтап 3: Отправка новостей в Telegram...")
    total_sent = 0
    for article in articles:
        # Markdown V2 требует экранирования специальных символов
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
        params = {
            'chat_id': channel_id,
            'text': message_text,
            'parse_mode': 'MarkdownV2',
            'disable_web_page_preview': True
        }
        
        response = requests.post(url, data=params)
        if response.status_code == 200:
            print(f"  -> Новость '{title[:30]}...' успешно отправлена.")
            total_sent += 1
        else:
            print(f"  -> Ошибка отправки: {response.status_code}, {response.text}")
        time.sleep(2) # Пауза между сообщениями

    print(f"Отправка завершена. Всего отправлено: {total_sent}")


# --- Основной блок для запуска ---
if __name__ == "__main__":
    print("Запуск AI-новостного бота...")
    
    # Получаем ключи из секретов окружения (так работает GitHub Actions)
    MEDIASTACK_KEY = os.environ.get('MEDIASTACK_API_KEY')
    GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHANNEL = os.environ.get('TELEGRAM_CHANNEL_ID')

    if not all([MEDIASTACK_KEY, GEMINI_KEY, TELEGRAM_TOKEN, TELEGRAM_CHANNEL]):
        print("Ошибка: Один или несколько API-ключей не найдены в переменных окружения.")
    else:
        raw_articles = get_news(MEDIASTACK_KEY)
        if raw_articles:
            summarized = summarize_with_gemini(raw_articles, GEMINI_KEY)
            if summarized:
                send_to_telegram(summarized, TELEGRAM_TOKEN, TELEGRAM_CHANNEL)
    
    print("\nРабота бота завершена.")