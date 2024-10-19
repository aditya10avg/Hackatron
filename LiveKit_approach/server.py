from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

app = FastAPI()

# The webhook URL where Twilio will request TwiML instructions
@app.api_route("/twiml", methods=["GET", "POST"], response_class=PlainTextResponse)
async def twiml_response(request: Request):
    print(f"Request method: {request.method}")
    print(f"Request URL: {request.url}")
    print("Twilio has accessed the /twiml endpoint.")
    twiml = """
    <Response>
        <Start>
            <Stream url="wss://calley-4x9pig7s.livekit.cloud" /> 
        </Start>
    </Response>
    """
    return twiml

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
