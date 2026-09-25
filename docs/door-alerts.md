# Front door left open

Installed 2026-09-25 by `scripts/install-door-alerts.py` (Home Assistant config
API, idempotent; `--apply` to write). Every rule and its reason is in that
script's docstring.

## When it fires (the owner chose A + B)

| | Trigger | Needs the phone? |
| --- | --- | --- |
| **A** | The last phone leaves the home zone (`zone.home` 0 for 1 min) with the door open - or the door opens and stays open 2 min within 7 min of everyone leaving | Yes: location *Always* (`docs/house-modes.md`) |
| **B** | Door open 10 min **and** no indoor sensor has seen anyone for 10 min | No |

Both run `script.front_door_left_open` (mode single: A and B together send one
message). It turns `input_boolean.front_door_alert` on, sends, and reminds every
15 min while the door stays open - three reminders at most.

## Where it goes

- **Dashboard:** a banner on every view and an amber one on Security, from
  `input_boolean.front_door_alert` via `/api/alarm` (`alerts`). It is Home
  Assistant's state, so every screen shows the same, and **I know** on any of
  them (`POST /api/alerts/front_door/ack`) clears it everywhere and stops the
  reminders. The banner has no Close - closing would be the same as I know.
- **iPhone:** `notify.mobile_app_iphone_15`, time-sensitive (through Focus),
  tag `front-door-open` so the closed message replaces the alert. Buttons:
  **Show camera** (the doorbell, `camera.zhi_neng_men_ling`; needs the phone to
  reach home - Tailscale) and **I know**. Delivered by Home Assistant's push
  relay, so it arrives away from home without Tailscale.
- **Telegram:** to every `notify.*` entity of the `telegram_bot` integration,
  found when the installer runs. Set up 2026-09-25: bot **Hornby_House**
  (@Hornby_house_bot), broadcast (send-only), one allowed chat - Jack Gu,
  `notify.hornby_house_jack_gu`. Test message sent 00:36.
- When the door closes after an alert: "Front door closed at 14:32" on the
  iPhone and Telegram, and the banner goes.

## Setting up Telegram (or adding a family member)

Adding someone later: they open @Hornby_house_bot and press Start; their chat id
comes from the bot's `getUpdates` (broadcast mode leaves updates unread, so it
is there); add it as an *allowed chat id* on the integration (Settings →
Devices & services → Telegram bot → Add allowed chat id), then run
`install-door-alerts.py --apply` again.

1. In Telegram, open **@BotFather**, send `/newbot`, give it a name (e.g.
   *House*) and a username ending in `bot`. It replies with a **token**.
2. Open your new bot and press **Start** (send it anything). Everyone who
   should get alerts does this too - or add the bot to a family group and
   send a message there.
3. Put the token on the board, never in git:
   `ssh orangepi@192.168.0.83`, then add `TELEGRAM_BOT_TOKEN=<token>` to
   `~/smart_home_AI/.env`.
4. Then the integration is added through Home Assistant's config flow
   (platform *broadcast* - sends only, needs no incoming connection), the chat
   ids from the bot's `getUpdates` become its allowed chats, and
   `install-door-alerts.py --apply` is run again to pick the new notify
   entities up.
