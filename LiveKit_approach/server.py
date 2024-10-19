from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()

# The webhook URL where Twilio will request TwiML instructions
@app.get("/twiml", response_class=PlainTextResponse)
async def twiml_response():
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
    # Run the server on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
