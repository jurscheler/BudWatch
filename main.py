import requests
import time
import pyodbc
from datetime import datetime

token = ""
email = "rurscheler@gmail.com"
password = "Asd123!."

# Define the connection string
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"  # Replace with your server name
    "DATABASE=BudWatch;"  # Replace with your database name
    "UID=admin;"  # Replace with your username
    "PWD=957Bruce;"  # Replace with your password
)

def authorize():
    global token
    try:
        # Use the 'json' parameter to send JSON data in the request body
        response = requests.post(
            "https://api.sensorpush.com/api/v1/oauth/authorize",
            json={"email": email, "password": password}
        )

        # Check if the request was successful
        if response.status_code == 200:
            # Get the JSON response and save to variable
            token = response.json().get("authorization")
            print(f"Token: {token}")
        else:
            print(f"Error: {response.status_code}")
    
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

def fetch_data():
    global token
    if not token:
        print("No token available. Please authorize first.")
        return None

    try:
        headers = {
            'Authorization': f'Bearer {token}'  # Assuming the API expects a Bearer token
        }
        print(f"headers: {headers}")
        
        # Use the 'json' parameter to send JSON data in the request body
        response = requests.post(
            "https://api.sensorpush.com/api/v1/samples",
            headers=headers,
            json={"limit": 1}
        )

        # Check if the request was successful
        if response.status_code == 200:
            # Get the JSON response
            sensor_data = response.json()
            print(f"Sensor Data: {sensor_data}")
            return sensor_data
        else:
            print(f"Error: {response.status_code}")
            return None
    
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

def save_data(sensorid, observed, temperature, humidity):
    # Save to database
    try:
        # Establish the connection
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Convert the observed timestamp to a datetime object
        observed_datetime = datetime.strptime(observed, "%Y-%m-%dT%H:%M:%S.%fZ")

        # SQL INSERT statement
        insert_query = """
        INSERT INTO sensor_data (sensorid, date, temperature, humidity)
        VALUES (?, ?, ?, ?)
        """

        # Execute the query
        cursor.execute(insert_query, sensorid, observed_datetime, temperature, humidity)

        # Commit the transaction
        conn.commit()
        print("Data inserted successfully!")

    except pyodbc.Error as e:
        print(f"An error occurred: {e}")

    finally:
        # Close the cursor and connection
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def main():
    # Authorize
    authorize()

    # Forever, every 10 seconds 
    while True:
        # Fetch current data from all sensors
        sensor_data = fetch_data()

        if sensor_data and "sensors" in sensor_data:
            # Iterate through each sensor in the response
            for sensorid, readings in sensor_data["sensors"].items():
                for reading in readings:
                    # Extract relevant fields
                    observed = reading.get("observed")
                    temperature = reading.get("temperature")
                    humidity = reading.get("humidity")

                    # Save data into sensor_data table of MS SQL database
                    if observed and temperature and humidity:
                        save_data(sensorid, observed, temperature, humidity)
                    else:
                        print("Missing data in sensor reading. Skipping.")

        # Wait for 10 seconds before fetching data again
        time.sleep(10)

if __name__ == "__main__":
    main()