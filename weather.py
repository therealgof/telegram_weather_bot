import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- Конфигурация ---
STATUS_FILE = "status.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL")  # канал для прогноза
ADMIN_CHAT_ID = 263523529      # твой личный chat_id для уведомлений
URL = "https://www.gismeteo.ru/weather-volgograd-5089/hourly/"  # актуальный URL

# --- Загрузка состояния ---
if os.path.exists(STATUS_FILE):
    with open(STATUS_FILE, "r") as f:
        status = json.load(f)
else:
    status = {"selectors_broken": False}

# --- Отправка сообщений ---
def send_telegram(text, chat_id=CHANNEL):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=10
        )
    except Exception as e:
        print(f"Telegram send error: {e}")

# --- Проверка селекторов ---
def check_weather_selectors():
    try:
        r = requests.get(URL, timeout=15)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select(".widget__row")  # актуальный CSS-селектор
        if not rows:
            raise Exception("No weather rows found")
        return rows
    except Exception as e:
        raise Exception(f"Selector check failed: {e}")

# --- Формирование прогноза ---
def build_message(hour):
    now = datetime.utcnow() + timedelta(hours=3)
    if hour == 6:
        forecast_date = now
        greeting = "Привет!"
        end_text = "Хорошего дня!"
    else:
        forecast_date = now + timedelta(days=1)
        greeting = ""
        end_text = "Хорошего вечера!"

    date_str = forecast_date.strftime("%d.%m")
    weekday_str = forecast_date.strftime("%A").lower()

    rows = check_weather_selectors()
    hours_to_show = ["06:00","09:00","12:00","15:00","18:00","21:00"] if hour==6 else ["00:00","03:00","06:00","09:00","12:00","15:00","18:00","21:00"]

    lines = []
    for r in rows:
        time_el = r.select_one(".widget__time")
        temp_el = r.select_one(".unit_temperature_c")
        desc_el = r.select_one(".weather-table__description")
        rain_el = r.select_one(".weather-table__precipitation")
        if not all([time_el,temp_el,desc_el,rain_el]):
            continue
        time_txt = time_el.get_text(strip=True)
        if time_txt not in hours_to_show:
            continue
        temp_txt = temp_el.get_text(strip=True)
        desc_txt = desc_el.get_text(strip=True)
        rain_txt = rain_el.get_text(strip=True)
        if rain_txt == "0":
            rain_txt = "без осадков"
        else:
            rain_txt = f"{rain_txt} мм осадков"
        lines.append(f"{time_txt} - {temp_txt}, {rain_txt}, {desc_txt}")

    if not lines:
        raise Exception("Not enough hourly data")

    message = f"{greeting}\nПогода на {'сегодня' if hour==6 else 'завтра'} {date_str}, {weekday_str}\n"
    message += "\n".join(lines)
    message += f"\n{end_text}"
    return message

# --- Основная логика ---
now = datetime.utcnow() + timedelta(hours=3)
hour = now.hour
send_hours = [6, 19]  # плановые часы отправки прогноза

try:
    check_weather_selectors()
    if status["selectors_broken"]:
        # селекторы восстановились → уведомление администратору
        send_telegram("Селекторы восстановились! Прогноз будет отправлен по расписанию.", chat_id=ADMIN_CHAT_ID)
        status["selectors_broken"] = False

    # отправка прогноза только в нужные часы
    if hour in send_hours:
        message = build_message(hour)
        send_telegram(message)  # в CHANNEL

except Exception as e:
    if not status["selectors_broken"]:
        send_telegram(f"Внимание! Селекторы сломаны: {e}", chat_id=ADMIN_CHAT_ID)
        status["selectors_broken"] = True

# --- Сохраняем статус ---
with open(STATUS_FILE, "w") as f:
    json.dump(status, f)
