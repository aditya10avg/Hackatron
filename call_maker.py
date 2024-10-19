import os
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
TWIML_URL = 'https://c3f3-14-139-240-252.ngrok-free.app/outbound-call'
WAIT_TIME = 10  # Time to wait between calls

app = FastAPI()

# Twilio Client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Function to make a call
def make_call(to_number):
    try:
        call = twilio_client.calls.create(
            to=to_number,
            from_=TWILIO_PHONE_NUMBER,
            url=TWIML_URL,
            status_callback='https://your-callback-url.com/status',  # This URL should point to your callback handler
            status_callback_event=['completed', 'failed', 'no-answer', 'busy'],
            status_callback_method='POST'
        )
        print(f"Initiated call to {to_number}, Call SID: {call.sid}")
        return call.sid
        
    except TwilioRestException as e:
        print(f"Error making call to {to_number}: {str(e)}")
        return None

# Function to update call status (you can enhance this to update Google Sheets or a database)
def update_call_status(phone_number, status):
    print(f"Updated status for {phone_number}: {status}")

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        phone_numbers = data.get("phone_numbers", [])
        
        for phone_number in phone_numbers:
            print(f"Processing phone number: {phone_number}")
            call_sid = make_call(phone_number)
            
            if call_sid:
                print(f"Call initiated successfully to {phone_number}. Call SID: {call_sid}")

                # Wait for the call to complete or fail
                while True:
                    call = twilio_client.calls(call_sid).fetch()
                    status = call.status

                    # Update status based on the call result
                    update_call_status(phone_number, status)

                    if status in ['completed', 'failed', 'no-answer', 'busy']:
                        break
                    
                    # Wait before checking the status again
                    time.sleep(5)  # Check every 5 seconds
                
            else:
                print(f"Failed to initiate call to {phone_number}")
            
            # Wait for the specified time before the next call
            print(f"Waiting {WAIT_TIME} seconds before the next call...")
            time.sleep(WAIT_TIME)

        return JSONResponse(content={"message": "Calls initiated."}, status_code=200)
    
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid request data")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
