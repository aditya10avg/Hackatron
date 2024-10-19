import asyncio
from livekit import cli, agents
from agent import entrypoint as voice_agent_entrypoint
from outbound_call import make_outbound_call

from livekit.agents import WorkerOptions

async def entrypoint_with_outbound_call(ctx: agents.JobContext):
    """
    This function is the modified entrypoint that combines the voice assistant
    with outbound call functionality.
    """

    # Step 1: Make the outbound call
    print("Starting an outbound call...")
    call_sid = make_outbound_call(
        to_phone_number='+1234567890',  # Replace with the recipient's phone number
        twiml_url='https://your-ngrok-url.com/twiml'  # Run the server.py and connect it to ngrok but remember adding livekit url to the server.py file.
    )
    print(f"Outbound call started with SID: {call_sid}")

    # Step 2: Start the voice assistant logic
    await voice_agent_entrypoint(ctx)

if __name__ == "__main__":
    # Run the modified entrypoint that includes both voice assistant and outbound calling
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint_with_outbound_call))
