# NYC weather alert

Sends an email every morning at 7am ET telling me whether to grab an
umbrella, a cap, or neither, based on that day's NYC forecast.

## How it works
- `weather_alert.py` calls [Open-Meteo](https://open-meteo.com/) (free, no API key) for NYC's forecast
- Classifies the day (clear / rainy / snowy / etc.) and precipitation chance
- Emails a short recommendation via Gmail SMTP
- Runs on a GitHub Actions cron schedule, no server needed