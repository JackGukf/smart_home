# Dashboard during internet outages

Implemented 2026-09-22. Losing WAN internet must not block local dashboard
updates or local Home Assistant automation. The router/LAN, Orange Pi, HA and
Zigbee coordinator must still operate for features that depend on them.

## Dashboard behavior

- Each main data source renders as soon as its own request completes.
- Requests have a 12-second browser deadline, with one main refresh in flight.
- A failed source keeps its last rendered readings for the current page session;
  initial missing values remain unavailable. The header says that some data is
  unavailable and previous readings are kept. Successful later polls recover.
- HA sensor snapshots do not wait for a cold direct-Tuya/cloud poll. Direct
  supplements are refreshed in the background and added on subsequent polls.
- Missing temperature/humidity values are not coerced to zero.
- Live HA sensor-card updates settle independently: an unreachable sensor
  keeps its previous card while successful sensor updates in the same batch
  render. Live sensor events do not overwrite the local connection indicator.
- Status remains available when HA states or history fail or return an invalid
  response. A history failure preserves service and battery information and
  labels activity history unavailable.
- Status / Services includes Internet, Govee cloud, and Weather cloud cards.
  HTTPS probes run concurrently with a two-second cap each, cached with the
  status overview for two minutes. A reachable provider is not proof that its
  authenticated API/device data is healthy. No internet status gates local work.

## Automation

Installed HA rules were inspected: local sensor/time triggers and light/switch
service actions contain no explicit HTTP/cloud action. No rule was disabled or
changed. Closing the dashboard or losing WAN internet does not stop HA rules.
Cloud-only devices still need internet. This is not HA/coordinator redundancy.

## Validation

Simulated a hanging cloud request and verified local rendering before it
completed, preservation of previous cloud values, and automatic recovery.
Connectivity tests distinguish failed connections from reachable HTTP error
responses. No live router/internet outage was induced.

Further regression checks cover mixed successful/failed live sensor cards and malformed HA status responses.
