# google-assistant-smart-home
Simple Python framework to control your DIY smart home devices using Google Assistant

## Requirements
* Web server (you can use some single-board computer like Raspberry Pi)
* Domain name
* SSL certificate for HTTPS (you can use free certificate from Let's Entrypt)
* This project is based on Flask, so you need Python 3.x.x and Flask to be installed

## How to install
* Checkout project somewhere on your server
* Edit __google_home.wsgi__ and change path to project directory
* Deploy project to your web server using WSGI, don't forget to allow authorization header
* Go to https://console.actions.google.com/ and create new project, select "smart home" type
* Open "Develop"->"Invocation" and type name of your project
* Open "Develop"->"Actions" and type fulfillment URL: https://_your-domain-name_/
* Open "Develop"->"Account linking" and type

Client ID: some ID, just remember it for now

Client secret: some password, remember it too and keep it secret

Authorization URL: https://_your-domain-name_/auth/

Token URL: https://_your-domain-name_/token/

* Open https://console.cloud.google.com -> "APIs & Services" -> "ENABLE APIS AND SERVICES" -> "HomeGraph API" -> "Manage" -> "Credentials" -> "Credentials in APIs & Services" -> "CREATE CREDENTIALS" -> "API Key", store it somewhere
* Edit __config.py__ and fill __CLIENT_ID__, __CLIENT_SECRET__ and __API_KEY__ with your credentials, also change __USERS_DIRECTORY__, __TOKENS_DIRECTORY__, and __DEVICES_DIRECTORY__ to your __users__, __tokens__ and __devices__ paths
* It's recommended to __chmod go-rwx tokens users__

## How to use
* Create file _username_.json in __users__ directory and write json config for user with password and list of available devices:
```json
{
    "password": "test",
    "devices": [
        "pc"
    ]
}
```

* Create file _device-name_.json in __devices__ directory and write json config for device using Google guides: https://developers.google.com/assistant/smarthome/concepts/devices-traits

Example for simple on-off device:
```json
{
    "type": "action.devices.types.SWITCH",
    "traits": [
        "action.devices.traits.OnOff"
    ],
    "name": {
        "name": "PC",
        "defaultNames": [
          "PC",
          "Computer"
        ],
        "nicknames": [
          "PC",
          "Computer"
        ]
    },
    "willReportState": false,
    "roomHint": "My room",
    "deviceInfo": {
        "manufacturer": "Cluster",
        "model": "1",
        "hwVersion": "1",
        "swVersion": "1"
    }
}
```
* Create file _device-name_.py in __devices__ directory and write python script with two methods: *device-name*_query(custom_data) and *device-name*_command(custom_data, command, params)

Example script to turn on/off PC:
```python
import subprocess

def pc_query(custom_data):
    p = subprocess.run(["ping", "-c", "1", "192.168.0.2"], stdout=subprocess.PIPE)
    state = p.returncode == 0
    return {"on": state, "online": True}

def pc_action(custom_data, command, params):
    if command == "action.devices.commands.OnOff":
        if params['on']:
            subprocess.run(["wakeonlan", "-i", "192.168.0.255", "00:11:22:33:44:55"])
        else:
            subprocess.run(["sh", "-c", "echo shutdown -h | ssh clust@192.168.0.2"])
        return {"status": "SUCCESS", "states": {"on": params['on'], "online": True}}
    else:
        return {"status": "ERROR"}

```
Query fuction must return device status object, and action function must return action result. Please read traits documentation for more info: https://developers.google.com/assistant/smarthome/traits.

* Open Google Home app on your phone and link it with your project
* Done! You can control your devices using voice commands or Google Home app
* Run __sync.py__ script when you need to update devices list
