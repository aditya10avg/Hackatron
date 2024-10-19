import os
import requests
import threading
from flask import Flask, request, jsonify
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

app = Flask(__name__)

# Set up Twilio credentials from environment variables
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')

# Initialize Twilio client
twilio_client = Client(account_sid, auth_token)

call_status_map = {}  # To store the status of ongoing calls

# Route 1: Webhook to start calls, triggered by Make.com
@app.route('/start_call', methods=['POST'])
def start_call():
    """Webhook to start the call from Make.com Route 1."""
    data = request.json
    to_number = data.get('phone_number')
    row_number = data.get('row')  # Row number for updating the sheet via Make.com

    if to_number:
        call_sid = make_call(to_number, row_number)
        if call_sid:
            return jsonify({"status": "Call initiated", "call_sid": call_sid}), 200
        else:
            return jsonify({"status": "Failed to initiate call"}), 500
    return jsonify({"status": "Invalid request"}), 400

def make_call(to_number, row_number):
    """Make a call using Twilio to the specified number."""
    try:
        call = twilio_client.calls.create(
            to=to_number,
            from_=twilio_phone_number,
            url="http://demo.twilio.com/docs/voice.xml",  # Replace with your TwiML URL
            status_callback=f'http://your-server-domain/twilio_status_callback?row={row_number}',  # Callback with row info
            status_callback_method='POST'
        )
        print(f"Call initiated to {to_number}. Call SID: {call.sid}")
        call_status_map[call.sid] = {'to': to_number, 'row': row_number, 'status': 'initiated'}
        return call.sid
    except TwilioRestException as e:
        print(f"Error making call to {to_number}: {str(e)}")
        return None

# Route 2: Webhook to receive status updates from Twilio
@app.route('/twilio_status_callback', methods=['POST'])
def twilio_status_callback():
    """Twilio status callback route for Make.com Route 2."""
    call_sid = request.form.get('CallSid')
    call_status = request.form.get('CallStatus')
    row_number = request.args.get('row')  # Pass the row number through the webhook

    # Log status
    print(f"Call {call_sid} status: {call_status}")

    # Forward the status to Make.com using its webhook
    make_webhook_url = "https://hook.us2.make.com/yc1rmnaqz8dxdeadgifdkagh4pfejtsk"
    payload = {
        'row': row_number,
        'call_sid': call_sid,
        'call_status': call_status
    }
    requests.post(make_webhook_url, json=payload)

    return 'OK', 200

# Flask server to handle webhooks
def run_flask_server():
    app.run(debug=False, use_reloader=False)

if __name__ == '__main__':
    # Start Flask app in a new thread to handle webhooks
    threading.Thread(target=run_flask_server).start()
