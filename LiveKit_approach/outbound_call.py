import os
from twilio.rest import Client

# Twilio credentials 
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')  

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def make_outbound_call(to_phone_number: str, twiml_url: str):
    """Make an outbound call using Twilio API and direct it to a TwiML URL."""
    
    call = client.calls.create(
        url=twiml_url,         # The URL returning TwiML instructions
        to=to_phone_number,    # The recipient's phone number, here we will use the logic of cold calling using spreadsheets.
        from_=TWILIO_PHONE_NUMBER  
    return call.sid
