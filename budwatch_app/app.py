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
    return round((f - 32) * 5 / 9, 1)  # Round to 1 decimal place

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

    # Fetch sensor IDs and names from the sensors table
    cursor.execute('SELECT sensorid, name FROM sensors ORDER BY name')
    sensors = cursor.fetchall()  # List of (sensorid, name) tuples

    # Fetch data for the default sensor (first sensor in the list), ordered by date DESC
    default_sensor = sensors[0] if sensors else None
    if default_sensor:
        default_sensor_id, default_sensor_name = default_sensor
        cursor.execute('''
            SELECT sd.id, sd.sensorid, sd.date, sd.temperature, sd.humidity, s.name
            FROM sensor_data sd
            JOIN sensors s ON sd.sensorid = s.sensorid
            WHERE sd.sensorid = ?
            ORDER BY sd.date DESC
        ''', (default_sensor_id,))
        default_sensor_data = cursor.fetchall()
        # Convert temperature to Celsius and GMT to EST
        default_sensor_data = [
            (row.id, row.sensorid, convert_gmt_to_est(row.date), fahrenheit_to_celsius(row.temperature), row.humidity, row.name)
            for row in default_sensor_data
        ]
    else:
        default_sensor_data = []

    conn.close()

    return render_template('index.html', sensors=sensors, default_sensor=default_sensor, default_sensor_data=default_sensor_data)

@app.route('/graph')
def graph():
    # Get the sensorid from the query parameters
    sensorid = request.args.get('sensorid')
    
    # Validate the sensorid
    if not sensorid:
        return "Sensor ID is missing in the request.", 400

    # Fetch data for the selected sensor, ordered by date DESC
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sd.date, sd.temperature, sd.humidity, s.name
        FROM sensor_data sd
        JOIN sensors s ON sd.sensorid = s.sensorid
        WHERE sd.sensorid = ?
        ORDER BY sd.date DESC
    ''', (sensorid,))
    data = cursor.fetchall()
    conn.close()

    # Convert temperature to Celsius and GMT to EST
    data = [
        (convert_gmt_to_est(row.date), fahrenheit_to_celsius(row.temperature), row.humidity, row.name)
        for row in data
    ]
    return render_template('graph.html', sensorid=sensorid, data=data)

@app.route('/api/sensor/<sensorid>')
def api_sensor_data(sensorid):
    # Fetch data for the selected sensor
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sd.date, sd.temperature, sd.humidity, s.name
        FROM sensor_data sd
        JOIN sensors s ON sd.sensorid = s.sensorid
        WHERE sd.sensorid = ?
        ORDER BY sd.date DESC
    ''', (sensorid,))
    data = cursor.fetchall()
    conn.close()

    # Format data for the frontend
    result = {
        'timestamps': [convert_gmt_to_est(row.date).strftime('%Y-%m-%d %H:%M:%S') for row in data],  # Convert GMT to EST
        'temperature': [round(fahrenheit_to_celsius(row.temperature), 1) for row in data],  # Round temperature to 1 decimal place
        'humidity': [round(row.humidity, 1) for row in data],  # Round humidity to 1 decimal place
        'sensor_name': data[0].name if data else None  # Include sensor name in the response
    }
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)