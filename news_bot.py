# news_bot.py (Версия 3.2 - Fixed, с надежной связкой заголовка и саммари)

import os
import requests
import google.generativeai as genai
import feedparser
import time
import random
import json
from html import unescape

# --- 0. Управление базой данных обработанных новостей (без изменений) ---
PROCESSED_DB_FILE = 'processed_articles.json'

def load_processed_urls():
    print("Этап 0: Загрузка базы данных обработанных новостей...")
    if not os.path.exists(PROCESSED_DB_FILE):
        return set()
    try:
        with open(PROCESSED_DB_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    except (json.JSONDecodeError, IOError):
        return set()

def save_processed_urls(processed_urls):
    print("\nЗавершающий этап: Сохранение обновленной базы данных...")
    try:
        with open(PROCESSED_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(processed_urls), f, indent=2)
        print(f"  -> Успешно сохранено {len(processed_urls)} URL.")
    except IOError as e:
        print(f"  !! Критическая ошибка сохранения базы данных: {e}")

# --- 1. Функция для сбора новостей (без изменений) ---
def get_news_from_rss(rss_urls, processed_urls):
    print("\nЭтап 1: Получение новостей из RSS-каналов...")
    articles = []
    seen_titles = set()
    for url in rss_urls:
        try:
            print(f"  -> Загружаю канал: {url}")
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if entry.link not in processed_urls and entry.title not in seen_titles:
                    description = unescape(entry.summary) if 'summary' in entry else ''
                    articles.append({
                        'id': len(articles), 'title': entry.title,
                        'description': description, 'url': entry.link,
                        'source': feed.feed.title
                    })
                    seen_titles.add(entry.title)
        except Exception as e:
            print(f"    !! Ошибка при обработке канала {url}: {e}")
    print(f"Собрано новых уникальных новостей для анализа: {len(articles)}")
    return articles

# --- 2. Интеллектуальный анализ и фильтрация ---
def analyze_and_filter_articles(articles, api_key):
    print("\nЭтап 2: Интеллектуальный анализ и фильтрация с помощью Gemini...")
    if not articles: return []

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    print("Модель Gemini 'gemini-2.5-flash' успешно настроена для анализа.")

    input_data_for_prompt = []
    for article in articles:
        input_data_for_prompt.append(f"ID: {article['id']}\nЗАГОЛОВОК: \"{article['title']}\"\nОПИСАНИЕ: \"{article['description'][:500]}...\"")
    
    articles_text = "\n---\n".join(input_data_for_prompt)
    
    # --- ИЗМЕНЕНИЕ: Усиленный промпт ---
    prompt = f"""
    Ты — главный редактор технологического издания. Проанализируй список новостей.

    Твои задачи:
    1.  **Группировка:** Найди новости, описывающие СТРОГО ОДНО И ТО ЖЕ событие. Критически важно не объединять разные темы. Если не уверен, оставь новость одиночной.
    2.  **Фильтрация:** Примени строгие правила для каждой новости или группы.
        - **Темы:** Только **искусственный интеллект (AI)** или **телекоммуникации**.
        - **Исключить:** Обзоры телефонов (если это не прорыв в AI), whitepapers, слухи, мнения без фактов.
    3.  **Приоритезация:** Оцени важность.
        - **ВЫСОКИЙ ПРИОРИТЕТ:** Исследования, статистика, анонсы ключевых брендов (NVIDIA, Google, OpenAI), важные обновления продуктов.
        - **НИЗКИЙ ПРИОРИТЕТ:** Общие рассуждения.

    Верни ответ в формате JSON-массива. Структура объекта:
    - `group_ids`: массив ID статей. Для одиночной новости — один ID.
    - `decision`: "KEEP" или "DISCARD".
    - `priority`: оценка важности от 1 до 10.
    - `reason`: краткое пояснение решения (например, "Не по теме", "Важный анонс").

    Проанализируй этот список:
    ---
    {articles_text}
    ---

    Верни ТОЛЬКО JSON-массив.
    """
    try:
        print(f"  -> Отправляю {len(articles)} новостей на пакетный анализ...")
        response = model.generate_content(prompt)
        cleaned_response_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        analysis_result = json.loads(cleaned_response_text)
        print("  -> Анализ успешно завершен.")
        
        approved_groups = [group for group in analysis_result if group.get('decision') == 'KEEP']
        approved_groups.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        print(f"  -> После фильтрации отобрано {len(approved_groups)} новостей/групп для публикации.")
        return approved_groups

    except Exception as e:
        print(f"  !! Ошибка на этапе анализа Gemini API: {e}")
        return []

# --- 3. Финальная суммаризация и подготовка сообщений ---
def summarize_and_prepare_messages(groups, all_articles, api_key):
    print("\nЭтап 3: Финальная суммаризация и подготовка сообщений...")
    if not groups: return [], set()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    print("Модель Gemini 'gemini-2.5' настроена для суммаризации.")

    prepared_messages = []
    processed_urls_in_batch = set()

    for group in groups:
        group_articles = [all_articles[id] for id in group['group_ids']]
        if not group_articles: continue

        for article in group_articles:
            processed_urls_in_batch.add(article['url'])

        content_for_summary = ""
        for i, article in enumerate(group_articles):
            content_for_summary += f"Источник {i+1} ({article['source']}):\nЗаголовок: {article['title']}\nОписание: {article['description']}\n\n"

        # --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Запрос JSON с заголовком и саммари ---
        prompt = f"""
        Проанализируй следующую подборку новостей. Они об одном событии.
        Твоя задача — подготовить финальный пост для Telegram-канала.

        1.  Придумай хороший, емкий **заголовок на русском языке**.
        2.  Напиши краткую **выжимку (саммари) на русском языке** в 2-3 предложениях, передавая главную суть.

        Верни ответ в формате JSON-объекта СТРОГО следующей структуры:
        {{
          "russian_title": "Твой заголовок на русском языке",
          "russian_summary": "Твоя выжимка на русском языке."
        }}

        Вот контент для анализа:
        ---
        {content_for_summary}
        ---

        Верни ТОЛЬКО JSON-объект.
        """
        try:
            representative_title = group_articles[0]['title'] # Для логгирования
            print(f"  -> Суммаризирую группу: '{representative_title[:60]}...'")
            response = model.generate_content(prompt)
            
            # Парсим JSON из ответа
            cleaned_response_text = response.text.strip().replace('```json', '').replace('```', '').strip()
            result_json = json.loads(cleaned_response_text)

            title_ru = result_json.get("russian_title")
            summary_ru = result_json.get("russian_summary")

            if title_ru and summary_ru:
                prepared_messages.append({
                    'title': title_ru,
                    'summary_ru': summary_ru,
                    'articles': group_articles
                })
            else:
                print(f"  !! Модель вернула некорректный JSON (отсутствует title или summary).")

        except json.JSONDecodeError:
            print(f"  !! Ошибка декодирования JSON ответа от Gemini. Ответ: {response.text}")
        except Exception as e:
            print(f"  !! Ошибка Gemini API при суммаризации: {e}")
        
        time.sleep(5)

    print(f"Суммаризация завершена. Подготовлено сообщений: {len(prepared_messages)}")
    return prepared_messages, processed_urls_in_batch

# --- 4. Отправка в Telegram (без изменений) ---
def send_to_telegram(messages, bot_token, channel_id):
    print("\nЭтап 4: Отправка новостей в Telegram...")
    total_sent = 0
    for msg_data in messages:
        chars_to_escape = "_*[]()~`>#+-=|{}.!"
        title = msg_data['title']
        summary = msg_data['summary_ru']
        
        for char in chars_to_escape:
            title = title.replace(char, f'\\{char}')
            summary = summary.replace(char, f'\\{char}')

        sources_text = ""
        if len(msg_data['articles']) == 1:
            article = msg_data['articles'][0]
            source_name_escaped = str(article['source'])
            for char in chars_to_escape:
                source_name_escaped = source_name_escaped.replace(char, f'\\{char}')
            sources_text = f"Источник: {source_name_escaped}\n[Читать оригинал]({article['url']})"
        else:
            sources_list = []
            for i, article in enumerate(msg_data['articles']):
                source_name_escaped = str(article['source'])
                for char in chars_to_escape:
                    source_name_escaped = source_name_escaped.replace(char, f'\\{char}')
                sources_list.append(f"{i+1}\\. [{source_name_escaped}]({article['url']})")
            sources_text = "*Источники:*\n" + "\n".join(sources_list)

        message_text = f"*{title}*\n\n{summary}\n\n{sources_text}"
        api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        params = {'chat_id': channel_id, 'text': message_text, 'parse_mode': 'MarkdownV2', 'disable_web_page_preview': True}
        
        response = requests.post(api_url, data=params)
        if response.status_code == 200:
            print(f"  -> Сообщение '{msg_data['title'][:30]}...' успешно отправлено.")
            total_sent += 1
        else:
            print(f"  -> Ошибка отправки: {response.status_code}, {response.text}")
        
        time.sleep(3)

    print(f"Отправка завершена. Всего отправлено: {total_sent}")

# --- Основной блок для запуска (без изменений) ---
if __name__ == "__main__":
    print("Запуск AI-новостного бота (v3.2 - Fixed)...")

    RSS_FEEDS = [
        "https://feeds.reuters.com/reuters/technologyNews", "https://feeds.bloomberg.com/technology/news.rss",
        "https://www.theverge.com/rss/index.xml", "http://feeds.arstechnica.com/arstechnica/index/",
        "https://techcrunch.com/category/artificial-intelligence/feed/", "https://www.wired.com/feed/category/artificial-intelligence/latest/rss",
        "https://feeds.feedburner.com/Venturebeat/AI", "https://www.lightreading.com/rss_feed.asp",
        "https://www.fiercetelecom.com/rss.xml", "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
        "https://www.kdnuggets.com/feed", "https://www.analyticsinsight.net/feed/",
        "https://www.rcrwireless.com/feed", "http://feeds.feedburner.com/TeleGeographyBlog",
        "http://feeds.google.com/googleaiblog/", "https://openai.com/blog.rss",
        "https://blogs.nvidia.com/blog/category/artificial-intelligence/feed/", "https://a16z.com/feed/",
    ]
    
    GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHANNEL = os.environ.get('TELEGRAM_CHANNEL_ID')

    if not all([GEMINI_KEY, TELEGRAM_TOKEN, TELEGRAM_CHANNEL]):
        print("\nКритическая ошибка: Один или несколько API-ключей не найдены в переменных окружения.")
    else:
        processed_urls = load_processed_urls()
        raw_articles = get_news_from_rss(RSS_FEEDS, processed_urls)
        
        if raw_articles:
            random.shuffle(raw_articles)
            filtered_groups = analyze_and_filter_articles(raw_articles, GEMINI_KEY)
            
            if filtered_groups:
                final_messages, urls_to_save = summarize_and_prepare_messages(filtered_groups, raw_articles, GEMINI_KEY)
                
                if final_messages:
                    send_to_telegram(final_messages, TELEGRAM_TOKEN, TELEGRAM_CHANNEL)
                    processed_urls.update(urls_to_save)
                    save_processed_urls(processed_urls)
                else:
                    print("\nНе удалось подготовить ни одного сообщения для отправки.")
            else:
                print("\nПосле интеллектуального анализа не осталось новостей для публикации.")
        else:
            print("\nНовых новостей для обработки не найдено.")
    
    print("\nРабота бота завершена.")
