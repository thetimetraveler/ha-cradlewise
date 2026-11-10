"""Constants for the Cradlewise integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "cradlewise"

API_BASE_URL = "https://integrations.cradlewise.com/api/v1"

CONF_TOKEN = "token"
CONF_STATUS_INTERVAL = "status_interval"
CONF_SLEEP_INTERVAL = "sleep_interval"

# Rate limits (per token): status 2/min, sleep 60/hour, 2880/day overall.
# Polling status every 30s would use the whole daily budget, so default to 60s.
MIN_STATUS_INTERVAL = 30  # seconds
DEFAULT_STATUS_INTERVAL = 60
MAX_STATUS_INTERVAL = 600

MIN_SLEEP_INTERVAL = 5  # minutes
DEFAULT_SLEEP_INTERVAL = 30
MAX_SLEEP_INTERVAL = 240

# The day-metrics endpoint accepts a 1-8 day window.
DAY_METRICS_WINDOW = timedelta(days=2)
WEEKLY_WINDOW = timedelta(days=7)

BABY_STATUSES = ["sleeping", "awake", "stirring", "crying", "away"]
