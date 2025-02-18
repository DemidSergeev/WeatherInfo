import openmeteo_requests

from datetime import datetime
from typing import Annotated

from fastapi import FastAPI, Query, Body
from pydantic import BaseModel, Field

url = "https://api.open-meteo.com/v1/forecast"

app = FastAPI()

openmeteo = openmeteo_requests.Client()

class Location(BaseModel):
    latitude: float = Field(59.95, ge=-90, le=90)
    longitude: float = Field(30.32, ge=-180, le=180)

class WeatherData(BaseModel):
    temperature: float
    humidity: float = Field(ge=0, le=100)
    precipitation: float = Field(ge=0)
    pressure: float = Field(ge=0)
    wind_speed: float = Field(ge=0)
    wind_direction: int = Field(ge=0, le=360)

class Forecast(BaseModel):
    time: datetime
    data: WeatherData

tracked_cities: dict[str, tuple[Location, list[Forecast]]] = {}

@app.get("/weather/now", description="Return temperature, pressure and wind speed for current time given the coordinates.")
async def current_weather(location: Annotated[Location, Query(title="Valid geographic coordinates")]):
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
async def add_city(
                    city: Annotated[str, Body(
                                            title="Name of city",
                                            description="Used like a label for geographic coordinates.",
                                            pattern=r"[^\W\d_]+",
                                            examples=[
                                                "Санкт-Петербург"
                                            ])
                                    ],
                    location: Annotated[Location, Body(title="Coordinates of given city")]
                    ):
    if city in tracked_cities:
        return
    else:
        tracked_cities[city] = (location, [])
        return

@app.get("/tracking", description="Returns cities which are in forecast-tracking map.")
async def show_tracked():
    return { "cities": list(tracked_cities.keys()) }