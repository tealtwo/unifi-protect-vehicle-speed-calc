# Copyright ©️ Project Teal Lvbs. License Applies
import requests
import json
import os
import time
from datetime import datetime, timedelta
from flask import Flask, request, render_template, jsonify
import threading
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# ====== CONFIGURATION =======
UNIFI_HOST = "https://protecthostaddress"  # Your Protect host
UNIFI_USERNAME = "superadminusername"  # Add your username here
UNIFI_PASSWORD = "superadminpassword"  # Add your password here
API_KEY = "protectapikey"  # Your API key
# Camera names and IDs
CAMERA_1_NAME = "streetentrancecameraname"
CAMERA_2_NAME = "streetexitcameraname"
CAMERA_1_ID = "entrancecameraid"  # If you know the camera ID, enter it here
CAMERA_2_ID = "exitcameraid"  # If you know the camera ID, enter it here
DISTANCE_FEET = 0.00  # MEASURE your cameras distance with something like iOS Measure and then use that distance converted to feet (required for accurate speeds).
VEHICLE_LENGTH = 15  # Average vehicle length in feet (can be adjusted).
SPEED_MULTIPLIER = 16.0 # averages out speeds, DO NOT mess with this.
VERIFY_SSL = False
DEFAULT_HOURS_BACK = 24
WEB_PORT = 8081
DEBUG = True
app = Flask(__name__)
session = requests.Session()
speed_results = []
camera_ids = {}
auth_cookies = {}
last_update_time = None
debug_logs = []
def debug_print(message):
    global debug_logs
    if DEBUG:
        print(f"[DEBUG] {message}")
        timestamp = datetime.now().strftime('%H:%M:%S')
        debug_logs.append(f"[{timestamp}] {message}")
        if len(debug_logs) > 1000:
            debug_logs = debug_logs[-1000:]
def authenticate_with_protect():
    global auth_cookies
    debug_print("Trying API key authentication")
    session.headers.clear()
    session.headers.update({
        'X-API-KEY': API_KEY,
        'Accept': 'application/json'
    })
    bootstrap_url = f"{UNIFI_HOST}/proxy/protect/api/bootstrap"
    try:
        response = session.get(bootstrap_url, verify=VERIFY_SSL)
        debug_print(f"API key auth response: {response.status_code}")

        if response.status_code == 200:
            try:
                data = response.json()
                debug_print("API key authentication successful")
                return True
            except:
                debug_print("Response is not valid JSON")
    except Exception as e:
        debug_print(f"Error with API key auth: {str(e)}")
    if UNIFI_USERNAME and UNIFI_PASSWORD:
        debug_print("Trying username/password authentication")
        login_endpoints = [
            "/api/auth/login",
            "/proxy/network/api/login",
            "/api/login",
            "/api/auth"
        ]
        for endpoint in login_endpoints:
            login_url = f"{UNIFI_HOST}{endpoint}"
            debug_print(f"Trying login endpoint: {login_url}")
            payload = {
                "username": UNIFI_USERNAME,
                "password": UNIFI_PASSWORD,
                "remember": True
            }
            session.headers.clear()
            session.cookies.clear()
            try:
                response = session.post(login_url, json=payload, verify=VERIFY_SSL)
                debug_print(f"Login response: {response.status_code}")
                if response.status_code in [200, 201, 204]:
                    auth_cookies = dict(session.cookies)
                    debug_print(f"Cookies received: {list(auth_cookies.keys())}")
                    bootstrap_url = f"{UNIFI_HOST}/proxy/protect/api/bootstrap"
                    try:
                        bootstrap_response = session.get(bootstrap_url, verify=VERIFY_SSL)
                        debug_print(f"Bootstrap response: {bootstrap_response.status_code}")
                        if bootstrap_response.status_code == 200:
                            try:
                                data = bootstrap_response.json()
                                debug_print("Username/password authentication successful")
                                return True
                            except:
                                debug_print("Bootstrap response is not valid JSON")
                    except Exception as e:
                        debug_print(f"Error with bootstrap: {str(e)}")
            except Exception as e:
                debug_print(f"Error with login: {str(e)}")
    debug_print("Trying token authentication with API key")
    token_url = f"{UNIFI_HOST}/proxy/protect/api/auth/access-key"
    session.headers.clear()
    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    payload = {
        "token": API_KEY
    }
    try:
        response = session.post(token_url, json=payload, verify=VERIFY_SSL)
        debug_print(f"Token auth response: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                if "accessToken" in data:
                    token = data["accessToken"]
                    session.headers.update({
                        'Authorization': f'Bearer {token}'
                    })
                    debug_print("Token authentication successful")
                    return True
            except:
                debug_print("Response is not valid JSON")
    except Exception as e:
        debug_print(f"Error with token auth: {str(e)}")
    debug_print("All authentication methods failed")
    return False
def get_camera_ids_from_protect():
    if CAMERA_1_ID and CAMERA_2_ID:
        debug_print("Using manually configured camera IDs")
        return {
            "cam1": CAMERA_1_ID,
            "cam2": CAMERA_2_ID
        }
    if not authenticate_with_protect():
        debug_print("Authentication failed, cannot get camera IDs")
        return None
    bootstrap_url = f"{UNIFI_HOST}/proxy/protect/api/bootstrap"
    debug_print(f"Getting cameras from: {bootstrap_url}")
    try:
        response = session.get(bootstrap_url, verify=VERIFY_SSL)
        debug_print(f"Bootstrap response: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                if "cameras" in data:
                    cameras = data["cameras"]
                    debug_print(f"Found {len(cameras)} cameras")
                    for camera in cameras:
                        name = camera.get("name", "Unknown")
                        camera_id = camera.get("id", "Unknown")
                        model = camera.get("type", "Unknown")
                        debug_print(f"Camera: {name}, ID: {camera_id}, Model: {model}")
                    cam_ids = {}
                    for camera in cameras:
                        name = camera.get("name", "")
                        camera_id = camera.get("id", "")

                        if name == CAMERA_1_NAME:
                            cam_ids["cam1"] = camera_id
                            debug_print(f"Matched Camera 1: {name}, ID: {camera_id}")
                        elif name == CAMERA_2_NAME:
                            cam_ids["cam2"] = camera_id
                            debug_print(f"Matched Camera 2: {name}, ID: {camera_id}")
                    if "cam1" in cam_ids and "cam2" in cam_ids:
                        debug_print("Found both cameras")
                        return cam_ids
                    else:
                        debug_print("Could not find both cameras by exact name, trying partial match")
                        for camera in cameras:
                            name = camera.get("name", "")
                            camera_id = camera.get("id", "")
                            if "cam1" not in cam_ids and CAMERA_1_NAME.lower() in name.lower():
                                cam_ids["cam1"] = camera_id
                                debug_print(f"Matched Camera 1 by partial name: {name}, ID: {camera_id}")
                            elif "cam2" not in cam_ids and CAMERA_2_NAME.lower() in name.lower():
                                cam_ids["cam2"] = camera_id
                                debug_print(f"Matched Camera 2 by partial name: {name}, ID: {camera_id}")
                        if "cam1" in cam_ids and "cam2" in cam_ids:
                            debug_print("Found both cameras after partial matching")
                            return cam_ids
                else:
                    debug_print("No cameras found in response")
            except Exception as e:
                debug_print(f"Error parsing bootstrap response: {str(e)}")
        else:
            debug_print(f"Bootstrap request failed: {response.status_code}")
    except Exception as e:
        debug_print(f"Error getting bootstrap data: {str(e)}")

    debug_print("Failed to get camera IDs")
    return None
def get_motion_events(cam_id, hours_back=1):
    if not cam_id:
        debug_print("Invalid camera ID")
        return []
    if not authenticate_with_protect():
        debug_print("Authentication failed, cannot get events")
        return []
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours_back)
    start_timestamp = int(start_time.timestamp() * 1000)
    end_timestamp = int(end_time.timestamp() * 1000)
    events_url = f"{UNIFI_HOST}/proxy/protect/api/events"
    params = {
        "start": start_timestamp,
        "end": end_timestamp,
        "cameras": [cam_id],
        "limit": 500
    }
    debug_print(f"Getting all events for camera {cam_id}")
    try:
        response = session.get(events_url, params=params, verify=VERIFY_SSL)
        debug_print(f"Events response: {response.status_code}")
        if response.status_code == 200:
            try:
                all_events = response.json()
                if isinstance(all_events, list) and all_events:
                    has_start = "start" in all_events[0]
                    has_end = "end" in all_events[0]
                    has_last_seen = "lastSeen" in all_events[0]
                    debug_print(f"Events have start: {has_start}, end: {has_end}, lastSeen: {has_last_seen}")
                    filtered_events = [event for event in all_events if
                                       event.get("type") in ["motion", "smartDetectZone"] and
                                       "start" in event and
                                       ("end" in event or "lastSeen" in event)]
                    debug_print(f"Found {len(filtered_events)} usable events out of {len(all_events)} total")
                    return filtered_events
                debug_print(f"No events found or unexpected format")
                return []
            except Exception as e:
                debug_print(f"Error parsing events: {str(e)}")
    except Exception as e:
        debug_print(f"Error getting events: {str(e)}")
    debug_print("Failed to get events")
    return []
def calculate_speed_from_detection_duration(event, vehicle_length=VEHICLE_LENGTH, multiplier=SPEED_MULTIPLIER):
    try:
        start_time = event["start"] / 1000  # Convert from ms to seconds
        end_time = None
        if "end" in event:
            end_time = event["end"] / 1000
        elif "lastSeen" in event:
            end_time = event["lastSeen"] / 1000

        if not end_time:
            debug_print("No end time found in event")
            return None
        duration = end_time - start_time
        if duration < 0.1 or duration > 30:
            debug_print(f"Event duration out of range: {duration:.2f}s")
            return None
        raw_speed = (vehicle_length / duration) * 0.681818
        adjusted_speed = raw_speed * multiplier
        debug_print(f"Duration: {duration:.2f}s, Raw: {raw_speed:.1f} mph, Adjusted: {adjusted_speed:.1f} mph")
        return round(adjusted_speed, 1)
    except Exception as e:
        debug_print(f"Error in speed calculation: {str(e)}")
        return None
def process_events(hours_back=DEFAULT_HOURS_BACK, vehicle_length=VEHICLE_LENGTH, speed_multiplier=SPEED_MULTIPLIER):
    global speed_results, camera_ids, last_update_time, debug_logs
    debug_print(f"Processing events from the past {hours_back} hours")
    debug_print(f"Using vehicle length: {vehicle_length}ft, speed multiplier: {speed_multiplier}")
    debug_logs = []
    camera_ids = get_camera_ids_from_protect()
    if not camera_ids or "cam1" not in camera_ids or "cam2" not in camera_ids:
        debug_print("Failed to get valid camera IDs")
        return []
    debug_print(f"Using camera IDs: cam1={camera_ids['cam1']}, cam2={camera_ids['cam2']}")
    cam1_events = get_motion_events(camera_ids["cam1"], hours_back)
    cam2_events = get_motion_events(camera_ids["cam2"], hours_back)
    debug_print(f"Found {len(cam1_events)} usable events for camera 1")
    debug_print(f"Found {len(cam2_events)} usable events for camera 2")
    results = []
    for camera_name, events in [
        (CAMERA_1_NAME, cam1_events),
        (CAMERA_2_NAME, cam2_events)
    ]:
        for event in events:
            speed = calculate_speed_from_detection_duration(event, vehicle_length, speed_multiplier)
            if speed is not None:
                timestamp = event["start"] / 1000
                end_time = event.get("end", event.get("lastSeen", 0)) / 1000
                duration = end_time - timestamp
                result = {
                    "camera": camera_name,
                    "camera_time": datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                    "speed_mph": speed,
                    "timestamp": int(timestamp),
                    "duration": round(duration, 2)
                }
                results.append(result)
                debug_print(f"Added result: {camera_name}, speed: {speed} mph, duration: {duration:.2f}s")
    results.sort(key=lambda x: x["timestamp"], reverse=True)
    debug_print(f"Total valid speed calculations: {len(results)}")
    speed_results = results
    last_update_time = datetime.now()
    return results
def create_html_template():
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    os.makedirs(template_dir, exist_ok=True)
    template_path = os.path.join(template_dir, "index.html")
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UniFi Protect Speed Monitor</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #2a3b4c;
            text-align: center;
        }
        .controls {
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .data-container {
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #2a3b4c;
            color: white;
            position: sticky;
            top: 0;
        }
        tr:hover {
            background-color: #f1f1f1;
        }
        .button {
            background-color: #4CAF50;
            border: none;
            color: white;
            padding: 10px 20px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 4px;
        }
        .info {
            margin-top: 20px;
            color: #666;
            font-size: 14px;
        }
        .loading {
            text-align: center;
            padding: 20px;
            font-style: italic;
            color: #666;
        }
        .error {
            color: #d9534f;
            font-weight: bold;
        }
        .stats {
            display: flex;
            justify-content: space-around;
            margin-bottom: 20px;
            text-align: center;
        }
        .stat-box {
            background-color: #fff;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            flex: 1;
            margin: 0 10px;
        }
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #2a3b4c;
        }
        .stat-label {
            color: #666;
        }
        .speed-low { color: green; }
        .speed-medium { color: orange; }
        .speed-high { color: red; }
        #debug {
            margin-top: 20px;
            padding: 10px;
            background-color: #f8f9fa;
            border: 1px solid #ddd;
            border-radius: 4px;
            max-height: 400px;
            overflow-y: auto;
            display: none;
        }
        .debug-toggle {
            color: #666;
            text-decoration: underline;
            cursor: pointer;
        }
        .config-panel {
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-top: 20px;
            display: none;
        }
        .config-toggle {
            color: #666;
            text-decoration: underline;
            cursor: pointer;
        }
        input[type="text"], input[type="number"], input[type="password"] {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 100%;
            margin-bottom: 10px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h1>UniFi Protect Speed Monitor</h1>
    <div class="controls">
        <label for="hours">Hours to look back:</label>
        <input type="number" id="hours" min="1" max="168" value="24">
        <button class="button" onclick="fetchData()">Update Data</button>
        <span id="status"></span>
    </div>
    <div class="stats" id="stats-container">
        <div class="stat-box">
            <div class="stat-value" id="total-events">-</div>
            <div class="stat-label">Total Events</div>
        </div>
        <div class="stat-box">
            <div class="stat-value" id="avg-speed">-</div>
            <div class="stat-label">Average Speed (mph)</div>
        </div>
        <div class="stat-box">
            <div class="stat-value" id="max-speed">-</div>
            <div class="stat-label">Max Speed (mph)</div>
        </div>
    </div>
    <div class="data-container">
        <table id="results-table">
            <thead>
                <tr>
                    <th>Date/Time</th>
                    <th>Camera</th>
                    <th>Speed (mph)</th>
                    <th>Duration (s)</th>
                </tr>
            </thead>
            <tbody id="results-body">
                <tr>
                    <td colspan="4" class="loading">Loading data...</td>
                </tr>
            </tbody>
        </table>
    </div>
    <div class="info">
        <p>Last updated: <span id="last-updated">Never</span></p>
        <p>Distance between cameras: <span id="distance">{{ distance }}</span> feet</p>
        <p>Vehicle length: <span id="vehicle-length-display">{{ vehicle_length }}</span> feet</p>
        <p>Speed multiplier: <span id="speed-multiplier-display">{{ speed_multiplier }}</span></p>
        <p>Cameras: <span id="camera1">{{ camera1 }}</span> and <span id="camera2">{{ camera2 }}</span></p>
        <p>
            <span class="debug-toggle" onclick="toggleDebug()">Show/Hide Debug Info</span> | 
            <span class="config-toggle" onclick="toggleConfig()">Show/Hide Configuration</span>
        </p>
    </div>
    <div id="debug">
        <h3>Debug Information</h3>
        <pre id="debug-content"></pre>
    </div>
    <div id="config" class="config-panel">
        <h3>Configuration</h3>
        <p>Enter your UniFi Protect credentials and camera IDs. These will be stored in your browser.</p>
        <div>
            <label for="username">Username:</label>
            <input type="text" id="username" placeholder="UniFi username">
        </div>
        <div>
            <label for="password">Password:</label>
            <input type="password" id="password" placeholder="UniFi password">
        </div>
        <div>
            <label for="cam1-id">Camera 1 ID:</label>
            <input type="text" id="cam1-id" placeholder="Enter Camera 1 ID">
        </div>
        <div>
            <label for="cam2-id">Camera 2 ID:</label>
            <input type="text" id="cam2-id" placeholder="Enter Camera 2 ID">
        </div>
        <div>
            <label for="distance-setting">Distance between cameras (feet):</label>
            <input type="number" id="distance-setting" min="0.1" step="0.1" value="{{ distance }}">
        </div>
        <div>
            <label for="vehicle-length">Average vehicle length (feet):</label>
            <input type="number" id="vehicle-length" min="1" value="{{ vehicle_length }}">
        </div>
        <div>
            <label for="speed-multiplier">Speed calibration multiplier:</label>
            <input type="number" id="speed-multiplier" min="0.1" step="0.1" value="{{ speed_multiplier }}">
        </div>
        <button class="button" onclick="saveConfig()">Save Configuration</button>
    </div>
    <script>
        function loadConfig() {
            const username = localStorage.getItem('username');
            const password = localStorage.getItem('password');
            const cam1Id = localStorage.getItem('cam1Id');
            const cam2Id = localStorage.getItem('cam2Id');
            const distance = localStorage.getItem('distance');
            const vehicleLength = localStorage.getItem('vehicleLength');
            const speedMultiplier = localStorage.getItem('speedMultiplier');
            if (username) document.getElementById('username').value = username;
            if (password) document.getElementById('password').value = password;
            if (cam1Id) document.getElementById('cam1-id').value = cam1Id;
            if (cam2Id) document.getElementById('cam2-id').value = cam2Id;
            if (distance) document.getElementById('distance-setting').value = distance;
            if (vehicleLength) document.getElementById('vehicle-length').value = vehicleLength;
            if (speedMultiplier) document.getElementById('speed-multiplier').value = speedMultiplier;
            if (distance) document.getElementById('distance').textContent = distance;
            if (vehicleLength) document.getElementById('vehicle-length-display').textContent = vehicleLength;
            if (speedMultiplier) document.getElementById('speed-multiplier-display').textContent = speedMultiplier;
        }
        function saveConfig() {
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const cam1Id = document.getElementById('cam1-id').value;
            const cam2Id = document.getElementById('cam2-id').value;
            const distance = document.getElementById('distance-setting').value;
            const vehicleLength = document.getElementById('vehicle-length').value;
            const speedMultiplier = document.getElementById('speed-multiplier').value;
            localStorage.setItem('username', username);
            localStorage.setItem('password', password);
            localStorage.setItem('cam1Id', cam1Id);
            localStorage.setItem('cam2Id', cam2Id);
            localStorage.setItem('distance', distance);
            localStorage.setItem('vehicleLength', vehicleLength);
            localStorage.setItem('speedMultiplier', speedMultiplier);
            document.getElementById('distance').textContent = distance;
            document.getElementById('vehicle-length-display').textContent = vehicleLength;
            document.getElementById('speed-multiplier-display').textContent = speedMultiplier;
            const statusEl = document.getElementById('status');
            statusEl.textContent = 'Configuration saved!';
            setTimeout(() => { statusEl.textContent = ''; }, 3000);
            fetchData();
        }
        function formatTimestamp(timestamp) {
            const date = new Date(timestamp * 1000);
            return date.toLocaleString();
        }
        function getSpeedClass(speed) {
            if (speed < 15) return 'speed-low'; // Below 15mph - green
            if (speed < 25) return 'speed-medium'; // 15-25mph - orange
            return 'speed-high'; // Above 25mph - red
        }
        function fetchData() {
            const hours = document.getElementById('hours').value;
            const statusEl = document.getElementById('status');
            const debugEl = document.getElementById('debug-content');
            const username = localStorage.getItem('username');
            const password = localStorage.getItem('password');
            const cam1Id = localStorage.getItem('cam1Id');
            const cam2Id = localStorage.getItem('cam2Id');
            const distance = localStorage.getItem('distance');
            const vehicleLength = localStorage.getItem('vehicleLength');
            const speedMultiplier = localStorage.getItem('speedMultiplier');
            let url = '/api/speeds?hours=' + hours;
            let params = [];
            if (username && password) {
                params.push(`username=${encodeURIComponent(username)}`);
                params.push(`password=${encodeURIComponent(password)}`);
            }
            if (cam1Id && cam2Id) {
                params.push(`cam1=${encodeURIComponent(cam1Id)}`);
                params.push(`cam2=${encodeURIComponent(cam2Id)}`);
            }
            if (distance) {
                params.push(`distance=${encodeURIComponent(distance)}`);
            }
            if (vehicleLength) {
                params.push(`vehicleLength=${encodeURIComponent(vehicleLength)}`);
            }
            if (speedMultiplier) {
                params.push(`speedMultiplier=${encodeURIComponent(speedMultiplier)}`);
            }
            if (params.length > 0) {
                url += '&' + params.join('&');
            }
            statusEl.textContent = 'Updating...';
            document.getElementById('results-body').innerHTML = '<tr><td colspan="4" class="loading">Loading data...</td></tr>';
            fetch(url)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    displayResults(data);
                    statusEl.textContent = 'Updated successfully!';
                    setTimeout(() => { statusEl.textContent = ''; }, 3000);
                    if (data.debug) {
                        debugEl.textContent = data.debug.join('\\n');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    statusEl.textContent = 'Error updating data';
                    statusEl.classList.add('error');
                });
        }
        function displayResults(data) {
            const tbody = document.getElementById('results-body');
            const lastUpdatedEl = document.getElementById('last-updated');
            const totalEventsEl = document.getElementById('total-events');
            const avgSpeedEl = document.getElementById('avg-speed');
            const maxSpeedEl = document.getElementById('max-speed');
            totalEventsEl.textContent = data.results.length;
            if (data.results.length > 0) {
                const speeds = data.results.map(r => r.speed_mph);
                const avgSpeed = speeds.reduce((a, b) => a + b, 0) / speeds.length;
                const maxSpeed = Math.max(...speeds);
                avgSpeedEl.textContent = avgSpeed.toFixed(1);
                maxSpeedEl.textContent = maxSpeed;
            } else {
                avgSpeedEl.textContent = '-';
                maxSpeedEl.textContent = '-';
            }
            if (data.last_update) {
                lastUpdatedEl.textContent = new Date(data.last_update).toLocaleString();
            }
            tbody.innerHTML = '';
            if (data.results.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="loading">No events found</td></tr>';
                return;
            }
            data.results.forEach(result => {
                const row = document.createElement('tr');
                const timeCell = document.createElement('td');
                timeCell.textContent = formatTimestamp(result.timestamp);
                const cameraCell = document.createElement('td');
                cameraCell.textContent = result.camera;
                const speedCell = document.createElement('td');
                speedCell.textContent = result.speed_mph + " MPH";
                speedCell.className = getSpeedClass(result.speed_mph);
                const durationCell = document.createElement('td');
                durationCell.textContent = result.duration + 's';
                row.appendChild(timeCell);
                row.appendChild(cameraCell);
                row.appendChild(speedCell);
                row.appendChild(durationCell);
                tbody.appendChild(row);
            });
        }
        function toggleDebug() {
            const debugEl = document.getElementById('debug');
            debugEl.style.display = debugEl.style.display === 'none' ? 'block' : 'none';
        }
        function toggleConfig() {
            const configEl = document.getElementById('config');
            configEl.style.display = configEl.style.display === 'none' ? 'block' : 'none';
        }
        window.onload = function() {
            loadConfig();
            fetchData();
        };
    </script>
</body>
</html>
    """
    with open(template_path, "w") as f:
        f.write(html_content)
    return template_path
@app.route('/')
def index():
    return render_template('index.html',
                           distance=DISTANCE_FEET,
                           camera1=CAMERA_1_NAME,
                           camera2=CAMERA_2_NAME,
                           vehicle_length=VEHICLE_LENGTH,
                           speed_multiplier=SPEED_MULTIPLIER)
@app.route('/api/speeds')
def get_speeds():
    global speed_results, last_update_time, debug_logs, UNIFI_USERNAME, UNIFI_PASSWORD, CAMERA_1_ID, CAMERA_2_ID
    try:
        hours = int(request.args.get('hours', DEFAULT_HOURS_BACK))
    except ValueError:
        hours = DEFAULT_HOURS_BACK
    username = request.args.get('username')
    password = request.args.get('password')
    if username and password:
        UNIFI_USERNAME = username
        UNIFI_PASSWORD = password
        debug_print(f"Using credentials from request: {username[:2]}***")
    cam1_id = request.args.get('cam1')
    cam2_id = request.args.get('cam2')
    if cam1_id and cam2_id:
        CAMERA_1_ID = cam1_id
        CAMERA_2_ID = cam2_id
        debug_print(f"Using camera IDs from request: {cam1_id}, {cam2_id}")
    try:
        vehicle_length = float(request.args.get('vehicleLength', VEHICLE_LENGTH))
    except ValueError:
        vehicle_length = VEHICLE_LENGTH
    try:
        speed_multiplier = float(request.args.get('speedMultiplier', SPEED_MULTIPLIER))
    except ValueError:
        speed_multiplier = SPEED_MULTIPLIER
    results = process_events(hours, vehicle_length, speed_multiplier)
    return jsonify({
        'results': speed_results,
        'last_update': last_update_time.isoformat() if last_update_time else None,
        'debug': debug_logs
    })
def run_web_server():
    create_html_template()
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False)
def main():
    print("[+] Starting UniFi Protect Speed Monitor")
    print("[+] Web interface will be available at http://localhost:8081")
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[+] Shutting down...")
if __name__ == "__main__":
    main()
# Copyright ©️ Project Teal Lvbs. License Applies