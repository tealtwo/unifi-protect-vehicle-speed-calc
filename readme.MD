# UniFi Protect Speed Monitor

A simple tool to calculate vehicle speeds using motion detection events from UniFi Protect cameras. Perfect for monitoring traffic patterns on your street without expensive specialized equipment.

![UniFi Protect Speed Monitor](https://i.ibb.co/20y00tDS/image.png)

## What is this?

I built this tool to monitor traffic speeds on my street using my existing Ubiquiti UniFi Protect cameras. Instead of buying expensive speed monitoring equipment, this app uses the smart AI detection capabilities of UniFi Protect cameras to calculate vehicle speeds based on how long vehicles appear in each camera's field of view (per frame).

The algorithm uses the known length of average vehicles combined with the time they're visible to estimate speed.

## Getting Started

### Docker (Recommended)

The easiest way to run this app is with Docker:

```bash
# Build the Docker image
docker build -t unifi-speed-monitor .

# Run the container
docker run -d -p 8081:8081 --restart unless-stopped --name speed-monitor unifi-speed-monitor
```

The app will be available at http://localhost:8081 or http://yourlocalip:8081

### Manual Installation

1. Clone this repo
2. Install requirements: `pip install -r requirements.txt`
3. Edit the configuration variables in `app.py`
4. Run it: `python app.py`

## Configuration

All configuration is done directly in the `app.py` file. Edit these variables:

```python
# ====== CONFIGURATION =======
UNIFI_HOST = "https://protecthostaddress"  # Your Protect host
UNIFI_USERNAME = "superadminusername"  # Add your username here (user must be local AND superadmin)
UNIFI_PASSWORD = "superadminpassword"  # Add your password here
API_KEY = "protectapikey"  # Your UniFi Protect API key
# Camera names and IDs
CAMERA_1_NAME = "streetentrancecameraname" # Street Entrance Camera name in UniFi Protect
CAMERA_2_NAME = "streetexitcameraname" # Street Exit Camera name in UniFi Protect
CAMERA_1_ID = "entrancecameraid"  # If you know the camera ID, enter it here
CAMERA_2_ID = "exitcameraid"  # If you know the camera ID, enter it here
DISTANCE_FEET = 0.00  # MEASURE your cameras distance with something like iOS Measure and then use that distance converted to feet (required for accurate speeds).
# ============================
```

The most important settings to get right:

- **Distance Between Cameras**: Distance between the lense of your two camera, the distance must be measured horizontally using something like iOS Measure, or an Android Equivalent, alternative methods may be used as well.

## How to Use

1. Access the web interface at http://localhost:8081
2. The dashboard displays estimated vehicle speeds from your cameras
3. Use the "Hours to look back" selector to choose how far back to analyze speeds

## Features

- 🚗 Calculates vehicle speeds based on UniFi Protect motion events
- 📊 Visual dashboard with speed statistics
- 🔄 Adjustable calibration
- 🔧 Easily Configurable
- 🐳 Easy Docker deployment

## Limitations

- Works best with cameras that have a clear view of the street
- Accuracy depends on camera placement and calibration
- Not intended for law enforcement or official speed measurements

## Troubleshooting

- **No events detected**: Make sure motion detection is enabled in UniFi Protect
- **Speeds seem wrong**: Adjust the speed multiplier in the configuration
- **Connection issues**: Verify your UniFi credentials and network connectivity
- **API errors**: Make sure your API key has the right permissions

## License

This project is licensed under the [Teal Lvbs License](https://github.com/tealtwo/license).

Copyright ©️ Project Teal Lvbs