# AirScope AQI Dashboard

AirScope searches for a city and displays pollutant readings reported by nearby monitoring stations. It can estimate a U.S.-scale AQI from the latest PM2.5 or PM10 reading when that data is available.


## About the AQI number

The displayed U.S. AQI is an estimate based on a nearby station's latest PM2.5 or PM10 reading. Official AQI reporting uses time-averaged measurements, so this estimate can differ from Google or government dashboards. If no suitable reading is available, AirScope does not invent a number. Station coverage and reporting freshness vary by location.

## Data sources

- Station readings: [OpenAQ](https://openaq.org/)
- City search: [Open-Meteo Geocoding](https://open-meteo.com/en/docs/geocoding-api)
- U.S. AQI breakpoints: [U.S. EPA](https://aqs.epa.gov/aqsweb/documents/codetables/aqi_breakpoints.html)

## Hosting note

Uploading this source to GitHub creates a code repository. GitHub Pages alone cannot run the Python API proxy; live station search needs the Python server and its private OpenAQ key.
