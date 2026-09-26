---
document_id: test-riverside-report
title: Test Riverside Flood Report 2021
kind: report
source: Test Emergency Operations Centre
version: "1.0"
effective_date: 2021-08-10
hazards: [flood]
zone_ids: [Z-RS]
summary: Test report on a flash flood in Riverside after drainage channel D-7 reached 95 percent of capacity.
incident:
  id: HI-TEST-FL-01
  hazard: flood
  title: Test Riverside flood
  started_on: 2021-07-15
  ended_on: 2021-07-16
  primary_zone_id: Z-RS
  zone_ids: [Z-RS]
  slope_id: null
  location_description: Riverside Bypass low point
  x_m: 9000
  y_m: 3500
  rainfall_24h_mm: 110
  rainfall_72h_mm: 140
  peak_intensity_mm_h: 40
  wind_speed_kmh: null
  wind_gust_kmh: null
  river_stage_m: 4.4
  antecedent_conditions: Two wet days before the event.
  infrastructure_state: D-7 at 95 percent of capacity.
  severity: 2
  severity_label: moderate
  affected_population: 500
  evacuated: 0
  deaths: 0
  injured: 0
  houses_damaged: 10
  houses_destroyed: 0
  damage_estimate_million: 2
  response_summary: Two pump units were deployed four hours after the first overflow.
  outcome_summary: Water drained within a day.
  lessons: Pre-position pump units when the flood index reaches the watch band.
impacts:
  - {asset_kind: road, asset_id: RD-TEST, impact: closed, detail: "Water on the bypass", duration_hours: 6}
---

## 1 Summary

On 15 July 2021 a flash flood inundated Riverside after 110 mm of rain fell in six hours and drainage channel
D-7 reached 95 percent of its capacity. Water rose to 0.6 m on Riverside Bypass and two pump units were
deployed four hours after the first overflow.

## 2 Lessons

Pump units must be pre-positioned at the depot when the flood index reaches the watch band. The evacuation
route along Riverside Bypass must be kept open by closing it to general traffic early.
