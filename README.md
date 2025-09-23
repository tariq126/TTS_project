Distributed Multi-Provider Text-to-Speech (TTS) Service
A robust, scalable, and secure API for converting ordered blocks of text into a single audio file. This service uses a distributed architecture with background workers to handle long-running TTS tasks without blocking the API. Its modular design allows for easy integration of multiple TTS providers (e.g., cloud-based ElevenLabs, and other OpenAI-compatible APIs).

Features
Asynchronous API: Built with FastAPI for high performance and non-blocking I/O.

Parallel Processing: Uses Celery and Redis to process multiple text blocks concurrently, significantly speeding up audio generation.

Multi-Provider Architecture: Easily extendable to support various TTS engines through a simple, configuration-driven provider system.

Cloud Storage: All audio files (individual blocks and the final result) are uploaded to Cloudinary for persistent storage.

Direct Audio Streaming: Endpoints are available to stream raw MP3 files directly, in addition to providing Cloudinary URLs.

Secure by Design: Endpoints are protected with JWT authentication and rate-limited to prevent abuse.

Scheduled Cleanup: A Celery Beat task automatically cleans up temporary files to conserve server resources.

Custom Audio Pauses: Supports specifying custom silence durations between text blocks.

Architecture Flow
The service follows a distributed, asynchronous pattern to ensure scalability and responsiveness.

Client -> API (/tts): A user sends an authenticated request with an ordered list of text blocks. Each block can specify a different TTS provider and voice.

API -> Redis: The API validates the request, creates a unique job_id, and stores the job's initial data in a Redis hash.

API -> Celery Queue: The API dispatches a process_block task to the Celery queue for each text block. It then immediately returns the job_id to the client with a 202 Accepted status.

Celery Worker -> TTS Provider: A worker picks up a task. It uses the provider factory to select the correct TTS engine (e.g., ElevenLabsProvider), generates the audio, and saves it to a temporary file.

Celery Worker -> Cloudinary: The worker uploads the temporary audio file to Cloudinary.

Celery Worker -> Redis: The worker updates the job hash in Redis, adding the block's new Cloudinary URL and atomically incrementing a "blocks done" counter. The last worker to finish triggers the combine_blocks task.

Combine Task: A worker downloads all individual audio files from Cloudinary, concatenates them with pydub (respecting any specified pauses), and uploads the final combined MP3 to Cloudinary.

Final Update: The worker updates the job in Redis with the final URL and sets the status to completed. The temporary files are kept on the server for a configured duration for direct download.

Client -> API (/result): The client can poll the /status endpoint and, once completed, retrieve the final result, either as a JSON object with URLs or as a direct audio stream.

Project Structure
tts_project/
├── venv/
├── api/
│   └── main.py             # FastAPI application (API Layer)
├── workers/
│   ├── providers/          # Modular TTS provider classes
│   │   ├── __init__.py     # Provider factory
│   │   ├── base.py         # Abstract base class for providers
│   │   └── elevenlabs.py
│   └── tts_worker.py       # Celery tasks (Worker Layer)
├── utils/
│   ├── redis_client.py     # Centralized Redis connection
│   └── schemas.py          # Shared data models (e.g., JobStatus enum)
├── temp/                   # Temporary audio files (auto-cleaned)
├── .env                    # Environment variables (MUST create)
├── config.py               # Central provider configuration
└── README.md               # This file

Setup and Installation
System Prerequisites
You must have the following software installed on your system and available in your system's PATH.

Python 3.11: Download Python 3.11.9

Redis: A running Redis server. (On Windows, install via WSL: sudo apt install redis-server).



FFmpeg: Required for audio processing by pydub. Download FFmpeg.

1. Clone & Setup Environment
git clone <your-repository-url>
cd tts_project

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows

2. Install Dependencies
Install all required Python packages. It is recommended to create a requirements.txt file first.

# Create the requirements file
pip freeze > requirements.txt

# Install from the file
pip install -r requirements.txt

3. Configure Environment Variables
Create a file named .env in the project root. This file is critical for storing secret keys and configuration.

.env file contents:
# Generate a new key with: openssl rand -hex 32
SECRET_KEY="your_strong_secret_key_here"


# Optional: Defaults to localhost if not set
REDIS_URL="redis://localhost:80/0"

Running the Application
You must run four separate processes in four separate terminals for the full application with scheduled cleanup.

Terminal 1: Start Redis
(In your WSL/Ubuntu terminal)

sudo redis-server

Terminal 2: Start the Celery Worker
(In PowerShell with venv activated)

celery -A workers.tts_worker.celery_app worker --loglevel=info -P gevent

Terminal 3: Start the Celery Beat Scheduler
(In another PowerShell with venv activated)

celery -A workers.tts_worker.celery_app beat --loglevel=info

Terminal 4: Start the FastAPI Server
(In a third PowerShell with venv activated)

uvicorn api.main:app --reload --log-level info

Your service is now running at http://127.0.0.1:8000.

API Documentation & Usage
This API is designed for programmatic integration. All generation and result endpoints require a Bearer token for authentication.

Authentication
POST /token

First, get an authentication token by sending your credentials.

Request Body (x-www-form-urlencoded):

username: admin

password: secret

Response: A JSON object with an access_token. Include this token in the Authorization header for all subsequent requests as Bearer <token>.

Discovery Endpoints
These endpoints help your application discover what TTS capabilities are available.

GET /tts/providers: Returns a list of all configured provider names (e.g., ["elevenlabs", "ghaymah"]).

GET /tts/voices/{provider_name}: Returns a list of available voices for a specific provider.

Generation Workflow
1. Create a Job

POST /tts: Submits a new text-to-speech job.

Request Body (JSON):

{
  "blocks": [
    {
      "text": "Hello from an OpenAI voice.",
      "wait_after_ms": 500,
      "provider": "openai",
      "voice": "tts-1"
    },
    {
      "text": "And hello from a different voice!",
      "wait_after_ms": 0,
      "provider": "elevenlabs",
      "voice": "rachel"
    }
  ]
}

Response: A JSON object with the job_id and a status of queued.

2. Check Job Status (Optional)

GET /status/{job_id}: Poll this endpoint to monitor the progress of a job.

Response: A JSON object showing the current status and progress (e.g., "2/2").

3. Retrieve Results

Once the job status is completed, you can retrieve the audio.

GET /result/{job_id}: Returns a JSON object containing the Cloudinary URLs for the final combined audio and each individual block.

GET /result/{job_id}/audio: Returns the raw MP3 file for the final combined audio. The Content-Type will be audio/mpeg.

GET /result/{job_id}/block/{block_index}/audio: Returns the raw MP3 file for a specific audio block.