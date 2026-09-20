# Energy monitoring: BC Hydro PowerLync and FortisBC gas

Researched and built 2026-09-19. Electricity is ready to go live the day the
PowerLync arrives; gas cannot be read from the house today, and this says why
and what the options are. The last section is the plan for an energy "AI mode"
once live readings exist.

## Electricity: the PowerLync

### What the device is

BC Hydro's **PowerLync Plug/Hub** (made by Powerley, ~$75, sometimes free) pairs
with the smart meter over **Zigbee Smart Energy** - BC Hydro joins it to your
meter - and reports to Powerley's cloud over mutual TLS, which cannot be read.
It *also* advertises itself on the LAN as an **Apple HomeKit accessory**
(`_hap._tcp`, HAP over HTTP on port 80). Besides a plain HomeKit outlet it
carries a custom Powerley service with the meter's readings:

| iid | What | Format |
| --- | --- | --- |
| 21 | Grid instantaneous demand | `"000000.859 kW"` |
| 22 | Grid register, delivered | `"064732.4 kWh"` |
| 23 | Grid register, received (solar) | `"000000.1 kWh"` |
| 24, 25 | The PowerLync's **own outlet** - not the house | W, kWh |
| 27 | Meter time | Unix time |

Home Assistant's HomeKit Controller ignores unknown services, so the community
integration [Bolshem/powerlync-hub-homeassistant](https://github.com/Bolshem/powerlync-hub-homeassistant)
polls them every 10 s over the existing pairing and makes sensors. The meter
itself updates about every 30 s. Local, no cloud, no account.

The **Energy Bridge** ($179) is a different device with local MQTT on port 2883;
none of this applies to it.

### When it arrives

1. Set it up the way BC Hydro says (their app), so it is joined to *this*
   meter and on the house Wi-Fi. **Do not add it to Apple Home** - a HomeKit
   accessory accepts one controller and Home Assistant must be it. If the
   BC Hydro app itself claims the HomeKit pairing, factory-reset the
   PowerLync after BC Hydro's setup and pair again.
2. Find the 8-digit HomeKit setup code on its label. If it only has a QR code,
   scan it: it reads `X-HM://...`, and the integration's README shows how to
   decode the code from that.
3. On the board:

   ```bash
   ~/smart_home_AI/.venv/bin/python scripts/setup-ha-powerlync.py --code 12345678 --apply
   ```

   It installs the integration from a pinned commit into
   `~/homeassistant-config/custom_components/powerlync_energy`, restarts Home
   Assistant, pairs the PowerLync, adds the energy entry and waits for a
   reading. Without `--apply` it is a dry run.
4. Nothing else. `/api/energy` looks for the sensors once a minute and switches
   the Home card and the Energy view to live by itself; the "Sample data" pill
   goes away. Optionally add `…_grid_total_energy_consumed` to Home Assistant's
   own Energy dashboard (Settings -> Energy -> Electricity grid).

### How the dashboard reads it (`src/python/energy.py`)

- **Now** and **the last hour**: the demand sensor's state and its history
  (`/api/history`), one value per minute. Cached 10 s for every screen.
- **Hours and days**: Home Assistant's long-term **statistics** of the kWh
  register (WebSocket `recorder/statistics_during_period`, `change` per hour
  and per day). Statistics survive the recorder's 10-day purge, so the 30-day
  bars fill up as the days pass. Cached 5 min.
- **A usual day** is the per-hour median of the last 14 whole days; it appears
  after three days of readings.
- Before the sensors exist the payload is the old sample data. Once they have
  been seen, a Home Assistant failure is a 502 and the page keeps its last
  reading - it never falls back to invented figures while claiming to be live.
- `electricity.sample` and `gas.sample` say which half is real.

Traps:

- The **Plug** sensors are the PowerLync's own outlet. `find_powerlync_entities`
  skips anything with `plug` or `local` in it.
- The integration's manifest pins `aiohomekit==3.2.20`, the version Home
  Assistant 2026.6.3 ships. Before upgrading Home Assistant or moving
  `PINNED_COMMIT`, check they still match; a mismatch makes HA try to install
  another aiohomekit at startup.
- The integration reaches into HomeKit Controller's internal data. A Home
  Assistant upgrade can break it; if the sensors go unavailable after an
  upgrade, look there first.

## Natural gas: the FortisBC meter

The meter in the photo is a **Sensus Sonix IQ 425** (ultrasonic, made 07/2026)
with a **FlexNet** radio, part of FortisBC's advanced meter rollout.

### It cannot be read over the air

FlexNet is Sensus's licensed-band (~900 MHz) network: encrypted, two-way,
between the meter and FortisBC's base stations only. There is no home-area
radio in it (no Zigbee, unlike the BC Hydro meter), and the usual trick for
utility meters - an RTL-SDR with `rtlamr` - decodes Itron ERT and Neptune,
not FlexNet. Nothing on the board can hear it.

### Three ways that could work

1. **Pulse output (best, needs FortisBC).** The cover is printed
   *PULSE INTERFACE: Form A switch, 1 pulse = 1 ft³, Vmax 26 Vdc*. A Form A
   pulse is a dry contact - an ESP32 running ESPHome's `pulse_meter` reads it
   directly, which would give real-time gas at 1 ft³ (about 0.001 GJ)
   resolution. But the meter is FortisBC's property and a gas appliance:
   **do not open or connect anything to it.** Ask FortisBC whether this meter's
   pulse output is enabled and whether they will connect a customer pulse
   cable for residential service. If they say yes, this is a small ESPHome job.
2. **Account Online, daily.** FortisBC says gas customers get daily usage in
   Account Online ("My energy use") as the advanced meters come in. I found
   **no public API and no Green Button download** for FortisBC gas. Logging in
   by script would be brittle (a web login that can change or add MFA at any
   time) and is not something to run from the board. **What to check:** log in,
   open My energy use, and see whether it offers a download (CSV/Excel) of
   daily use. If it does, send me one file and I will build an importer that
   fills the gas column from it - daily, and a day or two behind, which is all
   the Energy view claims for gas anyway.
3. **Read the display with a camera.** An ESP32 camera running
   *AI-on-the-edge-device* can read the LCD's cumulative ft³ without touching
   the meter. Outdoors, the display may cycle or sleep, and it needs power at
   the meter; workable, but the least reliable of the three.

Until one of these exists, the gas column stays sample data and says so.

## Forecasting: baseline, LightGBM and Chronos-2 (deployed 2026-09-19)

`src/python/energy_forecast.py` holds three models behind one interface, and a
walk-forward backtest on **this house's own series** decides which one the
nightly job uses. The baseline keeps the job unless something beats it by 3%:
a model that is only a hair better is not worth the moving parts.

| Model | What it is | Trains on the board in |
| --- | --- | --- |
| **seasonal median** | this hour of this weekday, historically. No dependencies | 0 s |
| **LightGBM** | gradient boosting on lags (1-4, 24, 25, 48, 168 h), rolling means and calendar; recursive over 24 hours | ~1.2 s |
| **Chronos-2** | Amazon's 120M-parameter pretrained model, zero-shot - no training at all | first call 5.9 s (loads weights), then 0.3 s |

**Measured on the board**, 30 days of hourly readings from the ecobee
(720 points, a real house series - there is no electricity history until the
PowerLync is paired):

| Model | MAE (degC) | RMSE | sMAPE | skill vs baseline |
| --- | --- | --- | --- | --- |
| chronos-2 | **0.218** | 0.281 | 1.0% | **+73%** |
| lightgbm | 0.547 | 0.581 | 2.1% | +31% |
| seasonal median | 0.794 | 0.989 | 3.9% | - |

A thermostat is a smooth series, which flatters a big model. On a **spiky**
series - 30 days from the sample electricity generator, which is shape plus
noise plus appliance bursts - the same backtest gives chronos-2 +14% and
lightgbm +4.5% over the baseline. Electricity will sit nearer that end, so
**do not assume Chronos-2 wins on the real meter**: the nightly job re-scores
every night and will say.

Cost on the board: peak ~1.3 GB with Chronos-2 (~160 MB without), a few
seconds a night, 5.6 GB of venv and 456 MB of model weights on disk.

### How it runs

- **`energy-forecast.timer`** at 03:45 Vancouver (after house-learning, before
  the digest) runs `energy-forecast.service` from **`~/forecast-venv`** - torch
  and LightGBM stay out of the dashboard's environment, which only reads the
  JSON. Set the venv up with `scripts/install-forecast-venv.sh`
  (`--no-chronos` for the light install).
- Until the PowerLync is paired the job finds no electricity statistic and
  exits saying so - that is the normal state today, and it is not an error.
- It writes `energy_forecast.json`; `/api/energy` carries it while it is less
  than 36 hours old, and the Energy view shows "Next 24 hours" with the total,
  the cost, **the name of the model that produced it** and how accurate that
  model was in the backtest.
- Try it by hand on any statistic:

      PYTHONPATH=. ~/forecast-venv/bin/python -m src.python.energy_forecast \
          --evaluate --statistic-id sensor.my_ecobee_current_temperature --kind mean

### Which sensors it can run on

Only what Home Assistant keeps **long-term statistics** for, which on this
board is 57 sensors with 4+ days of history. `--kind mean` for a reading
(degrees, ppm, lux, a count), `--kind change` for a meter (kWh in that hour).
`--days` is how much history to pull; it uses what exists.

Measured 2026-09-19, five folds each, and the point is that **the winner
depends on the series**:

| Series | Hours | Best | Skill over baseline | Would use |
| --- | --- | --- | --- | --- |
| `sensor.my_ecobee_current_temperature` | 719 | chronos-2 | +73% | chronos-2 |
| `sensor.my_ecobee_current_humidity` | 719 | seasonal median | chronos -2%, lgbm -10% | seasonal median |
| `sensor.0xa4c138d00106c90d_illuminance` (kitchen/family room) | 385 | seasonal median | chronos -5%, lgbm -17% | seasonal median |
| `sensor.office_camera_npu_person_count` | 277 | lightgbm | +2.3% (under the 3% margin) | seasonal median |

Smooth and strongly autocorrelated (a thermostat) is where the big model earns
its keep. Spiky or near-random at the hour scale (sunlight through a window,
whether somebody is in the office) is where **nothing beats the house's own
routine**, and the job says so rather than dressing it up. Electricity will sit
between the two, nearer the spiky end.

Two traps this turned up, both fixed:

- **Statistics skip hours** - a restart, a battery change, a sensor that said
  nothing. Chronos-2 refuses a series whose frequency it cannot infer and
  LightGBM's 168-hour lag walks off the end, so `regularize()` puts every
  series on a continuous hourly grid first: gaps up to 6 h interpolated, and
  anything before a longer gap dropped rather than bridged with invention.
- **LightGBM trains from the first day, not the first week.** A lag that
  reaches past the start of history is NaN, which LightGBM handles natively;
  waiting for lag 168 to be real would refuse to train during the first week -
  exactly the week after the PowerLync arrives.

Nothing here drives a device. The house rule stands: Python computes, rules
execute, and no model sits in a trigger path.

## Next: an energy "AI mode"

Planned for when live electricity has run for a week or two (the usual day
needs history). The house's rule for AI still applies: **Python computes,
rules execute, the model only writes prose or drafts rules for a person to
approve.** Nothing here puts a model in a trigger path.

What live readings make possible, roughly in order of value:

Forecasting is now in place (above). What is left:

1. **What is on right now.** Every step in demand (say ±150 W within 30 s) is
   matched against the Home Assistant events at the same moment, which
   `house-memory.service` already keeps. Steps explained by a device the house
   controls (lights, the TP-Link plugs, the TV, the IKEA drivers) teach the
   house each device's draw; steps nothing explains are the big unmanaged
   loads (dryer, oven, heaters). The Energy view could then say "about 1.8 kW:
   the dryer (probably) and 140 W of lights".
2. **Always-on load.** The overnight floor, tracked nightly. A floor that rises
   by 100 W and stays is something left on; that is worth a line in the
   morning digest.
3. **Unusual use.** Hourly kWh added to the nightly `house-learning` routine
   model (hour of week), logged silently like its other unusual moments.
4. **Which BC Hydro rate is cheaper.** With real hourly use, compare the
   standard two-step rate against BC Hydro's optional time-of-day rate over the
   same hours. A deterministic calculation - check the current tariff figures
   before trusting it - that says in dollars whether switching is worth it,
   and how close each billing period is to the Step 2 threshold.
5. **Shifting load.** Suggestions ("the dryer ran at 17:40 three days this
   week"), and for loads Home Assistant switches, draft automations for the
   Automations view that the owner installs or not. The model can phrase the
   suggestion; the schedule is a rule.

Items 1, 2 and 4 need no model at all. The NPU and Qwen add little to this; the
value is in the house's own event log, which is already being kept.
