import openmeteo_requests

from datetime import datetime
from typing import Annotated

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

url = "https://api.open-meteo.com/v1/forecast"

app = FastAPI()

openmeteo = openmeteo_requests.Client()

class Location(BaseModel):
    latitude: float = Field(59.95, ge=-90, le=90)
    longitude: float = Field(30.32, ge=-180, le=180)

@app.get("/weather/now")
async def current_weather(location: Annotated[Location, Query(title="Valid geographic coordinates")]):
    """Return temperature, pressure and wind speed for current time given the coordinates."""
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