# news_bot.py (Версия 3.3 - Skeptical, с семантической памятью)

import os
import requests
import google.generativeai as genai
import feedparser
import time
import random
import json
from html import unescape
from datetime import datetime, timedelta

# --- 0. Управление базами данных ---
PROCESSED_URLS_DB = 'processed_urls.json'
RECENT_TOPICS_DB = 'recent_topics.json'
MEMORY_DAYS = 3 # Сколько дней хранить темы в памяти

# --- URL База ---
def load_processed_urls():
    print("Этап 0.1: Загрузка базы данных обработанных URL...")
    if not os.path.exists(PROCESSED_URLS_DB): return set()
    try:
        with open(PROCESSED_URLS_DB, 'r', encoding='utf-8') as f: return set(json.load(f))
    except (json.JSONDecodeError, IOError): return set()

def save_processed_urls(urls):
    print("\nЗавершающий этап 0.1: Сохранение обновленной базы URL...")
    try:
        with open(PROCESSED_URLS_DB, 'w', encoding='utf-8') as f: json.dump(list(urls), f, indent=2)
        print(f"  -> Успешно сохранено {len(urls)} URL.")
    except IOError as e: print(f"  !! Критическая ошибка сохранения базы URL: {e}")

# --- Новая семантическая память о темах ---
def load_recent_topics():
    """Загружает недавно опубликованные темы и отсеивает старые."""
    print(f"Этап 0.2: Загрузка семантической памяти (за последние {MEMORY_DAYS} дня)...")
    if not os.path.exists(RECENT_TOPICS_DB): return []
    try:
        with open(RECENT_TOPICS_DB, 'r', encoding='utf-8') as f:
            all_topics = json.load(f)
        
        relevant_topics = []
        cutoff_date = datetime.now() - timedelta(days=MEMORY_DAYS)
        
        for topic in all_topics:
            topic_date = datetime.fromisoformat(topic['date'])
            if topic_date > cutoff_date:
                relevant_topics.append(topic)
        
        print(f"  -> Загружено {len(relevant_topics)} актуальных тем для проверки на повторы.")
        return relevant_topics
    except (json.JSONDecodeError, IOError, KeyError):
        return []

def save_recent_topics(existing_topics, new_topics):
    """Добавляет новые темы в память и сохраняет."""
    print("\nЗавершающий этап 0.2: Обновление семантической памяти...")
    now_iso = datetime.now().isoformat()
    for new_topic in new_topics:
        new_topic['date'] = now_iso
    
    updated_topics = existing_topics + new_topics
    
    # Еще раз отсеиваем старые на всякий случай
    cutoff_date = datetime.now() - timedelta(days=MEMORY_DAYS)
    final_topics = [t for t in updated_topics if datetime.fromisoformat(t['date']) > cutoff_date]

    try:
        with open(RECENT_TOPICS_DB, 'w', encoding='utf-8') as f:
            json.dump(final_topics, f, indent=2, ensure_ascii=False)
        print(f"  -> Семантическая память обновлена. Всего тем: {len(final_topics)}.")
    except IOError as e:
        print(f"  !! Критическая ошибка сохранения семантической памяти: {e}")

# --- 1. Сбор новостей (без изменений) ---
def get_news_from_rss(rss_urls, processed_urls):
    print("\nЭтап 1: Получение новостей из RSS-каналов...")
    # ... (код без изменений) ...
    articles = []
    seen_titles = set()
    for url in rss_urls:
        try:
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

# --- 2. Анализ "Скептического Редактора" с проверкой на повторы ---
def analyze_and_filter_articles(articles, api_key, recent_topics):
    print("\nЭтап 2: Анализ в режиме 'Скептического Редактора'...")
    if not articles: return []

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')

    input_data_for_prompt = []
    for article in articles:
        input_data_for_prompt.append(f"ID: {article['id']}\nЗАГОЛОВОК: \"{article['title']}\"\nОПИСАНИЕ: \"{article['description'][:500]}...\"")
    articles_text = "\n---\n".join(input_data_for_prompt)

    recent_topics_text = "\n".join([f"- {t['russian_title']}" for t in recent_topics]) if recent_topics else "Нет."

    # --- ИЗМЕНЕНИЕ: Самый важный промпт! ---
    prompt = f"""
    Ты — чрезвычайно требовательный и скептически настроенный главный редактор элитного техно-издания. Твоя задача — безжалостно отфильтровать поток новостей, оставив только 100% релевантный, важный и свежий материал. Ошибки недопустимы.

    ШАГ 1: ПРОВЕРКА НА ПОВТОРЫ.
    Вот темы, которые мы УЖЕ ОПУБЛИКОВАЛИ за последние дни:
    <УЖЕ ОПУБЛИКОВАНО>
    {recent_topics_text}
    </УЖЕ ОПУБЛИКОВАНО>

    Твоя первая и главная задача — ОТКЛОНИТЬ (decision: "DISCARD") любую новость, которая является простым пересказом или незначительным обновлением этих тем. Новость проходит, только если содержит КРИТИЧЕСКИ ВАЖНУЮ, ПРИНЦИПИАЛЬНО НОВУЮ информацию (например, вчера был анонс, а сегодня вышли официальные цены и тесты).

    ШАГ 2: АГРЕССИВНАЯ ФИЛЬТРАЦИЯ.
    После проверки на повторы, примени эти правила с максимальной строгостью:
    - **ТЕМАТИКА:** Только **Искусственный Интеллект** и **Телекоммуникации**. Никаких общих IT-новостей, гаджетов, игр, криптовалют.
    - **ЧТО ВЫБРАСЫВАТЬ НЕМЕДЛЕННО (Примеры):**
        - Обзоры смартфонов, ноутбуков, часов. Даже если там есть "AI-камера".
        - Пресс-релизы о назначениях в компаниях.
        - Общие прогнозы роста рынка ("Рынок X вырастет на Y% к Z году").
        - "Whitepapers", глубоко технические документы, научные статьи для академиков.
        - Новости, основанные на слухах, утечках, мнениях аналитиков без фактов.
        - Спонсорский контент, маркетинговые статьи.
        - Списки "Топ 10 чего-угодно".

    ШАГ 3: ГРУППИРОВКА И ПРИОРИТЕЗАЦИЯ.
    - **Группировка:** Новости, прошедшие фильтры, можно сгруппировать, если они описывают ОДНО И ТО ЖЕ КОНКРЕТНОЕ событие. Будь консервативен: если не уверен, не группируй.
    - **Приоритет:** Присвой приоритет от 1 до 10. 10 — это глобальный прорыв (выход GPT-5). 1 — рядовая новость. Отдавай предпочтение новостям с цифрами, данными исследований, анонсами от ключевых игроков (OpenAI, Google, NVIDIA, Ericsson).

    ТВОЯ ЗАДАЧА: Вернуть JSON-массив с решением по КАЖДОЙ группе/новости.
    Структура: `{{ "group_ids": [..], "decision": "KEEP" | "DISCARD", "priority": X, "reason": "Краткое и честное обоснование" }}`.
    Причина должна быть конкретной: "Повтор темы", "Не по теме: гаджеты", "Слухи", "Достойный анонс" и т.д.

    АНАЛИЗИРУЙ ЭТОТ СПИСОК:
    ---
    {articles_text}
    ---

    Верни ТОЛЬКО JSON-массив. Без комментариев.
    """
    try:
        print(f"  -> Отправляю {len(articles)} новостей на строгий анализ...")
        response = model.generate_content(prompt)
        cleaned_response_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        analysis_result = json.loads(cleaned_response_text)
        print("  -> Анализ 'Скептического Редактора' завершен.")
        
        approved_groups = [g for g in analysis_result if g.get('decision') == 'KEEP']
        approved_groups.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        print(f"  -> После безжалостной фильтрации для публикации отобрано: {len(approved_groups)} новостей/групп.")
        return approved_groups

    except Exception as e:
        print(f"  !! Ошибка на этапе анализа Gemini API: {e}")
        return []


# --- 3. Суммаризация и подготовка (с извлечением тем для памяти) ---
def summarize_and_prepare_messages(groups, all_articles, api_key):
    print("\nЭтап 3: Финальная суммаризация и подготовка сообщений...")
    if not groups: return [], set(), []

    # ... (код модели и конфигурации без изменений) ...
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')

    prepared_messages = []
    processed_urls_in_batch = set()
    new_topics_for_memory = [] # <-- Новое

    for group in groups:
        # ... (код сборки контента для саммари без изменений) ...
        group_articles = [all_articles[id] for id in group['group_ids']]
        if not group_articles: continue
        for article in group_articles: processed_urls_in_batch.add(article['url'])
        content_for_summary = ""
        for i, article in enumerate(group_articles):
            content_for_summary += f"Источник {i+1} ({article['source']}):\nЗаголовок: {article['title']}\nОписание: {article['description']}\n\n"

        # --- Промпт для саммари (без изменений, он хорош) ---
        prompt = f"""
        Проанализируй следующую подборку новостей.
        1. Придумай хороший, емкий **заголовок на русском языке**.
        2. Напиши краткую **выжимку (саммари) на русском языке** в 2-3 предложениях.
        Верни ответ в формате JSON-объекта СТРОГО следующей структуры:
        {{
          "russian_title": "Твой заголовок на русском языке",
          "russian_summary": "Твоя выжимка на русском языке."
        }}
        Вот контент:
        ---
        {content_for_summary}
        ---
        Верни ТОЛЬКО JSON-объект.
        """
        try:
            print(f"  -> Суммаризирую группу: '{group_articles[0]['title'][:60]}...'")
            response = model.generate_content(prompt)
            cleaned_response_text = response.text.strip().replace('```json', '').replace('```', '').strip()
            result_json = json.loads(cleaned_response_text)
            
            title_ru = result_json.get("russian_title")
            summary_ru = result_json.get("russian_summary")

            if title_ru and summary_ru:
                prepared_messages.append({
                    'title': title_ru, 'summary_ru': summary_ru, 'articles': group_articles
                })
                # --- Новое: Добавляем тему в память для следующего запуска ---
                new_topics_for_memory.append({'russian_title': title_ru, 'russian_summary': summary_ru})
            
        except Exception as e:
            print(f"  !! Ошибка при суммаризации или парсинге JSON: {e}")
        time.sleep(5)

    print(f"Суммаризация завершена. Подготовлено сообщений: {len(prepared_messages)}")
    return prepared_messages, processed_urls_in_batch, new_topics_for_memory


# --- 4. Отправка в Telegram (без изменений) ---
def send_to_telegram(messages, bot_token, channel_id):
    # ... (код без изменений) ...
    print("\nЭтап 4: Отправка новостей в Telegram...")
    total_sent = 0
    for msg_data in messages:
        # ... (экранирование и форматирование) ...
        chars_to_escape = "_*[]()~`>#+-=|{}.!"
        title = msg_data['title']; summary = msg_data['summary_ru']
        for char in chars_to_escape:
            title = title.replace(char, f'\\{char}'); summary = summary.replace(char, f'\\{char}')
        sources_text = ""
        if len(msg_data['articles']) == 1:
            article = msg_data['articles'][0]
            source_name_escaped = str(article['source'])
            for char in chars_to_escape: source_name_escaped = source_name_escaped.replace(char, f'\\{char}')
            sources_text = f"Источник: {source_name_escaped}\n[Читать оригинал]({article['url']})"
        else:
            sources_list = []
            for i, article in enumerate(msg_data['articles']):
                source_name_escaped = str(article['source'])
                for char in chars_to_escape: source_name_escaped = source_name_escaped.replace(char, f'\\{char}')
                sources_list.append(f"{i+1}\\. [{source_name_escaped}]({article['url']})")
            sources_text = "*Источники:*\n" + "\n".join(sources_list)
        message_text = f"*{title}*\n\n{summary}\n\n{sources_text}"
        
        # ... (отправка) ...
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


# --- Основной блок с новой логикой ---
if __name__ == "__main__":
    print("Запуск AI-новостного бота (v3.3 - Skeptical)...")

    # Конфигурация (без изменений)
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
        print("\nКритическая ошибка: Один или несколько API-ключей не найдены.")
    else:
        # --- Новый рабочий процесс ---
        processed_urls = load_processed_urls()
        recent_topics = load_recent_topics()
        
        raw_articles = get_news_from_rss(RSS_FEEDS, processed_urls)
        
        if raw_articles:
            filtered_groups = analyze_and_filter_articles(raw_articles, GEMINI_KEY, recent_topics)
            
            if filtered_groups:
                final_messages, urls_to_save, new_topics = summarize_and_prepare_messages(filtered_groups, raw_articles, GEMINI_KEY)
                
                if final_messages:
                    send_to_telegram(final_messages, TELEGRAM_TOKEN, TELEGRAM_CHANNEL)
                    
                    # Сохраняем обе базы данных
                    processed_urls.update(urls_to_save)
                    save_processed_urls(processed_urls)
                    save_recent_topics(recent_topics, new_topics)
                else:
                    print("\nНе удалось подготовить ни одного сообщения для отправки.")
            else:
                print("\nПосле строгой фильтрации не осталось новостей для публикации.")
        else:
            print("\nНовых новостей для обработки не найдено.")
    
    print("\nРабота бота завершена.")
