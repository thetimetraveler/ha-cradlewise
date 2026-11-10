# Cradlewise for Home Assistant

A custom [Home Assistant](https://www.home-assistant.io/) integration for the
[Cradlewise](https://www.cradlewise.com/) smart crib, built on the official
[Cradlewise Data API](https://integrations.cradlewise.com/documentation)
(beta, read-only).

> **Unofficial.** This project is not affiliated with or endorsed by Cradlewise.
> The Data API is in beta and may change.

## Requirements

- An active **Nurture Plus** subscription.
- You must be the baby's **admin** (caregivers cannot create tokens).
- Home Assistant 2025.8 or newer.

## Getting a token

1. Sign in to the Cradlewise **web dashboard** (not the mobile app).
2. Open **Cradlewise Data API** in the left menu and press **Generate**.
3. Copy the token (it starts with `cw_`).

A token is bound to **one baby** and is valid for **60 days**. Generating a new
token invalidates the old one. When it expires, Home Assistant will show a
repair/reauthentication prompt where you paste a new token.

## Installation

### HACS (custom repository)

1. HACS → ⋮ → **Custom repositories** → add this repository, category **Integration**.
2. Install **Cradlewise** and restart Home Assistant.

### Manual

Copy `custom_components/cradlewise` into your Home Assistant `config/custom_components/` directory and restart.

## Setup

**Settings → Devices & services → Add integration → Cradlewise**, then paste your token.
Add the integration once per baby (one token each).

## Entities

| Entity | Source | Notes |
| --- | --- | --- |
| Status | `/baby/status` | `sleeping`, `awake`, `stirring`, `crying`, `away` |
| Status since | `/baby/status` | Diagnostic timestamp |
| In crib / Bounce / Music | `/baby/status` | Binary sensors |
| Soothes today, Naps today | `/sleep/day-metrics` | Naps sensor has per-nap details as an attribute |
| Longest stretch, Time in bed, Awake in bed | `/sleep/day-metrics` | Durations for the current day |
| Rise time, Bedtime | `/sleep/day-metrics` | Timestamps |
| Average sleep / day sleep / night sleep / nap duration / naps per day | `/sleep/weekly-sleep-metrics` | Rolling 7 days |

"Day" is not midnight-to-midnight: each baby has a configurable day start
(default 8:00 am local), and the daily metrics follow it.

## Polling and rate limits

The API has no webhooks, so the integration polls. Limits are per token:
2 status requests/min, 60 sleep requests/hour, and **2,880 requests/day in total**.
Polling status every 30 s would consume the entire daily budget, so the defaults are:

- Status: every **60 s** (min 30 s)
- Sleep metrics: every **30 min** (2 requests per refresh, min 5 min)

Change them via the integration's **Configure** button. On HTTP 429 the integration
logs the failure and retries on its next scheduled poll.

## Example automation

```yaml
automation:
  - alias: Chime off while baby sleeps
    triggers:
      - trigger: state
        entity_id: sensor.cradlewise_crib_status
        to: sleeping
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.doorbell_chime
```

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

## Privacy

Your token is stored in Home Assistant's config entry storage and is only sent to
`integrations.cradlewise.com`.

## License

MIT
