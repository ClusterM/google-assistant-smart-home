# coding: utf8

import config
from flask import Flask
from flask import request
from flask import render_template
from flask import send_from_directory
from flask import redirect
from flask import jsonify
import sys
import os
import requests
import urllib
import json
import random
import string
from time import time
import importlib
import logging

# Enable log if need

if hasattr(config, 'LOG_FILE'):
    logging.basicConfig(level=config.LOG_LEVEL,
                    format=config.LOG_FORMAT,
                    datefmt=config.LOG_DATE_FORMAT,
                    filename=config.LOG_FILE,
                    filemode='a')
logger = logging.getLogger()

# Path to device plugins
sys.path.insert(0, config.DEVICES_DIRECTORY)

last_code = None
last_code_user = None
last_code_time = None

app = Flask(__name__)

logger.info("Started.", extra={'remote_addr': '-', 'user': '-'})

# Function to load user info
def get_user(username):
    filename = os.path.join(config.USERS_DIRECTORY, username + ".json")
    if os.path.isfile(filename) and os.access(filename, os.R_OK):
        with open(filename, mode='r') as f:
            text = f.read()
            data = json.loads(text)
            return data
    else:
        logger.warning("user not found", extra={'remote_addr': request.remote_addr, 'user': username})
        return None

# Function to retrieve token from header
def get_token():
    auth = request.headers.get('Authorization')
    parts = auth.split(' ', 2)
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        return parts[1]
    else:
        logger.warning("invalid token: %s", auth, extra={'remote_addr': request.remote_addr, 'user': '-'})
        return None

# Function to check current token, returns username
def check_token():
    access_token = get_token()
    access_token_file = os.path.join(config.TOKENS_DIRECTORY, access_token)
    if os.path.isfile(access_token_file) and os.access(access_token_file, os.R_OK):
        with open(access_token_file, mode='r') as f:
            return f.read()
    else:
        return None

# Function to load device info
def get_device(device_id):
    filename = os.path.join(config.DEVICES_DIRECTORY, device_id + ".json")
    if os.path.isfile(filename) and os.access(filename, os.R_OK):
        with open(filename, mode='r') as f:
            text = f.read()
            data = json.loads(text)
            data['id'] = device_id
            return data
    else:
        return None

# Random string generator
def random_string(stringLength=8):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for i in range(stringLength))

@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('css', path)

# OAuth entry point
@app.route('/auth/', methods=['GET', 'POST'])
def auth():
    global last_code, last_code_user, last_code_time
    if request.method == 'GET':
        # Ask user for login and password
        return render_template('login.html')
    elif request.method == 'POST':
        if ("username" not in request.form
            or "password" not in request.form
            or "state" not in request.args
            or "response_type" not in request.args
            or request.args["response_type"] != "code"
            or "client_id" not in request.args
            or request.args["client_id"] != config.CLIENT_ID):
                logger.warning("invalid auth request", extra={'remote_addr': request.remote_addr, 'user': request.form['username']})
                return "Invalid request", 400
        # Check login and password
        user = get_user(request.form["username"])
        if user == None or user["password"] != request.form["password"]:
            logger.warning("invalid password", extra={'remote_addr': request.remote_addr, 'user': request.form['username']})
            return render_template('login.html', login_failed=True)

        # Generate random code and remember this user and time
        last_code = random_string(8)
        last_code_user = request.form["username"]
        last_code_time = time()

        params = {'state': request.args['state'], 
                  'code': last_code,
                  'client_id': config.CLIENT_ID}
        logger.info("generated code", extra={'remote_addr': request.remote_addr, 'user': request.form['username']})
        return redirect(request.args["redirect_uri"] + '?' + urllib.parse.urlencode(params))

# OAuth, token request
@app.route('/token/', methods=['POST'])
def token():
    global last_code, last_code_user, last_code_time
    if ("client_secret" not in request.form
        or request.form["client_secret"] != config.CLIENT_SECRET
        or "client_id" not in request.form
        or request.form["client_id"] != config.CLIENT_ID
        or "code" not in request.form):
            logger.warning("invalid token request", extra={'remote_addr': request.remote_addr, 'user': last_code_user})
            return "Invalid request", 400
    # Check code
    if request.form["code"] != last_code:
        logger.warning("invalid code", extra={'remote_addr': request.remote_addr, 'user': last_code_user})
        return "Invalid code", 403
    # Check time
    if  time() - last_code_time > 10:
        logger.warning("code is too old", extra={'remote_addr': request.remote_addr, 'user': last_code_user})
        return "Code is too old", 403
    # Generate and save random token with username
    access_token = random_string(32)
    access_token_file = os.path.join(config.TOKENS_DIRECTORY, access_token)
    with open(access_token_file, mode='wb') as f:
        f.write(last_code_user.encode('utf-8'))
    logger.info("access granted", extra={'remote_addr': request.remote_addr, 'user': last_code_user})
    # Return just token without any expiration time
    return jsonify({'access_token': access_token})

# Main URL to interact with Google requests
@app.route('/', methods=['GET', 'POST'])
def fulfillment():
    # Google will send POST requests only, some it's just placeholder for GET
    if request.method == 'GET': return "Your smart home is ready."

    # Check token and get username
    user_id = check_token()
    if user_id == None:
        return "Access denied", 403
    r = request.get_json()
    logger.debug("request: \r\n%s", json.dumps(r, indent=4), extra={'remote_addr': request.remote_addr, 'user': user_id})

    result = {}
    result['requestId'] = r['requestId']

    # Let's check inputs array. Why it's array? Is it possible that it will contain multiple objects? I don't know.
    inputs = r['inputs']
    for i in inputs:
        intent = i['intent']
        # Sync intent, need to response with devices list
        if intent == "action.devices.SYNC":
            result['payload'] = {"agentUserId": user_id, "devices": []}
            # Loading user info
            user = get_user(user_id)
            # Loading each device available for this user
            for device_id in user['devices']:
                # Loading device info
                device = get_device(device_id)
                result['payload']['devices'].append(device)

        # Query intent, need to response with current device status
        if intent == "action.devices.QUERY":
            result['payload'] = {}
            result['payload']['devices'] = {}
            for device in i['payload']['devices']:
                device_id = device['id']
                custom_data = device.get("customData", None)
                # Load module for this device
                device_module = importlib.import_module(device_id)
                # Call query method for this device
                query_method = getattr(device_module, device_id + "_query")
                result['payload']['devices'][device_id] = query_method(custom_data)

        # Execute intent, need to execute some action
        if intent == "action.devices.EXECUTE":
            result['payload'] = {}
            result['payload']['commands'] = []
            for command in i['payload']['commands']:
                for device in command['devices']:
                    device_id = device['id']
                    custom_data = device.get("customData", None)
                    # Load module for this device
                    device_module = importlib.import_module(device_id)
                    # Call execute method for this device for every execute command
                    action_method = getattr(device_module, device_id + "_action")
                    for e in command['execution']:
                        command = e['command']
                        params = e.get("params", None)
                        action_result = action_method(custom_data, command, params)
                        action_result['ids'] = [device_id]
                        result['payload']['commands'].append(action_result)
        
        # Disconnect intent, need to revoke token
        if intent == "action.devices.DISCONNECT":
            access_token = get_token()
            access_token_file = os.path.join(config.TOKENS_DIRECTORY, access_token)
            if os.path.isfile(access_token_file) and os.access(access_token_file, os.R_OK):
                os.remove(access_token_file)
                logger.debug("token %s revoked", access_token, extra={'remote_addr': request.remote_addr, 'user': user_id})
            return {}    

    logger.debug("response: \r\n%s", json.dumps(result, indent=4), extra={'remote_addr': request.remote_addr, 'user': user_id})
    return jsonify(result)
