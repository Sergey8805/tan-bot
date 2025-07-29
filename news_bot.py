# news_bot.py (Версия 3.1 - Unlocked, без лимита на количество новостей)

import os
import requests
import google.generativeai as genai
import feedparser
import time
import random
import json
from html import unescape

# --- 0. Управление базой данных обработанных новостей ---
PROCESSED_DB_FILE = 'processed_articles.json'

def load_processed_urls():
    """Загружает множество URL уже обработанных статей из файла."""
    print("Этап 0: Загрузка базы данных обработанных новостей...")
    if not os.path.exists(PROCESSED_DB_FILE):
        print("  -> Файл базы данных не найден, будет создан новый.")
        return set()
    try:
        with open(PROCESSED_DB_FILE, 'r', encoding='utf-8') as f:
            urls = set(json.load(f))
            print(f"  -> Загружено {len(urls)} URL.")
            return urls
    except (json.JSONDecodeError, IOError) as e:
        print(f"  !! Ошибка загрузки базы данных: {e}. Создается новая база.")
        return set()

def save_processed_urls(processed_urls):
    """Сохраняет обновленное множество URL в файл."""
    print("\nЗавершающий этап: Сохранение обновленной базы данных...")
    try:
        with open(PROCESSED_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(processed_urls), f, indent=2)
        print(f"  -> Успешно сохранено {len(processed_urls)} URL.")
    except IOError as e:
        print(f"  !! Критическая ошибка сохранения базы данных: {e}")


# --- 1. Функция для сбора новостей из списка RSS-каналов ---
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
                        'id': len(articles),
                        'title': entry.title,
                        'description': description,
                        'url': entry.link,
                        'source': feed.feed.title
                    })
                    seen_titles.add(entry.title)
        except Exception as e:
            print(f"    !! Ошибка при обработке канала {url}: {e}")

    print(f"Собрано новых уникальных новостей для анализа: {len(articles)}")
    return articles

# --- 2. Главная функция: Интеллектуальный анализ, кластеризация и фильтрация ---
def analyze_and_filter_articles(articles, api_key):
    print("\nЭтап 2: Интеллектуальный анализ и фильтрация с помощью Gemini...")
    if not articles:
        return []

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    print("Модель Gemini 'gemini-2.5-flash' успешно настроена для анализа.")

    input_data_for_prompt = []
    for article in articles:
        input_data_for_prompt.append(f"ID: {article['id']}\nЗАГОЛОВОК: \"{article['title']}\"\nОПИСАНИЕ: \"{article['description'][:500]}...\"")
    
    articles_text = "\n---\n".join(input_data_for_prompt)

    prompt = f"""
    Ты — главный редактор ведущего технологического издания. Твоя задача — проанализировать список свежих новостей и подготовить из них качественную сводку, отбросив все лишнее.

    Вот твои критерии отбора и приоритезации:

    1.  **Группировка (Кластеризация):** Сначала найди новости из разных источников, которые описывают ОДНО И ТО ЖЕ событие (например, анонс нового продукта, выход отчета, крупное обновление). Сгруппируй их.
    2.  **Тематический фильтр:**
        - **ОСТАВИТЬ:** Новости, строго касающиеся **искусственного интеллекта (AI)** или **индустрии телекоммуникаций**.
        - **УДАЛИТЬ:** Все, что не относится к этим двум темам.
    3.  **Фильтр по содержанию (Исключения):**
        - **УДАЛИТЬ:** Обзоры потребительских устройств (смартфонов, ноутбуков), если это не связано с прорывной AI-технологией.
        - **УДАЛИТЬ:** "Whitepapers", сложную техническую документацию, научные статьи для узких специалистов.
        - **УДАЛИТЬ:** Новости, основанные на слухах, предположениях, гипотезах или мнениях без фактов.
    4.  **Приоритезация (что важнее):**
        - **ВЫСОКИЙ ПРИОРИТЕТ:** Новости с конкретными **исследовательскими или статистическими данными**.
        - **ВЫСОКИЙ ПРИОРИТЕТ:** Новости с упоминанием **ключевых брендов** (NVIDIA, Google, OpenAI, Ericsson, Huawei, etc.) или **влиятельных личностей** (CEO, ведущие исследователи).
        - **ВЫСОКИЙ ПРИОРИТЕТ:** Анонсы и обзоры **важных обновлений технологических продуктов** (новые версии моделей ИИ, запуск новых сетей 5G/6G и т.д.).
        - **НИЗКИЙ ПРИОРИТЕТ:** Общие рассуждения о рынке без конкретики.

    Твоя задача: Вернуть ответ в формате JSON-массива. Каждый элемент массива — это объект, представляющий ОДНУ новость или ОДНУ группу новостей.

    Структура объекта в JSON:
    - `group_ids`: массив ID статей из входного списка, которые ты объединил в эту группу. Если новость одиночная, в массиве будет один ID.
    - `decision`: твое решение, "KEEP" (оставить) или "DISCARD" (отклонить).
    - `priority`: числовая оценка важности от 1 до 10 (10 — самая важная).
    - `reason`: краткое (1-2 слова) пояснение твоего решения (например, "Слухи", "Не по теме", "Важный анонс", "Статистика рынка").
    - `representative_title`: самый лучший и репрезентативный заголовок для этой группы новостей.

    Проанализируй этот список новостей:
    ---
    {articles_text}
    ---

    Верни ТОЛЬКО JSON-массив. Без лишних слов и форматирования.
    """

    try:
        print(f"  -> Отправляю {len(articles)} новостей на пакетный анализ...")
        response = model.generate_content(prompt)
        
        cleaned_response_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        analysis_result = json.loads(cleaned_response_text)
        print("  -> Анализ успешно завершен. Получены результаты.")
        
        approved_groups = [group for group in analysis_result if group['decision'] == 'KEEP']
        approved_groups.sort(key=lambda x: x['priority'], reverse=True)

        # --- ИЗМЕНЕНИЕ ---
        # Жесткое ограничение на количество новостей снято.
        # Теперь в обработку пойдут все группы, которые модель пометила как 'KEEP'.
        final_groups = approved_groups
        # -----------------
        
        print(f"  -> После фильтрации и приоритезации отобрано {len(final_groups)} новостей/групп для публикации.")
        return final_groups

    except Exception as e:
        print(f"  !! Ошибка на этапе анализа Gemini API: {e}")
        print(f"  !! Ответ от API, который вызвал ошибку: {response.text if 'response' in locals() else 'No response'}")
        return []


# --- 3. Функция для финальной суммаризации и подготовки сообщений ---
def summarize_and_prepare_messages(groups, all_articles, api_key):
    print("\nЭтап 3: Финальная суммаризация отобранных новостей...")
    if not groups:
        return [], set()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    print("Модель Gemini 'gemini-2.5-flash' настроена для суммаризации.")

    prepared_messages = []
    processed_urls_in_batch = set()

    for group in groups:
        group_articles = [all_articles[id] for id in group['group_ids']]
        
        for article in group_articles:
            processed_urls_in_batch.add(article['url'])

        content_for_summary = ""
        for i, article in enumerate(group_articles):
            content_for_summary += f"Источник {i+1} ({article['source']}):\nЗаголовок: {article['title']}\nОписание: {article['description']}\n\n"

        prompt = f"""
        Сделай краткую, но емкую выжимку (саммари) на РУССКОМ языке в 2-3 предложениях для следующей новостной подборки.
        Если новость одна, сделай выжимку для нее. Если их несколько, синтезируй общую суть, так как они все об одном и том же событии.
        Передай только главную суть, без вводных фраз.

        Вот контент для анализа:
        ---
        {content_for_summary}
        ---

        Твой ответ — это только текст саммари на русском языке.
        """
        try:
            print(f"  -> Суммаризирую группу: '{group['representative_title'][:60]}...'")
            response = model.generate_content(prompt)
            summary = response.text.strip()

            if summary:
                prepared_messages.append({
                    'title': group['representative_title'],
                    'summary_ru': summary,
                    'articles': group_articles
                })
        except Exception as e:
            print(f"  !! Ошибка Gemini API при суммаризации: {e}")
        
        time.sleep(5)

    print(f"Суммаризация завершена. Подготовлено сообщений: {len(prepared_messages)}")
    return prepared_messages, processed_urls_in_batch


# --- 4. Функция для отправки сообщений в Telegram ---
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
            source_name = str(article['source']).replace(char, f'\\{char}')
            sources_text = f"Источник: {source_name}\n[Читать оригинал]({article['url']})"
        else:
            sources_list = []
            for i, article in enumerate(msg_data['articles']):
                source_name = str(article['source']).replace(char, f'\\{char}')
                sources_list.append(f"{i+1}\\. [{source_name}]({article['url']})")
            sources_text = "*Источники:*\n" + "\n".join(sources_list)

        message_text = (
            f"*{title}*\n\n"
            f"{summary}\n\n"
            f"{sources_text}"
        )

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


# --- Основной блок для запуска ---
if __name__ == "__main__":
    print("Запуск AI-новостного бота (v3.1 - Unlocked)...")

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
