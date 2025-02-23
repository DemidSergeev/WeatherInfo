# WeatherInfo
The program is a test project which implements **FastAPI-based REST API service**. It provides weather forecasting and tracking functionalities. It interacts with the **Open-Meteo API** to fetch weather data and stores user-specific city tracking information in an **SQLite database**. 

---

# Setup
1. Clone repository.
2. Create and activate `venv`.
3. Install requirements: `pip install -r requirements.txt`
4. Run script: `python3 main.py`.
5. The API is now available at `127.0.0.1:8000`.
---

Below is detailed description of what the program can do:
### 1. **Current Weather Data**
   - **Endpoint**: `GET /weather/now`
   - **Description**: 
     - This method accepts geographic coordinates (latitude and longitude) and returns the current temperature, wind speed, and atmospheric pressure at the specified location.
---

### 2. **Add City for Weather Tracking**
   - **Endpoint**: `POST /tracking/{user_id}`
   - **Description**: 
     - This method allows a user to add a city (with its name and coordinates) to their personal list of tracked cities.
     - The server stores the city's location and starts tracking its weather forecasts.
     - The weather data for tracked cities is updated every 15 minutes using a background scheduler.

---

### 3. **Get List of Tracked Cities**
   - **Endpoint**: `GET /tracking/{user_id}`
   - **Description**: 
     - This method returns a list of cities that a specific user is currently tracking for weather forecasts.
     - The user is identified by their unique `user_id`.

---

### 4. **Get Weather Forecast for a Specific Time**
   - **Endpoint**: `GET /tracking/{user_id}/{city}`
   - **Description**: 
     - This method provides the weather forecast for a specific city at a given time on the current day.
     - The user can specify which weather parameters they want to receive (e.g., temperature, humidity, wind speed, precipitation, pressure).
     - The server returns the closest available forecast preceding the specified time.

---

### 5. **User Registration**
   - **Endpoint**: `POST /register`
   - **Description**: 
     - This method allows new users to register by providing a username.
     - The server generates a unique `user_id` for the user (using a hash of the username) and stores the user in the database.

---

### Additional Features:
- **Background Scheduler**:
  - The server uses a background scheduler to update weather forecasts for all tracked cities every 15 minutes.
  
- **Database Storage**:
  - The server stores weather data and user information in an SQLite database.
  - Weather data is serialized into JSON and stored in the `weather_data` table.
  - User data (including tracked cities) is serialized into JSON and stored in the `users` table.

- **Error Handling**:
  - The server provides appropriate error responses (e.g., `404 Not Found`, `409 Conflict`, `400 Bad Request`) for invalid requests or conflicts.

---

### Example Workflow:
1. A new user registers using the `/register` endpoint and receives a `user_id`.
2. The user adds a city (e.g., "Saint Petersburg") to their tracking list using the `/tracking/{user_id}` endpoint.
3. The server starts tracking weather forecasts for the city and updates the data every 15 minutes.
4. The user can retrieve the list of tracked cities using the `/tracking/{user_id}` endpoint.
5. The user can request the weather forecast for a specific city and time using the `/tracking/{user_id}/{city}` endpoint.
