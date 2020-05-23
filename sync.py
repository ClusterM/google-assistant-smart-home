#!/usr/bin/python3

import requests
import json
import os
import config

users = os.listdir(config.USERS_DIRECTORY)
for user_file in users:
    user = user_file.replace(".json", "")
    print("User:", user, "... ", end="", flush=True)
    payload = {"agentUserId": user}
    url = "https://homegraph.googleapis.com/v1/devices:requestSync?key=" + config.API_KEY
    r = requests.post(url, data=json.dumps(payload))
    if r.text.strip() == "{}":
        print("OK")
    else:
        print("ERROR")
        print(r.text)
