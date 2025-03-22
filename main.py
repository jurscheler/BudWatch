import requests
import time
import os
import pyodbc
from datetime import datetime

# Environment variables setup remains the same
sp_email = os.getenv('BUDWATCH_EMAIL')
sp_password = os.getenv('BUDWATCH_PASSWORD')

server = os.getenv('BUDWATCH_SQL_SERVER', 'localhost')
database = os.getenv('BUDWATCH_SQL_DATABASE', 'BudWatch')
username = os.getenv('BUDWATCH_SQL_USERNAME', 'admin')
password = os.getenv('BUDWATCH_SQL_PASSWORD')

token = ""
conn_str = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={password};"
)

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def authorize():
    global token
    try:
        response = requests.post(
            "https://api.sensorpush.com/api/v1/oauth/authorize",
            json={"email": sp_email, "password": sp_password}
        )

        if response.status_code == 200:
            token = response.json().get("authorization")
            print(f"[{get_timestamp()}] Authorization successful. Token: {token[:15]}...")  # Truncate for security
            return True
        print(f"[{get_timestamp()}] Authorization failed: HTTP {response.status_code}")
        return False
    
    except requests.exceptions.RequestException as e:
        print(f"[{get_timestamp()}] Network error during authorization: {str(e)}")
        return False
    except Exception as e:
        print(f"[{get_timestamp()}] Unexpected error in authorization: {str(e)}")
        return False

def fetch_data():
    global token
    try:
        if not token:
            print(f"[{get_timestamp()}] No authorization token available")
            return None

        response = requests.post(
            "https://api.sensorpush.com/api/v1/samples",
            headers={'Authorization': f'Bearer {token}'},
            json={"limit": 1},
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            print(f"[{get_timestamp()}] Token expired or invalid")
            token = None  # Force re-authorization
        else:
            print(f"[{get_timestamp()}] API request failed: HTTP {response.status_code}")
        return None

    except requests.exceptions.RequestException as e:
        print(f"[{get_timestamp()}] Network error during data fetch: {str(e)}")
        return None
    except Exception as e:
        print(f"[{get_timestamp()}] Unexpected error in data fetch: {str(e)}")
        return None

def save_data(sensorid, observed, temperature, humidity):
    try:
        observed_datetime = datetime.strptime(observed, "%Y-%m-%dT%H:%M:%S.%fZ")
        with pyodbc.connect(conn_str) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO sensor_data (sensorid, date, temperature, humidity) VALUES (?, ?, ?, ?)",
                    sensorid, observed_datetime, temperature, humidity
                )
                conn.commit()
        # Added data details in success message
        print(f"[{get_timestamp()}] Data saved | Sensor: {sensorid} | "
              f"Time: {observed} | Temp: {temperature}°C | Humidity: {humidity}%")
        return True
    
    except pyodbc.Error as e:
        print(f"[{get_timestamp()}] Database error: {str(e)}")
        return False
    except Exception as e:
        print(f"[{get_timestamp()}] Unexpected error in save_data: {str(e)}")
        return False

def main():
    # Initial authorization with retries
    while True:
        if authorize():
            break
        print(f"[{get_timestamp()}] Retrying authorization in 60 seconds...")
        time.sleep(60)

    # Main monitoring loop
    while True:
        try:
            sensor_data = fetch_data()
            
            if not sensor_data or "sensors" not in sensor_data:
                print(f"[{get_timestamp()}] Invalid data format or empty response")
                raise ConnectionError("Invalid API response")

            data_saved = False
            for sensorid, readings in sensor_data["sensors"].items():
                for reading in readings:
                    if all(k in reading for k in ("observed", "temperature", "humidity")):
                        if save_data(sensorid, **{k: reading[k] for k in ("observed", "temperature", "humidity")}):
                            data_saved = True

            if not data_saved:
                print(f"[{get_timestamp()}] No valid data processed in this cycle")

        except (ConnectionError, requests.exceptions.RequestException) as e:
            print(f"[{get_timestamp()}] Network-related error: {str(e)}. Re-authenticating...")
            if not authorize():
                print(f"[{get_timestamp()}] Re-authorization failed. Will retry in next cycle")

        except Exception as e:
            print(f"[{get_timestamp()}] Unexpected error: {str(e)}. Restarting cycle...")

        finally:
            time.sleep(60)

if __name__ == "__main__":
    main()