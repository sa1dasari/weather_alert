import os
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import requests

NYC_LAT = 40.7128
NYC_LON = -74.0060

# Open-Meteo WMO weather codes -> human categories
# https://open-meteo.com/en/docs
def classify_weather_code(code: int) -> str:
    if code == 0:
        return "clear"
    if code in (1, 2):
        return "mostly_sunny"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "foggy"
    if code in (51, 53, 55, 56, 57):
        return "drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "rainy"
    if code in (71, 73, 75, 77, 85, 86):
        return "snowy"
    if code in (95, 96, 99):
        return "stormy"
    return "unknown"


def fetch_forecast() -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": NYC_LAT,
        "longitude": NYC_LON,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,windspeed_10m_max",
        "temperature_unit": "fahrenheit",
        "windspeed_unit": "mph",
        "timezone": "America/New_York",
        "forecast_days": 1,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    daily = data["daily"]
    return {
        "weathercode": daily["weathercode"][0],
        "temp_max": daily["temperature_2m_max"][0],
        "temp_min": daily["temperature_2m_min"][0],
        "precip_prob": daily["precipitation_probability_max"][0],
        "uv_index_max": daily["uv_index_max"][0],
        "windspeed_max": daily["windspeed_10m_max"][0],
    }


def uv_advice(uv_index: float) -> str | None:
    """Returns a sunscreen note, or None if UV is low enough to skip it."""
    if uv_index >= 8:
        return f"UV index {round(uv_index)} (very high) \u2014 sunscreen is a must, reapply if you're out midday."
    if uv_index >= 6:
        return f"UV index {round(uv_index)} (high) \u2014 worth putting on sunscreen."
    if uv_index >= 3:
        return f"UV index {round(uv_index)} (moderate) \u2014 sunscreen if you'll be out for a while."
    return None


def wind_advice(windspeed_mph: float, recommend_umbrella: bool) -> str | None:
    """Returns a wind note, or None if wind isn't notable."""
    if windspeed_mph >= 30:
        note = f"Winds up to {round(windspeed_mph)} mph \u2014 secure loose items, this is genuinely gusty."
    elif windspeed_mph >= 20:
        note = f"Winds up to {round(windspeed_mph)} mph \u2014 on the breezy side."
    else:
        return None
    if recommend_umbrella and windspeed_mph >= 20:
        note += " An umbrella may turn inside out; a hooded jacket might serve you better."
    return note


def build_message(forecast: dict) -> tuple[str, str]:
    category = classify_weather_code(forecast["weathercode"])
    precip = forecast["precip_prob"]
    temp_max = round(forecast["temp_max"])
    temp_min = round(forecast["temp_min"])
    uv_index = forecast.get("uv_index_max", 0)
    windspeed = forecast.get("windspeed_max", 0)

    recommend_umbrella = category in ("rainy", "drizzle", "stormy", "snowy") or precip >= 40
    recommend_cap = category in ("clear", "mostly_sunny") and precip < 20

    labels = {
        "clear": "clear skies",
        "mostly_sunny": "mostly sunny",
        "cloudy": "cloudy",
        "foggy": "foggy",
        "drizzle": "light drizzle",
        "rainy": "rain",
        "snowy": "snow",
        "stormy": "thunderstorms",
        "unknown": "uncertain conditions",
    }
    label = labels.get(category, "uncertain conditions")

    if recommend_umbrella:
        headline = f"Bring an umbrella today \u2614"
        advice = f"{precip}% chance of precipitation with {label} expected. Grab an umbrella on your way out."
    elif recommend_cap:
        headline = f"Grab a cap today \u2600\ufe0f"
        advice = f"{label.capitalize()} expected, only {precip}% chance of rain. A cap should do the trick."
    else:
        headline = f"No umbrella or cap needed today"
        advice = f"{label.capitalize()} expected, {precip}% chance of rain. Should be a low-fuss day."

    extra_lines = []
    uv_note = uv_advice(uv_index)
    if uv_note:
        extra_lines.append(uv_note)
    wind_note = wind_advice(windspeed, recommend_umbrella)
    if wind_note:
        extra_lines.append(wind_note)

    subject = f"NYC weather: {headline}"
    body = (
        f"{headline}\n\n"
        f"{advice}\n"
    )
    if extra_lines:
        body += "\n" + "\n".join(extra_lines) + "\n"
    body += (
        f"\nHigh: {temp_max}\u00b0F  Low: {temp_min}\u00b0F\n"
        f"Conditions: {label}\n"
        f"Chance of precipitation: {precip}%\n"
        f"UV index: {round(uv_index)}\n"
        f"Wind: {round(windspeed)} mph\n"
    )
    return subject, body


def send_email(subject: str, body: str) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_app_password)
        server.sendmail(gmail_user, [recipient], msg.as_string())


def main() -> int:
    try:
        forecast = fetch_forecast()
    except Exception as exc:
        print(f"Failed to fetch forecast: {exc}", file=sys.stderr)
        return 1

    subject, body = build_message(forecast)
    print(subject)
    print(body)

    try:
        send_email(subject, body)
    except Exception as exc:
        print(f"Failed to send email: {exc}", file=sys.stderr)
        return 1

    print("Email sent successfully.")
    return 0


if __name__ == "__main__":
    event_name = os.environ.get("GITHUB_EVENT_NAME", "manual")
    now_et = datetime.now(ZoneInfo("America/New_York"))
    print(f"Running weather alert at {now_et.isoformat()} (trigger: {event_name})")

    if event_name == "schedule" and now_et.hour != 7:
        print(f"Current ET hour is {now_et.hour}, not 7. Skipping.")
        sys.exit(0)

    sys.exit(main())