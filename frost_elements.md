# Elements for Frost

## Elements

Liste over alle værelementene som er tilgjengelige med 1-times oppløsning fra stasjon SN46220:

curl -X GET "https://frost.met.no/observations/v0.jsonld?sources=SN46220&referencetime=PT1H/now&elements=air_temperature,\
sum(precipitation_amount%20PT1H),\
wind_speed,\
wind_from_direction,\
mean(relative_humidity%20PT1H),\
max(wind_speed_of_gust%20PT1H),\
mean(surface_air_pressure%20PT1H),\
mean(cloud_area_fraction%20PT1H),\
weather_type,\
mean(air_temperature%20PT1H),\
min(air_temperature%20PT1H),\
max(air_temperature%20PT1H),\
mean(dew_point_temperature%20PT1H),\
sum(duration_of_sunshine%20PT1H),\
mean(global_radiation%20PT1H)" \
--header "Accept: application/json" \
-u 43fefca2-a26b-415b-954d-ba9af37e3e1f:



Temperatur:
- air_temperature: Lufttemperatur
- min(air_temperature PT1H): Minimum lufttemperatur
- max(air_temperature PT1H): Maksimum lufttemperatur
- mean(air_temperature PT1H): Gjennomsnittlig lufttemperatur
- grass_temperature: Gresstemperatur
- min(grass_temperature PT1H): Minimum gresstemperatur
- max(grass_temperature PT1H): Maksimum gresstemperatur
- mean(grass_temperature PT1H): Gjennomsnittlig gresstemperatur
- min(snow_temperature PT1H): Minimum snøtemperatur
- max(snow_temperature PT1H): Maksimum snøtemperatur
- mean(snow_temperature PT1H): Gjennomsnittlig snøtemperatur
- min(runway_temperature PT1H): Minimum rullebanetemperatur
- max(runway_temperature PT1H): Maksimum rullebanetemperatur
- mean(runway_temperature PT1H): Gjennomsnittlig rullebanetemperatur



Nedbør
- sum(precipitation_amount PT1H): Nedbørmengde
- sum(duration_of_precipitation PT1H): Antall minutter med nedbør
- sum(duration_of_precipitation_as_rain PT1H): Antall minutter med regn
- sum(duration_of_precipitation_as_snow PT1H): Antall minutter med snø
- sum(duration_of_precipitation_as_drizzle PT1H): Antall minutter med yr
- sum(duration_of_precipitation_as_hail PT1H): Antall minutter med hagl

Vind:
- wind_speed: Vindhastighet
- mean(wind_speed PT1H): Gjennomsnittlig vindhastighet
- min(wind_speed PT1H): Minimum vindhastighet
- max(wind_speed PT1H): Maksimum vindhastighet
- wind_from_direction: Vindretning
- mean(wind_from_direction PT1H): Gjennomsnittlig vindretning
- wind_speed_of_gust: Vindkast
- max(wind_speed_of_gust PT1H): Maksimum vindkast

Luftfuktighet:
- relative_humidity: Relativ luftfuktighet
- mean(relative_humidity PT1H): Gjennomsnittlig luftfuktighet
- min(relative_humidity PT1H): Minimum luftfuktighet
- max(relative_humidity PT1H): Maksimum luftfuktighet
- dew_point_temperature: Duggpunktstemperatur
- min(dew_point_temperature PT1H): Minimum duggpunktstemperatur
- max(dew_point_temperature PT1H): Maksimum duggpunktstemperatur
- sum(duration_of_leaf_wetness PT1H): Varighet av bladfuktighet

Snø
- snow_temperature: Snøtemperatur (ved ulike dybder, standard 10 cm)
- mean(snow_temperature PT1H): Gjennomsnittlig snøtemperatur
- min(snow_temperature PT1H): Minimum snøtemperatur
- max(snow_temperature PT1H): Maksimum snøtemperatur

- sum(duration_of_precipitation_as_snow PT1H): Antall minutter med snøfall siste time
- sum(duration_of_precipitation_as_snow PT10M): Antall minutter med snøfall siste 10 min


For å hente flere elementer samtidig, kan du liste dem opp i elements-parameteren:
curl -X GET "https://frost.met.no/observations/v0.jsonld?sources=SN46220&referencetime=PT1H/now&elements=air_temperature,sum(precipitation_amount%20PT1H),wind_speed,wind_from_direction,mean(relative_humidity%20PT1H)" \
--header "Accept: application/json" \
-u 43fefca2-a26b-415b-954d-ba9af37e3e1f:

surface_snow_thickness (cm) - Snødybde
max(wind_speed_of_gust PT1H) (m/s) - Maksimal vindkast siste time
max(wind_speed PT1H) (m/s) - Maksimal vindhastighet siste time
wind_speed (m/s) - Vindhastighet
relative_humidity (%) - Relativ luftfuktighet
air_temperature (°C) - Lufttemperatur
wind_from_direction (grader) - Vindretning
over_time(gauge_content_difference PT1H) - Nedbørmåler differanse
surface_temperature (°C) - Bakketemperatur
min(air_temperature PT1H) (°C) - Minimum lufttemperatur siste time
battery_voltage (volt) - Batterispenning
sum(duration_of_precipitation PT1H) (minutter) - Varighet av nedbør siste time
sum(precipitation_amount PT1H) (mm) - Nedbørmengde siste time
accumulated(precipitation_amount) (mm) - Akkumulert nedbør
max(air_temperature PT1H) (°C) - Maksimal lufttemperatur siste time
wind_from_direction (grader) - Vindretning
dew_point_temperature (°C) - Duggpunktstemperatur

Alle disse målingene er tilgjengelige med timeoppløsning (PT1H) og har vært aktive siden februar 2018.

den fungerende elementlisten:
elements = "surface_snow_thickness,max(wind_speed_of_gust PT1H),max(wind_speed PT1H),wind_speed,relative_humidity,air_temperature,wind_from_direction,surface_temperature,min(air_temperature PT1H),sum(duration_of_precipitation PT1H),sum(precipitation_amount PT1H),max(air_temperature PT1H),dew_point_temperature"
"
