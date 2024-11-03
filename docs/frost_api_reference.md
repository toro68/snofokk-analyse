# FROST API Referanse

## Tidsoppløsninger
- PT1H  = Timesdata
- PT10M = 10-minuttersdata
- P1D   = Døgndata
- P1M   = Månedsdata

## Hovedparametere
=== OVERSIKT OVER TILGJENGELIGE TIDSOPPLØSNINGER ===

Forklaring av tidsoppløsninger:
PT1H  = Timesdata
PT10M = 10-minuttersdata
P1D   = Døgndata
P1M   = Månedsdata

=== PARAMETERE MED TIMESOPPLØSNING (PT1H) ===

# Temperatur

- air_temperature
  Enhet: degC
  Tilgjengelig fra: 2018-02-06
  Status: Authoritative

- dew_point_temperature
  Enhet: degC
  Tilgjengelig fra: 2018-02-06
  Status: Authoritative

- max(air_temperature PT1H)
  Enhet: degC
  Tilgjengelig fra: 2018-02-06
  Status: Authoritative

- min(air_temperature PT1H)
  Enhet: degC
  Tilgjengelig fra: 2018-02-06
  Status: Authoritative

# Nedbør

- accumulated(precipitation_amount)
  Enhet: mm
  Tilgjengelig fra: 2018-02-06
  Status: Authoritative

- sum(precipitation_amount PT1H)
  Enhet: mm
  Tilgjengelig fra: 2018-02-06
  Status: Authoritative

# Vind

- max(wind_speed PT1H)
  Enhet: m/s
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative

- max(wind_speed_of_gust PT1H)
  Enhet: m/s
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative

- max_wind_speed(wind_from_direction PT1H)
  Enhet: degrees
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative

- wind_speed
  Enhet: m/s
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative

# Fuktighet

- relative_humidity
  Enhet: percent
  Tilgjengelig fra: 2018-02-06
  Status: Authoritative

=== ANDRE TIDSOPPLØSNINGER ===

# Temperatur

- air_temperature
  Enhet: degC
  Tilgjengelig fra: 2018-02-06
  Status: Authoritative
  Tidsoppløsning: PT10M

- best_estimate_mean(air_temperature P1M)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- best_estimate_mean(air_temperature P1Y)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1Y

- best_estimate_mean(air_temperature P3M)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P3M

- integral_of_deficit(mean(air_temperature P1D) P1D 17.0)
  Enhet: degree-day
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative
  Tidsoppløsning: P1D

- integral_of_deficit(mean(air_temperature P1D) P1M 17.0)
  Enhet: degree-day
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- integral_of_deficit(mean(air_temperature P1D) P1Y 17.0)
  Enhet: degree-day
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1Y

- integral_of_deficit(mean(air_temperature P1D) P3M 17.0)
  Enhet: degree-day
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P3M

- integral_of_deficit(mean(air_temperature P1D) P6M 17.0)
  Enhet: degree-day
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P6M

- integral_of_excess(mean(air_temperature P1D) P1D 0.0)
  Enhet: degree-day
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative
  Tidsoppløsning: P1D

- integral_of_excess(mean(air_temperature P1D) P1D 5.0)
  Enhet: degree-day
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative
  Tidsoppløsning: P1D

- integral_of_excess(mean(air_temperature P1D) P1M 0.0)
  Enhet: degree-day
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- integral_of_excess(mean(air_temperature P1D) P1M 5.0)
  Enhet: degree-day
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- max(air_temperature P1D)
  Enhet: degC
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative
  Tidsoppløsning: P1D

- max(air_temperature P1M)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- max(air_temperature P1Y)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1Y

- max(air_temperature P3M)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P3M

- max(air_temperature P6M)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P6M

- max(air_temperature PT12H)
  Enhet: degC
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative
  Tidsoppløsning: PT12H

- mean(air_temperature P1D)
  Enhet: degC
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative
  Tidsoppløsning: P1D

- mean(air_temperature P1M)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- mean(air_temperature P1Y)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1Y

- mean(air_temperature P3M)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P3M

- mean(air_temperature P6M)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P6M

- mean(air_temperature_anomaly P1M 1991_2020)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- mean(air_temperature_anomaly P1Y 1961_1990)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1Y

- mean(air_temperature_anomaly P1Y 1991_2020)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1Y

- mean(air_temperature_anomaly P3M 1961_1990)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P3M

- mean(air_temperature_anomaly P3M 1991_2020)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P3M

- mean(air_temperature_anomaly P6M 1961_1990)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P6M

- mean(air_temperature_anomaly P6M 1991_2020)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P6M

- mean(dew_point_temperature P1D)
  Enhet: degC
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative
  Tidsoppløsning: P1D

- mean(dew_point_temperature P1M)
  Enhet: degC
  Tilgjengelig fra: 2018-02-01
  Status: Authoritative
  Tidsoppløsning: P1M

- mean(max(air_temperature P1D) P1M)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- mean(min(air_temperature P1D) P1M)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- min(air_temperature P1D)
  Enhet: degC
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative
  Tidsoppløsning: P1D

- min(air_temperature P1M)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- min(air_temperature P1Y)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1Y

- min(air_temperature P3M)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P3M

- min(air_temperature P6M)
  Enhet: degC
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P6M

- min(air_temperature PT12H)
  Enhet: degC
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative
  Tidsoppløsning: PT12H

- over_time(time_of_maximum_air_temperature P1M)
  Enhet: Date
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- over_time(time_of_minimum_air_temperature P1M)
  Enhet: Date
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

# Nedbør

- accumulated(precipitation_amount)
  Enhet: mm
  Tilgjengelig fra: 2018-02-06
  Status: Authoritative
  Tidsoppløsning: PT10M

- best_estimate_sum(precipitation_amount P1M)
  Enhet: mm
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- best_estimate_sum(precipitation_amount P1Y)
  Enhet: mm
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1Y

- best_estimate_sum(precipitation_amount P3M)
  Enhet: mm
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P3M

- best_estimate_sum(precipitation_amount P6M)
  Enhet: mm
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1Y

- max(sum(precipitation_amount P1D) P1M)
  Enhet: mm
  Tilgjengelig fra: 2018-02-01
  Status: Authoritative
  Tidsoppløsning: P1M

- number_of_days_gte(sum(precipitation_amount P1D) P1M 1.0)
  Enhet: number of
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- over_time(sum(time_of_maximum_precipitation_amount P1D) P1M)
  Enhet: Date
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- sum(precipitation_amount P1D)
  Enhet: mm
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative
  Tidsoppløsning: P1D

- sum(precipitation_amount P1M)
  Enhet: mm
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- sum(precipitation_amount P1Y)
  Enhet: mm
  Tilgjengelig fra: 2020-01-01
  Status: Authoritative
  Tidsoppløsning: P1Y

- sum(precipitation_amount P30D)
  Enhet: mm
  Tilgjengelig fra: 2024-02-01
  Status: Authoritative
  Tidsoppløsning: P1D

- sum(precipitation_amount P3M)
  Enhet: mm
  Tilgjengelig fra: 2020-01-01
  Status: Authoritative
  Tidsoppløsning: P3M

- sum(precipitation_amount P6M)
  Enhet: mm
  Tilgjengelig fra: 2020-01-01
  Status: Authoritative
  Tidsoppløsning: P6M

- sum(precipitation_amount PT10M)
  Enhet: mm
  Tilgjengelig fra: 2018-02-06
  Status: Authoritative
  Tidsoppløsning: PT10M

- sum(precipitation_amount PT12H)
  Enhet: mm
  Tilgjengelig fra: 2018-02-06
  Status: Authoritative
  Tidsoppløsning: PT12H

# Vind

- max(max(wind_speed P1D) P1M)
  Enhet: m/s
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- max(max(wind_speed PT1H) P1D)
  Enhet: m/s
  Tilgjengelig fra: 2018-02-09
  Status: Authoritative
  Tidsoppløsning: P1D

- max(wind_speed P1D)
  Enhet: m/s
  Tilgjengelig fra: 2018-02-08
  Status: Authoritative
  Tidsoppløsning: P1D

- max(wind_speed P1M)
  Enhet: m/s
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- max(wind_speed_of_gust P1D)
  Enhet: m/s
  Tilgjengelig fra: 2018-02-09
  Status: Authoritative
  Tidsoppløsning: P1D

- max(wind_speed_of_gust P1M)
  Enhet: m/s
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- mean(max(wind_speed P1D) P1M)
  Enhet: m/s
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- mean(max(wind_speed PT1H) P1D)
  Enhet: m/s
  Tilgjengelig fra: 2018-02-09
  Status: Authoritative
  Tidsoppløsning: P1D

- mean(wind_speed P1D)
  Enhet: m/s
  Tilgjengelig fra: 2018-02-08
  Status: Authoritative
  Tidsoppløsning: P1D

- mean(wind_speed P1M)
  Enhet: m/s
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- mean(wind_speed_of_gust P1D)
  Enhet: m/s
  Tilgjengelig fra: 2018-02-09
  Status: Authoritative
  Tidsoppløsning: P1D

- mean(wind_speed_of_gust P1M)
  Enhet: m/s
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- min(max(wind_speed P1D) P1M)
  Enhet: m/s
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- min(max(wind_speed PT1H) P1D)
  Enhet: m/s
  Tilgjengelig fra: 2018-02-09
  Status: Authoritative
  Tidsoppløsning: P1D

- min(wind_speed P1D)
  Enhet: m/s
  Tilgjengelig fra: 2018-02-08
  Status: Authoritative
  Tidsoppløsning: P1D

- min(wind_speed P1M)
  Enhet: m/s
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- min(wind_speed_of_gust P1D)
  Enhet: m/s
  Tilgjengelig fra: 2018-02-09
  Status: Authoritative
  Tidsoppløsning: P1D

- min(wind_speed_of_gust P1M)
  Enhet: m/s
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- over_time(time_of_maximum_wind_speed P1M)
  Enhet: Date
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

# Fuktighet

- max(relative_humidity P1D)
  Enhet: percent
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative
  Tidsoppløsning: P1D

- max(relative_humidity P1M)
  Enhet: percent
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- mean(relative_humidity P1D)
  Enhet: percent
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative
  Tidsoppløsning: P1D

- mean(relative_humidity P1M)
  Enhet: percent
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

- min(relative_humidity P1D)
  Enhet: percent
  Tilgjengelig fra: 2018-02-07
  Status: Authoritative
  Tidsoppløsning: P1D

- min(relative_humidity P1M)
  Enhet: percent
  Tilgjengelig fra: 2018-03-01
  Status: Authoritative
  Tidsoppløsning: P1M

=== ALLE TIDSOPPLØSNINGER PER PARAMETER ===

accumulated(precipitation_amount):
  - PT10M
  - PT1H

air_temperature:
  - PT10M
  - PT1H

battery_voltage:
  - PT1H

best_estimate_mean(air_temperature P1M):
  - P1M

best_estimate_mean(air_temperature P1Y):
  - P1Y

best_estimate_mean(air_temperature P3M):
  - P3M

best_estimate_sum(precipitation_amount P1M):
  - P1M

best_estimate_sum(precipitation_amount P1Y):
  - P1Y

best_estimate_sum(precipitation_amount P3M):
  - P3M

best_estimate_sum(precipitation_amount P6M):
  - P1Y

dew_point_temperature:
  - PT1H

integral_of_deficit(mean(air_temperature P1D) P1D 17.0):
  - P1D

integral_of_deficit(mean(air_temperature P1D) P1M 17.0):
  - P1M

integral_of_deficit(mean(air_temperature P1D) P1Y 17.0):
  - P1Y

integral_of_deficit(mean(air_temperature P1D) P3M 17.0):
  - P3M

integral_of_deficit(mean(air_temperature P1D) P6M 17.0):
  - P6M

integral_of_excess(mean(air_temperature P1D) P1D 0.0):
  - P1D

integral_of_excess(mean(air_temperature P1D) P1D 5.0):
  - P1D

integral_of_excess(mean(air_temperature P1D) P1M 0.0):
  - P1M

integral_of_excess(mean(air_temperature P1D) P1M 5.0):
  - P1M

max(air_temperature P1D):
  - P1D

max(air_temperature P1M):
  - P1M

max(air_temperature P1Y):
  - P1Y

max(air_temperature P3M):
  - P3M

max(air_temperature P6M):
  - P6M

max(air_temperature PT12H):
  - PT12H

max(air_temperature PT1H):
  - PT1H

max(max(wind_speed P1D) P1M):
  - P1M

max(max(wind_speed PT1H) P1D):
  - P1D

max(relative_humidity P1D):
  - P1D

max(relative_humidity P1M):
  - P1M

max(sum(precipitation_amount P1D) P1M):
  - P1M

max(surface_snow_thickness P1M):
  - P1M

max(wind_speed P1D):
  - P1D

max(wind_speed P1M):
  - P1M

max(wind_speed PT1H):
  - PT1H

max(wind_speed_of_gust P1D):
  - P1D

max(wind_speed_of_gust P1M):
  - P1M

max(wind_speed_of_gust PT1H):
  - PT1H

max_wind_speed(wind_from_direction PT1H):
  - PT1H

mean(air_temperature P1D):
  - P1D

mean(air_temperature P1M):
  - P1M

mean(air_temperature P1Y):
  - P1Y

mean(air_temperature P3M):
  - P3M

mean(air_temperature P6M):
  - P6M

mean(air_temperature_anomaly P1M 1991_2020):
  - P1M

mean(air_temperature_anomaly P1Y 1961_1990):
  - P1Y

mean(air_temperature_anomaly P1Y 1991_2020):
  - P1Y

mean(air_temperature_anomaly P3M 1961_1990):
  - P3M

mean(air_temperature_anomaly P3M 1991_2020):
  - P3M

mean(air_temperature_anomaly P6M 1961_1990):
  - P6M

mean(air_temperature_anomaly P6M 1991_2020):
  - P6M

mean(dew_point_temperature P1D):
  - P1D

mean(dew_point_temperature P1M):
  - P1M

mean(max(air_temperature P1D) P1M):
  - P1M

mean(max(wind_speed P1D) P1M):
  - P1M

mean(max(wind_speed PT1H) P1D):
  - P1D

mean(min(air_temperature P1D) P1M):
  - P1M

mean(relative_humidity P1D):
  - P1D

mean(relative_humidity P1M):
  - P1M

mean(surface_snow_thickness P1M):
  - P1M

mean(water_vapor_partial_pressure_in_air P1D):
  - P1D

mean(water_vapor_partial_pressure_in_air P1M):
  - P1M

mean(wind_speed P1D):
  - P1D

mean(wind_speed P1M):
  - P1M

mean(wind_speed_of_gust P1D):
  - P1D

mean(wind_speed_of_gust P1M):
  - P1M

min(air_temperature P1D):
  - P1D

min(air_temperature P1M):
  - P1M

min(air_temperature P1Y):
  - P1Y

min(air_temperature P3M):
  - P3M

min(air_temperature P6M):
  - P6M

min(air_temperature PT12H):
  - PT12H

min(air_temperature PT1H):
  - PT1H

min(max(wind_speed P1D) P1M):
  - P1M

min(max(wind_speed PT1H) P1D):
  - P1D

min(relative_humidity P1D):
  - P1D

min(relative_humidity P1M):
  - P1M

min(surface_snow_thickness P1M):
  - P1M

min(wind_speed P1D):
  - P1D

min(wind_speed P1M):
  - P1M

min(wind_speed_of_gust P1D):
  - P1D

min(wind_speed_of_gust P1M):
  - P1M

number_of_days_gte(sum(precipitation_amount P1D) P1M 1.0):
  - P1M

over_time(gauge_content_difference PT1H):
  - PT1H

over_time(sum(time_of_maximum_precipitation_amount P1D) P1M):
  - P1M

over_time(time_of_maximum_air_temperature P1M):
  - P1M

over_time(time_of_maximum_wind_speed P1M):
  - P1M

over_time(time_of_minimum_air_temperature P1M):
  - P1M

relative_humidity:
  - PT1H

sum(duration_of_precipitation PT10M):
  - PT10M

sum(duration_of_precipitation PT1H):
  - PT1H

sum(precipitation_amount P1D):
  - P1D

sum(precipitation_amount P1M):
  - P1M

sum(precipitation_amount P1Y):
  - P1Y

sum(precipitation_amount P30D):
  - P1D

sum(precipitation_amount P3M):
  - P3M

sum(precipitation_amount P6M):
  - P6M

sum(precipitation_amount PT10M):
  - PT10M

sum(precipitation_amount PT12H):
  - PT12H

sum(precipitation_amount PT1H):
  - PT1H

surface_snow_thickness:
  - P1D
  - PT10M
  - PT1H

surface_temperature:
  - PT10M
  - PT1H

wind_from_direction:
  - PT1H

wind_speed:
  - PT1H
