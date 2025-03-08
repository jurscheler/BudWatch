from flask import Flask, render_template, request, jsonify
import pyodbc
import os
from datetime import datetime
import pytz  # For time zone conversion

app = Flask(__name__)

# Database connection details
SERVER = os.getenv('BUDWATCH_SQL_SERVER', 'localhost')  # Default to 'localhost' if not set
DATABASE = os.getenv('BUDWATCH_SQL_DATABASE', 'BudWatch')  # Default to 'BudWatch' if not set
USERNAME = os.getenv('BUDWATCH_SQL_USERNAME', 'admin')  # Default to 'admin' if not set
PASSWORD = os.getenv('BUDWATCH_SQL_PASSWORD')
CONNECTION_STRING = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD}'

def get_db_connection():
    return pyodbc.connect(CONNECTION_STRING)

def fahrenheit_to_celsius(f):
    return (f - 32) * 5 / 9

def convert_gmt_to_est(gmt_time):
    """
    Converts a timezone-naive GMT datetime to EST.
    """
    # Define GMT and EST time zones
    gmt = pytz.timezone('GMT')
    est = pytz.timezone('US/Eastern')
    
    # Ensure the input is a datetime object
    if not isinstance(gmt_time, datetime):
        raise ValueError("Input must be a datetime object.")
    
    # Localize the naive datetime to GMT
    if gmt_time.tzinfo is None:
        gmt_time = gmt.localize(gmt_time)
    
    # Convert to EST
    est_time = gmt_time.astimezone(est)
    return est_time

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch unique sensor IDs
    cursor.execute('SELECT DISTINCT sensorid FROM sensor_data ORDER BY sensorid')
    sensor_ids = [row.sensorid for row in cursor.fetchall()]  # Access by column name

    # Fetch data for the default sensor (first sensor in the list), ordered by date DESC
    default_sensor_id = sensor_ids[0] if sensor_ids else None
    if default_sensor_id:
        cursor.execute('SELECT id, sensorid, date, temperature, humidity FROM sensor_data WHERE sensorid = ? ORDER BY date DESC', (default_sensor_id,))
        default_sensor_data = cursor.fetchall()
        # Convert temperature to Celsius and GMT to EST
        default_sensor_data = [
            (row.id, row.sensorid, convert_gmt_to_est(row.date), fahrenheit_to_celsius(row.temperature), row.humidity)
            for row in default_sensor_data
        ]
    else:
        default_sensor_data = []

    conn.close()

    return render_template('index.html', sensor_ids=sensor_ids, default_sensor_id=default_sensor_id, default_sensor_data=default_sensor_data)

@app.route('/graph/<sensorid>')
def graph(sensorid):
    # Fetch data for the selected sensor, ordered by date DESC
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT date, temperature, humidity FROM sensor_data WHERE sensorid = ? ORDER BY date DESC', (sensorid,))
    data = cursor.fetchall()
    # Convert temperature to Celsius and GMT to EST
    data = [
        (convert_gmt_to_est(row.date), fahrenheit_to_celsius(row.temperature), row.humidity)
        for row in data
    ]
    conn.close()
    return render_template('graph.html', sensorid=sensorid, data=data)

@app.route('/api/sensor/<sensorid>')  # Treat sensorid as a string
def api_sensor_data(sensorid):
    # API endpoint for fetching sensor data (used by Chart.js)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT date, temperature, humidity FROM sensor_data WHERE sensorid = ?', (sensorid,))
    data = cursor.fetchall()
    conn.close()
    # Format data for Chart.js
    result = {
        'timestamps': [convert_gmt_to_est(row.date).strftime('%Y-%m-%d %H:%M:%S') for row in data],  # Convert GMT to EST
        'temperature': [fahrenheit_to_celsius(row.temperature) for row in data],
        'humidity': [row.humidity for row in data]
    }
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)