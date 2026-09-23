# Home card loading

The Home Temperatures card builds four 24-hour trends from Home Assistant's
recorder. The history endpoint caches each sensor grouping for five minutes.
The browser also saves the last successful grouping and series, so a page
refresh can draw the previous wave immediately while checking for new data.
During startup, areas, thermostats, and sensor entities arrive independently.
If the grouping changes while an older history request is running, the new
request proceeds and only its result may update the current card.

Home camera stills come from the local snapshot endpoint. A capture from
go2rtc can take several seconds; measured examples on 2026-09-23 ranged from
about 1.3 to 4.5 seconds per camera. Previously the background saver visited
cameras serially and the Home markup added a new timestamp to each snapshot
URL on redraw, causing repeated captures. Preview URLs are now stable, the
browser keeps the last still, and the server shares a captured frame for 30
seconds across simultaneous viewers. The saver visits outdoor cameras first
with at most two concurrent captures. These changes affect still previews,
not the WebRTC live stream started by the camera card.
