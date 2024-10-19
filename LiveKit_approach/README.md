# LiveKit Assistant

First, create a virtual environment, update pip, and install the required packages:

```
$ python3 -m venv calley
$ source calley/bin/activate.fish (only because I use fish shell)
$ pip install -pip U
$ pip install -r requirements.txt
```

You need to set up the following environment variables:

```
LIVEKIT_URL=...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
DEEPGRAM_API_KEY=...
OPENAI_API_KEY=...
```

Then, run the assistant:

```
$ cd LiveKit_approach
$ python3 agent.py download-files
$ python3 agent.py start
```

Load the [hosted playground](https://agents-playground.livekit.io/) and connect it.
