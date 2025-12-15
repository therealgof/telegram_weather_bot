import requests
import json
from datetime import datetime
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL = os.environ.get("CHANNEL")
ADMIN_ID = 263523529

STATUS_FILE = "status.json"
URL = "https://www.gismeteo.ru/weather-volgograd-5089/"

def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"selector_error_sent": False, "selectors": {}}

def save_status(status):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f)

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    requests.post(url, data=payload)

def fetch_weather_json():
    r = requests.get(URL)
    if r.status_code != 200:
        return None, "Ошибка доступа к сайту"
    
    html = r.text
    try:
        match = r'<script>.*?window\.M\.state\s*=\s*(\{.*?\})\s*</script>'
        import re
        m = re.search(match, html, re.DOTALL)
        if not m:
            return None, "JSON с погодой не найден"
        data = json.loads(m.group(1))
        return data, None
    except Exception as e:
        return None, f"Ошибка парсинга JSON: {e}"

def extract_weather_auto(data):
    # Берём объект cw
    cw = data.get("weather", {}).get("cw", {})
    if not cw:
        return None, "Нет данных cw"
    
    # Авто-подбор доступных ключей
    keys_map = {
        "temperature": ["temperatureAir"],
        "feels_like": ["temperatureFeelsLike"],
        "description": ["description"],
        "wind_speed": ["windSpeed"],
        "wind_dir": ["windDirection"],
        "precipitation": ["precipitation"],
        "date": ["date"]
    }
    
    weather = {}
    for k, possible_keys in keys_map.items():
        for key in possible_keys:
            if key in cw:
                weather[k] = cw[key][0]  # берём первый элемент массива
                break
        else:
            return None, f"Ключ {k} не найден в cw"
    
    return weather, None

def is_weather_time():
    now = datetime.now()
    return now.hour in [6, 19]

status = load_status()
data, error = fetch_weather_json()

if error:
    if not status.get("selector_error_sent"):
        send_telegram_message(ADMIN_ID, f"⚠️ Проблема с селекторами/структурой сайта:\n{error}")
        status["selector_error_sent"] = True
        save_status(status)
else:
    weather, weather_error = extract_weather_auto(data)
    if weather_error:
        if not status.get("selector_error_sent"):
            send_telegram_message(ADMIN_ID, f"⚠️ Селекторы изменились, не могу извлечь данные: {weather_error}")
            status["selector_error_sent"] = True
        save_status(status)
    else:
        if status.get("selector_error_sent"):
            send_telegram_message(ADMIN_ID, "✅ Селекторы восстановлены, данные доступны для прогноза.")
            status["selector_error_sent"] = False
            save_status(status)
        
        if is_weather_time():
            message = (
                f"Погода в Волгограде на {weather['date']}\n"
                f"{weather['description']}\n"
                f"Температура: {weather['temperature']}°C (ощущается как {weather['feels_like']}°C)\n"
                f"Ветер: {weather['wind_speed']} км/ч, {weather['wind_dir']}\n"
                f"Осадки: {weather['precipitation']} мм"
            )
            send_telegram_message(CHANNEL, message)
