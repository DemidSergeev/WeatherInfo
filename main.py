import openmeteo_requests
import requests_cache
from retry_requests import retry

from datetime import datetime, date, time
from typing import Annotated
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler

from fastapi import FastAPI, HTTPException, Query, Body, Path
from pydantic import BaseModel, Field
import pandas as pd
import sqlite3
import json

# Configuring Open-meteo API
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)
url = "https://api.open-meteo.com/v1/forecast"

class Location(BaseModel):
    """Model class for coupling together `latitude` and `longitude`."""

    latitude: float = Field(59.95, ge=-90, le=90)
    longitude: float = Field(30.32, ge=-180, le=180)


class WeatherData(BaseModel):
    """Model class for a variety of weather data parameters at a given moment."""

    temperature: float | None = None
    humidity: float | None = Field(default=None, ge=0, le=100)
    precipitation: float | None = Field(default=None, ge=0)
    pressure: float | None = Field(default=None, ge=0)
    wind_speed: float | None = Field(default=None, ge=0)
    wind_direction: float | None = Field(default=None, ge=0, le=360)


class ForecastQueryParameters(BaseModel):
    """Model class for specifying whether some weather parameter should be returned or not."""

    daytime: str | None = Field(None, max_length=5, description="Daytime in HH:mm format.")
    temperature: bool | None = True
    humidity: bool | None = True
    precipitation: bool | None = True
    pressure: bool | None = True
    wind_speed: bool | None = True
    wind_direction: bool | None = True


class Forecast(BaseModel):
    """Model class for representing a forecast at specified time."""

    time: datetime
    data: WeatherData

class CityWeatherData(BaseModel):
    """Model class for representing a list of forecasts for specific location"""

    location: Location
    forecasts: list[Forecast]

def update_forecasts_for_city(city: str) -> None:
    """Updates forecasts list for single city."""

    location = tracked_cities[city].location

    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "minutely_15": ["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m", "wind_direction_10m"],
        "hourly": "surface_pressure",
        "forecast_days": 1
    }

    responses = openmeteo.weather_api(url, params)

    response = responses[0]

    tracked_cities[city].forecasts = parse_forecasts(response)


def update_forecasts() -> None:
    """Updates forecast-tracking map (`tracked_cities`) with new data."""

    latitudes = [city_weather_data.location.latitude for city_weather_data in tracked_cities.values()]
    longitudes = [city_weather_data.location.longitude for city_weather_data in tracked_cities.values()]

    params = {
        "latitude": latitudes,
        "longitude": longitudes,
        "minutely_15": ["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m", "wind_direction_10m"],
        "hourly": "surface_pressure",
        "forecast_days": 1
    }

    # Perform request to open-meteo API
    responses = openmeteo.weather_api(url, params)

    for i, (city, city_weather_data) in enumerate(tracked_cities.items()):
        response = responses[i]
        city_weather_data.forecasts = parse_forecasts(response)

        
def parse_forecasts(response):
    """Return forecasts list parsed from open-meteo API response."""

    forecasts = []
    # Get 15-minute interval data
    minutely_15 = response.Minutely15()
    temperature = minutely_15.Variables(0).ValuesAsNumpy()
    humidity = minutely_15.Variables(1).ValuesAsNumpy()
    precipitation = minutely_15.Variables(2).ValuesAsNumpy()
    wind_speed = minutely_15.Variables(3).ValuesAsNumpy()
    wind_direction = minutely_15.Variables(4).ValuesAsNumpy()

    # Get 1-hour interval data
    hourly = response.Hourly()
    pressure = hourly.Variables(0).ValuesAsNumpy()

    # Get time range for forecasts
    time_range = pd.date_range(
        start=pd.to_datetime(minutely_15.Time(), unit="s"),
        end=pd.to_datetime(minutely_15.TimeEnd(), unit="s"),
        freq=pd.Timedelta(seconds=minutely_15.Interval()),
        inclusive="left"
    )
    
    for i in range(len(time_range)):
        new_forecast = Forecast(
            time=time_range[i],
            data=WeatherData(
                temperature= temperature[i],
                humidity=humidity[i],
                precipitation=precipitation[i],
                wind_speed=wind_speed[i],
                wind_direction=wind_direction[i],
                pressure=pressure[i // 4] # Pressure data is hourly, so it is duplicated 4 times across the hour
            )
        )
        forecasts.append(new_forecast)

    return forecasts


tracked_cities: dict[str, CityWeatherData] = {}


def dump_to_db(cursor: sqlite3.Cursor, tracked_cities: dict[str, CityWeatherData]) -> None:
    """Serialize forecast-tracking map into JSON and store in sqlite3 database"""

    json_data = json.dumps(tracked_cities, default=lambda o: o.model_dump() if isinstance(o, BaseModel) else None)
    cursor.execute("INSERT INTO weather_data (data) VALUES (?)", (json_data,))

def load_from_db(cursor: sqlite3.Cursor) -> dict[str, CityWeatherData]:
    """Load JSON from DB and deserialize into forecast-tracking map"""

    # Load JSON from DB
    cursor.execute("SELECT data FROM weather_data ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if not row:
        return {}
    
    json_data = row[0]

    # Deserialize JSON into forecast-tracking map
    def custom_decoder(obj):
        if "latitude" in obj and "longitude" in obj:
            return Location(**obj)
        if "time" in obj and "data" in obj:
            return Forecast(time=datetime.fromisoformat(obj["time"]), data=WeatherData(**obj["data"]))
        return obj

    tracked_cities = json.loads(json_data, object_hook=custom_decoder)
    return tracked_cities

# This context manager performs startup and shutdown operations and is passed into FastAPI app instance
@asynccontextmanager
async def lifespan(app: FastAPI):
    connection = sqlite3.connect("tracked_cities.db") 
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weather_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT
    )
    """)
    connection.commit()
    
    # Load forecast-tracking map from DB
    tracked_cities = load_from_db(cursor)
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_forecasts, "interval", minutes=15)
    scheduler.start()

    update_forecasts()

    yield

    scheduler.shutdown()
    dump_to_db(cursor, tracked_cities)
    connection.commit()
    connection.close()


app = FastAPI(lifespan=lifespan)


@app.get("/weather/now", description="Return temperature, pressure and wind speed for current time given the coordinates.")
async def current_weather(location: Annotated[Location, Query(title="Valid geographic coordinates")]):
    """Perform request to open-meteo API to receive current-time temperatue, pressure and wind speed in the given `location`."""
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "current": [
            "temperature_2m",
            "surface_pressure",
            "wind_speed_10m"
            ],
        "forecast_days": 1
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]

    current = response.Current()

    time = current.Time()

    temperature = current.Variables(0).Value()
    pressure = current.Variables(1).Value()
    wind_speed = current.Variables(2).Value()

    return {
        "location": location,
        "time": datetime.fromtimestamp(time),
        "temperature": temperature,
        "wind_speed": wind_speed,
        "pressure": pressure
            }

@app.post("/tracking", description="Add city with its location coordinates to forecast-tracking map.")
async def add_city(city: Annotated[str, Body(
                                            title="Name of city",
                                            description="Used like a label for geographic coordinates.",
                                            pattern=r"^[a-zA-Zа-яА-ЯёЁ-]+$",
                                            examples=[
                                                "Санкт-Петербург"
                                            ])
                                    ],
                    location: Annotated[Location, Body(title="Coordinates of given city")]):
    """Add `location` into forecast-tracking map for key `city`.
    
    If `city` already exists, do nothing."""

    if city not in tracked_cities:
        tracked_cities[city] = CityWeatherData(location=location, forecasts=[])
        update_forecasts_for_city(city)

@app.get("/tracking", description="Returns cities which are in forecast-tracking map.")
async def get_tracked():
    """Return a list of cities that are currently being tracked for forecasts."""
    return { "cities": list(tracked_cities.keys()) }

@app.get("/tracking/{city}", description="Returns today's forecast for specified city and daytime.")
async def get_forecast(city: Annotated[str, Path(title="City name.",
                                                 description="Name of the city. It must already exist in forecast-tracking map.",
                                                 pattern=r"^[a-zA-Zа-яА-ЯёЁ-]+$")],
                        parameters: Annotated[ForecastQueryParameters, Query()]):
    """Return forecast for specified daytime for a city that exists in forecast-tracking map.
    
    It returns a closest preceding forecast.
    If city is not tracked, return 404 status code."""

    if city not in tracked_cities:
        raise HTTPException(status_code=404, detail="City not found in forecast-tracking map.")

    forecast_datetime = datetime.now()
    daytime = parameters.daytime
    if daytime:
        forecast_day = date.today()
        try:
            forecast_time = datetime.strptime(daytime, "%H:%M").time()
            forecast_datetime = datetime.combine(forecast_day, forecast_time)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Incorrect daytime syntax: '{daytime}'. Should be HH:mm")

    forecasts = tracked_cities[city].forecasts # accessing forecasts list for specified city

    forecast = search_forecast(forecasts, forecast_datetime)

    if not forecast:
        raise HTTPException(status_code=404, detail="No forecast found for specified time.")

    # Filter the forecast data based on the requested parameters
    filtered_data = {
        field: getattr(forecast.data, field)
        for field in parameters.dict()
        if field != "daytime" and getattr(parameters, field) is True
    }
    return filtered_data

def search_forecast(forecasts: list[Forecast], forecast_datetime: datetime) -> Forecast:
    """Return the latest forecast preceding `forecast_datetime`."""

    if not forecasts:
        return None

    l, r = 0, len(forecasts) - 1
    result = None

    while l <= r:
        m = (l + r) // 2
        if forecasts[m].time <= forecast_datetime:
            result = forecasts[m]
            l = m + 1
        else:
            r = m - 1
        
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)