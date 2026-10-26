# Turret Envelope Run — 2026-10-26

Raw capture of the session that put the ±180° turret cable envelope into
both motor writers and checked it on the robot. Plan:
[turret envelope](../plans/2026-10-26-turret-envelope.md). Procedure:
[turret centering runbook](../runbooks/turret-centering.md).

## Starting state

- User confirmed: the turret at **C=42298** faces camera-forward and the
  cables are fine there. Rule given: never more than 180° either way.
- No state file on the robot; the oracle read C=42298 (A=-6343, D=10047).

## Locked checks

| Case | Writer | Command | Result |
|---|---|---|---|
| No state file | motord | `burst 0.5 16` | `turret blocked: locked`, dC=0 |
| Saved `last` 1000 ticks off the real C | v1 server | `TurretRight(-120)` streamed 1 s | `turret LOCKED: encoder C=41640 but last saved 42640 …`, dC=0 |
| Same | motord | `burst 0.5 16` | `turret blocked: locked`, dC=0 |

## Limit checks (temporary half-range, limits at center ±200)

Margin 300 (first build) and 800 (final build); same limit positions because
the temporary half-range was raised from 500 to 1000 with the margin.

| Writer | Speed | Move | Limit | Stopped at | Past the limit |
|---|---|---|---|---|---|
| motord | 16 % | rel −700 | 42098 | 42086 | 12 |
| motord | 16 % | rel +700 | 42498 | 42510 | 12 |
| v1 server | pwm 80 | `TurretRight(80)` 2.5 s | 42098 | 41955 | 143 (detected at 42045) |
| v1 server | pwm 250 | `TurretRight(-250)` 1.5 s | 42498 | 42811 | 313 (detected at 42510) |
| motord (margin 800) | 16 % | rel −900 from 42811 (outside high limit, inward allowed) | 42098 | 42082 | 16 |
| motord (margin 800) | 16 % | rel +500 | 42498 | 42513 | 15 |
| v1 server (margin 800) | pwm 250 | `TurretRight(250)` 1.5 s | 42098 | 41640 | 458 (detected at 41948) |

The v1 server's 10 Hz loop plus coast at full GUI speed (pwm 250) overshoots
by up to ~460 ticks; motord's 60 Hz loop by ~15 at 16 %. The final margin of
800 ticks keeps the worst case near 20700 ticks from center (177° at
116.7 ticks/°).

## Restore and re-check

- State restored to `{"center": 42298, "half_range": 21000, "last": <C>}`.
- Turret returned by motord: 41640 → 42592 → **42308** (final approach
  encoder-negative, from the left, as in the centering run).
- Kinect at C=42308, sonar 59–61: obstacle columns 138–531, x=334.5,
  **bearing +1.42°** (two readings, identical), surface yaw −0.40° / −0.92°.
  At the original centering (C=42298) the readings were columns 126–516,
  bearing +0.10°, yaw +0.25°. The bearing and the yaw moved in opposite
  directions, which a turret rotation alone does not produce; the obstacle or
  the scene likely shifted slightly. The reference was not changed (the user
  had confirmed the facing).
