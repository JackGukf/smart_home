# Python Automation

Use this folder for quick automations, device discovery, and scripts that are easier to iterate in Python.

Suggested setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Keep real credentials in environment variables or an untracked local file.
## TP-Link/Kasa Light Switch Control

The TP-Link switch controller uses `python-kasa` and runs asynchronously.

Control a switch directly by IP address:

```bash
python3 -m src.python.tplink_switch --host 192.168.1.10 status
python3 -m src.python.tplink_switch --host 192.168.1.10 on
python3 -m src.python.tplink_switch --host 192.168.1.10 off
python3 -m src.python.tplink_switch --host 192.168.1.10 toggle
```

Control a named switch from local config:

```bash
cp configs/devices.example.yaml configs/devices.local.yaml
python3 -m src.python.tplink_switch --config configs/devices.local.yaml --name living_room_switch status
```

For newer Kasa/Tapo devices that require credentials, set environment variables instead of storing secrets in config:

```bash
export TPLINK_USERNAME="your-email@example.com"
export TPLINK_PASSWORD="your-password"
```

The command prints JSON with the switch name, host, alias, model, and on/off state.

## Web Dashboard

The FastAPI dashboard serves a local web UI for TP-Link light switches:

```bash
python3 -m uvicorn src.python.web_app:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` on the Pi, or `http://<pi-ip>:8000` from another device on the LAN.

### Ecobee thermostat

Add an `ecobee` section to `configs/devices.local.yaml`:

```yaml
ecobee:
  temperature_unit: celsius
  thermostats:
    - name: Main thermostat
      thermostat_id: replace_me
      room: Hallway
```

Set Ecobee API credentials in the dashboard environment. Keep these out of Git:

```bash
export ECOBEE_CLIENT_ID="your-ecobee-app-api-key"
export ECOBEE_REFRESH_TOKEN="your-refresh-token"
```

The dashboard reads thermostat status from Ecobee Cloud and shows temperature, humidity, HVAC mode, equipment status, and heat/cool setpoints.
