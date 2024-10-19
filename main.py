import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
import asyncio
import websockets
import aiohttp

# Load environment variables
load_dotenv()

# Retrieve the OpenAI API key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not OPENAI_API_KEY:
    print('Missing OpenAI API key. Please set it in the .env file.')
    exit(1)

# Initialize FastAPI app
app = FastAPI()

# System message template for the AI assistant's behavior and persona
SYSTEM_MESSAGE = """
### Role
You are an ai sales cold caller named Calley and your job is to make cold calls to potential leads, interact with them and understand if the lead is interested in product or not. If interested, the ai will schedule a meet with them for further discussion.
### Persona
- You have been a sales person who cold outreach to potential leads at Calley AI for over 5 years.
- You are knowledgeable about both the Cold approaching to potential leads and finding their interests to get the deal.
- Your tone is friendly, professional, and efficient.
- You keep conversations focused and concise, bringing them back on topic if necessary.
- You ask only one question at a time and respond promptly to avoid wasting the customer's time.
### Conversation Guidelines
- Always be polite and maintain a medium-paced speaking style.
- Crack jokes in between to for entertaining the potential lead.
- When the conversation veers off-topic, gently bring it back with a polite reminder.
### First Message
The first message you receive from the customer is their name and a summary of their last call, repeat this exact message to the customer as the greeting.
### Handling FAQs
Use the function `question_and_answer` to respond to common customer queries.
### Booking a Tow
When a customer shows interest:
1. Ask if they like to have a demo call.
2. If yes, use the `book_meeting` function to arrange a meeting with calley team. 
When the customer shows no interest or is reluctant:
1. Ask if there is any specific service they are looking for.
2. Wish them a good day and tell them not to hesitate to reach calley if they feel the need in future.
"""

# Some default constants
VOICE = 'alloy'
PORT = int(os.getenv('PORT', 5050))
MAKE_WEBHOOK_URL = "https://hook.us2.make.com/6c88s86jeia5rxhu2yzr6tsuf8636l7k"

# Session management
sessions = {}

# Event types to log
LOG_EVENT_TYPES = [
    'response.content.done',
    'rate_limits.updated',
    'response.done',
    'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped',
    'input_audio_buffer.speech_started',
    'session.created',
    'response.text.done',
    'conversation.item.input_audio_transcription.completed'
]

# Root route
@app.get("/")
async def root():
    return {"message": "Twilio Media Stream Server is running!"}

# Function to send data to the Make.com webhook
async def send_to_webhook(payload):
    print('Sending data to webhook:', json.dumps(payload, indent=2))
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(MAKE_WEBHOOK_URL, json=payload) as response:
                print('Webhook response status:', response.status)
                if response.ok:
                    response_text = await response.text()
                    print('Webhook response:', response_text)
                    return response_text
                else:
                    print('Failed to send data to webhook:', response.reason)
                    raise Exception('Webhook request failed')
    except Exception as error:
        print('Error sending data to webhook:', str(error))
        raise
    
from fastapi import Form
from starlette.websockets import WebSocketDisconnect

# Handle incoming calls from Twilio
@app.post("/incoming-call")
async def incoming_call(From: str = Form(...), CallSid: str = Form(...)):
    print('Incoming call')
    
    caller_number = From or 'Unknown'
    session_id = CallSid
    print('Caller Number:', caller_number)
    print('Session ID (CallSid):', session_id)

    first_message = "Hello, welcome to Calley AI. How can I assist you today?"

    try:
        webhook_response = await send_to_webhook({
            "route": "1",
            "data1": caller_number,
            "data2": "empty"
        })

        response_data = json.loads(webhook_response)
        if response_data and 'firstMessage' in response_data:
            first_message = response_data['firstMessage']
            print('Parsed firstMessage from Make.com:', first_message)
        else:
            first_message = webhook_response.strip()
    except Exception as error:
        print('Error sending data to Make.com webhook:', str(error))

    # Set up a new session for this call
    session = {
        'transcript': '',
        'stream_sid': None,
        'caller_number': caller_number,
        'call_details': {
            'From': From,
            'CallSid': CallSid
        },
        'first_message': first_message
    }
    sessions[session_id] = session

    # Respond to Twilio with TwiML
    twiml_response = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Connect>
            <Stream url="wss://{request.url.hostname}/media-stream">
                <Parameter name="firstMessage" value="{first_message}" />
                <Parameter name="callerNumber" value="{caller_number}" />
            </Stream>
        </Connect>
    </Response>
    """

    return Response(content=twiml_response, media_type="application/xml")

# WebSocket route to handle the media stream
@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    print('Client connected to media-stream')

    first_message = ''
    stream_sid = ''
    openai_ws_ready = asyncio.Event()
    queued_first_message = None
    thread_id = ""

    try:
        # Get session ID from headers
        session_id = websocket.headers.get('x-twilio-call-sid') or f"session_{int(time.time())}"
        session = sessions.get(session_id, {'transcript': '', 'stream_sid': None})
        sessions[session_id] = session

        caller_number = session.get('caller_number', 'Unknown')
        print('Caller Number:', caller_number)

        # Open a WebSocket connection to the OpenAI Realtime API
        async with websockets.connect(
            'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
            extra_headers={
                'Authorization': f'Bearer {OPENAI_API_KEY}',
                'OpenAI-Beta': 'realtime=v1'
            }
        ) as openai_ws:
            # Function to send the session configuration to OpenAI
            async def send_session_update():
                session_update = {
                    'type': 'session.update',
                    'session': {
                        'turn_detection': {'type': 'server_vad'},
                        'input_audio_format': 'g711_ulaw',
                        'output_audio_format': 'g711_ulaw',
                        'voice': VOICE,
                        'instructions': SYSTEM_MESSAGE,
                        'modalities': ["text", "audio"],
                        'temperature': 0.8,
                        'input_audio_transcription': {
                            "model": "whisper-1"
                        },
                        'tools': [
                            {
                                'type': "function",
                                'name': "question_and_answer",
                                'description': "Get answers to customer questions about calley ai and how it qualifies the lead using ai cold calling.",
                                'parameters': {
                                    'type': "object",
                                    'properties': {
                                        "question": {"type": "string"}
                                    },
                                    'required': ["question"]
                                }
                            },
                            {
                                'type': "function",
                                'name': "book_tow",
                                'description': "Book a meeting with the customer",
                                'parameters': {
                                    'type': "object",
                                    'properties': {
                                        "address": {"type": "string"}
                                    },
                                    'required': ["address"]
                                }
                            }
                        ],
                        'tool_choice': "auto"
                    }
                }
                print('Sending session update:', json.dumps(session_update))
                await openai_ws.send(json.dumps(session_update))

            # Function to send the first message
            async def send_first_message():
                nonlocal queued_first_message
                if queued_first_message and openai_ws_ready.is_set():
                    print('Sending queued first message:', queued_first_message)
                    await openai_ws.send(json.dumps(queued_first_message))
                    await openai_ws.send(json.dumps({'type': 'response.create'}))
                    queued_first_message = None

            # Set up event handlers for OpenAI WebSocket
            openai_ws_ready.set()
            await send_session_update()
            await send_first_message()

            # Main loop to handle messages from Twilio and OpenAI
            while True:
                done, pending = await asyncio.wait(
                    [websocket.receive_text(), openai_ws.recv()],
                    return_when=asyncio.FIRST_COMPLETED
                )

                for task in done:
                    message = task.result()

                    if task == websocket.receive_text():
                        # Handle messages from Twilio
                        data = json.loads(message)

                        if data['event'] == 'start':
                            stream_sid = data['start']['streamSid']
                            call_sid = data['start']['callSid']
                            custom_parameters = data['start'].get('customParameters', {})

                            print('CallSid:', call_sid)
                            print('StreamSid:', stream_sid)
                            print('Custom Parameters:', custom_parameters)

                            caller_number = custom_parameters.get('callerNumber', 'Unknown')
                            session['caller_number'] = caller_number
                            first_message = custom_parameters.get('firstMessage', "Hello, how can I assist you?")
                            print('First Message:', first_message)
                            print('Caller Number:', caller_number)

                            queued_first_message = {
                                'type': 'conversation.item.create',
                                'item': {
                                    'type': 'message',
                                    'role': 'user',
                                    'content': [{'type': 'input_text', 'text': first_message}]
                                }
                            }

                            if openai_ws_ready.is_set():
                                await send_first_message()

                        elif data['event'] == 'media':
                            audio_append = {
                                'type': 'input_audio_buffer.append',
                                'audio': data['media']['payload']
                            }
                            await openai_ws.send(json.dumps(audio_append))

                    else:
                        # Handle messages from OpenAI
                        response = json.loads(message)

                        if response['type'] == 'response.audio.delta' and 'delta' in response:
                            await websocket.send_json({
                                'event': 'media',
                                'streamSid': stream_sid,
                                'media': {'payload': response['delta']}
                            })

                        # Handle function calls
                        if response['type'] == 'response.function_call_arguments.done':
                            print("Function called:", response)
                            function_name = response['name']
                            args = json.loads(response['arguments'])

                            if function_name == 'question_and_answer':
                                question = args['question']
                                try:
                                    webhook_response = await send_to_webhook({
                                        'route': "3",
                                        'data1': question,
                                        'data2': thread_id
                                    })

                                    print("Webhook response:", webhook_response)

                                    parsed_response = json.loads(webhook_response)
                                    answer_message = parsed_response.get('message', "I'm sorry, I couldn't find an answer to that question.")

                                    if 'thread' in parsed_response:
                                        thread_id = parsed_response['thread']
                                        print("Updated thread ID:", thread_id)

                                    function_output_event = {
                                        'type': "conversation.item.create",
                                        'item': {
                                            'type': "function_call_output",
                                            'role': "system",
                                            'output': answer_message,
                                        }
                                    }
                                    await openai_ws.send(json.dumps(function_output_event))

                                    await openai_ws.send(json.dumps({
                                        'type': "response.create",
                                        'response': {
                                            'modalities': ["text", "audio"],
                                            'instructions': f'Respond to the user\'s question "{question}" based on this information: {answer_message}. Be concise and friendly.',
                                        }
                                    }))
                                except Exception as error:
                                    print('Error processing question:', str(error))
                                    await send_error_response(openai_ws)

                            elif function_name == 'book_tow':
                                address = args['address']
                                try:
                                    webhook_response = await send_to_webhook({
                                        'route': "4",
                                        'data1': session['caller_number'],
                                        'data2': address
                                    })

                                    print("Webhook response:", webhook_response)

                                    parsed_response = json.loads(webhook_response)
                                    booking_message = parsed_response.get('message', "I'm sorry, I couldn't book the tow service at this time.")

                                    function_output_event = {
                                        'type': "conversation.item.create",
                                        'item': {
                                            'type': "function_call_output",
                                            'role': "system",
                                            'output': booking_message,
                                        }
                                    }
                                    await openai_ws.send(json.dumps(function_output_event))

                                    await openai_ws.send(json.dumps({
                                        'type': "response.create",
                                        'response': {
                                            'modalities': ["text", "audio"],
                                            'instructions': f'Inform the user about the tow booking status: {booking_message}. Be concise and friendly.',
                                        }
                                    }))
                                except Exception as error:
                                    print('Error booking tow:', str(error))
                                    await send_error_response(openai_ws)

                        # Log agent response
                        if response['type'] == 'response.done':
                            agent_message = next((content['transcript'] for content in response['response']['output'][0].get('content', []) if 'transcript' in content), 'Agent message not found')
                            session['transcript'] += f"Agent: {agent_message}\n"
                            print(f"Agent ({session_id}): {agent_message}")

                        # Log user transcription
                        if response['type'] == 'conversation.item.input_audio_transcription.completed' and 'transcript' in response:
                            user_message = response['transcript'].strip()
                            session['transcript'] += f"User: {user_message}\n"
                            print(f"User ({session_id}): {user_message}")

                        # Log other relevant events
                        if response['type'] in LOG_EVENT_TYPES:
                            print(f"Received event: {response['type']}", response)

    except WebSocketDisconnect:
        print(f"Client disconnected ({session_id}).")
        print('Full Transcript:')
        print(session['transcript'])
        print('Final Caller Number:', session['caller_number'])

        await send_to_webhook({
            'route': "2",
            'data1': session['caller_number'],
            'data2': session['transcript']
        })

        del sessions[session_id]

    except Exception as e:
        print(f"Error in WebSocket connection: {str(e)}")

# Helper function for sending error responses
async def send_error_response(ws):
    await ws.send(json.dumps({
        "type": "response.create",
        "response": {
            "modalities": ["text", "audio"],
            "instructions": "I apologize, but I'm having trouble processing your request right now. Is there anything else I can help you with?",
        }
    }))

# Run the FastAPI app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)