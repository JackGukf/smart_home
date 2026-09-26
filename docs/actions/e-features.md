# E. Features

## E1 Per-person presence and users
☐ · both · M

**Why.** Only one phone is tracked and the dashboard has one login, so the house
cannot say who is home, and the audit log says "admin".

**Do.** Each family member's phone in Home Assistant (Companion app, location
*Always*); house modes use "everyone away"; personal dashboard logins so the
audit log names people.

**Owner.** The phones.

## E2 Guest / cleaner mode
☐ · Claude · S

A time window (or a temporary PIN) during which the intruder rule and the
camera leaving signals stand down and the door alerts go quiet — so the cleaner
does not set off the siren.

## E3 Clips on the dashboard
☐ · Claude · M

The night watch keeps clips in `~/night-clips/`, visible only on the board. A
Clips page: by night, camera and trigger, the annotated photo and the video; plus
optional pre-roll (a short rolling buffer so a clip starts a few seconds *before*
the trigger).

## E4 Energy that acts
☐ · Claude · M

Standby load drifting up (baseline +30% in a week), the digest pointing out the
expensive hours, and appliance-done notices from a smart plug's power signature.

## E5 Air quality actions
☐ · Claude · S

CO2 over 1000 ppm -> a notice (or ventilation); humidity out of range -> the
humidifier, within the owner's rules.

## E6 Locks
☐ · Owner · —

A Matter or Zigbee lock would complete the modes: Away locks, arrival unlocks
only with presence, "door left unlocked" alongside "door left open".
