import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import sys

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL")

URL = "https://www.gismeteo.ru/weather-volgograd-5089/hourly/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TODAY_HOURS = ["06:00", "09:00", "12:00", "15:00", "18:00", "21:00"]
TOMORROW_HOURS = ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00"]

DAYS = {
    0: "понедельник",
    1: "вторник",
    2: "среда",
    3: "четверг",
    4: "пятница",
    5: "суббота",
    6: "воскресенье",
}

def fail(reason):
    print(f"[ERROR] {reason}")
    sys.exit(0)  # важно: не ошибка для GitHub Actions

def get_weather():
    try:
        r = requests.get(URL, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            fail(f"HTTP {r.status_code}")
    except Exception as e:
        fail(f"Request failed: {e}")

    soup = BeautifulSoup(r.text, "html.parser")
    rows = soup.select(".weather-table__row")

    if not rows:
        fail("No weather rows found")

    data = {}

    for row in rows:
        try:
            time = row.select_one(".weather-table__time").text.strip()
            temp = row.select_one(".unit_temperature_c").text.strip()
            desc = row.select_one(".weather-table__description").text.strip().lower()
            rain_el = row.select_one(".weather-table__precipitation")

            if rain_el:
                rain_raw = rain_el.text.strip()
                if rain_raw in ("0", "—", "-"):
                    rain = "без осадков"
                else:
                    rain = f"{rain_raw} мм осадков"
            else:
                rain = "без осадков"

            data[time] = {
                "temp": temp,
                "rain": rain,
                "clouds": desc
            }
        except Exception:
            continue

    if len(data) < 8:
        fail("Too few parsed hours")

    return data

def build_message(date_obj, hours, is_today):
    date_str = date_obj.strftime("%d.%m")
    weekday = DAYS[date_obj.weekday()]

    header = (
        f"Привет!\nПогода на сегодня {date_str}, {weekday}"
        if is_today
        else f"Погода на завтра {date_str}, {weekday}"
    )

    lines = [header]
    added = 0

    for h in hours:
        w = WEATHER.get(h)
        if not w:
            continue
        lines.append(f"{h} - {w['temp']}, {w['rain']}, {w['clouds']}")
        added += 1

    if added < len(hours) // 2:
        fail("Not enough hourly data")

    ending = "Хорошего дня!" if is_today else "Хорошего вечера!"
    lines.append(ending)

    text = "\n".join(lines)

    if len(text) < 100:
        fail("Message too short")

    return text

def send(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHANNEL, "text": text},
            timeout=10
        )
    except Exception as e:
        fail(f"Telegram send failed: {e}")

# ---------- main ----------
now = datetime.utcnow() + timedelta(hours=3)  # МСК
WEATHER = get_weather()

if now.hour < 12:
    msg = build_message(now, TODAY_HOURS, True)
else:
    msg = build_message(now + timedelta(days=1), TOMORROW_HOURS, False)

send(msg)
