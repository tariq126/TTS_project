# Simple README (User-Friendly)

## Distributed Multi-Provider Text-to-Speech (TTS) Service

This project is a service that converts text into speech. You can submit multiple blocks of text, and the service will generate a single audio file. It supports multiple TTS providers like ElevenLabs, OpenAI, and Ghaymah Pro.

### Features

*   **Asynchronous API**: The API is fast and doesn't block, even for long-running tasks.
*   **Parallel Processing**: Multiple text blocks are processed at the same time, which makes the audio generation faster.
*   **Multi-Provider Architecture**: You can use different TTS providers for different text blocks.
*   **Arabic Text Preprocessing**: Arabic text is automatically diacritized before being sent to the TTS provider.
*   **Cloud Storage**: The generated audio files are stored in the cloud.
*   **Direct Audio Streaming**: You can stream the generated audio files directly.
*   **Secure**: The API is protected with JWT authentication.
*   **Scheduled Cleanup**: Temporary files are automatically cleaned up to save server resources.
*   **Custom Audio Pauses**: You can add custom pauses between text blocks.

### Installation & Usage

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd tts_project
    ```
2.  **Configure environment variables:**
    Create a file named `.env` in the project root and add the required API keys and configuration.
3.  **Run the application:**
    ```bash
    docker-compose up --build
    ```

### Example Usage

1.  **Get an authentication token:**
    ```bash
    curl -X POST -d "username=admin&password=secret" http://localhost:8000/token
    ```
2.  **Submit a TTS job:**
    ```bash
    curl -X POST -H "Authorization: Bearer <your_token>" -H "Content-Type: application/json" -d '{
      "project_id": "<your_project_id>",
      "blocks": [
        {
          "text": "Hello from an OpenAI voice.",
          "wait_after_ms": 500,
          "provider": "ghaymah",
          "voice": "tts-1",
          "arabic": false
        },
        {
          "text": "And hello from a different voice!",
          "wait_after_ms": 0,
          "provider": "elevenlabs",
          "voice": "rachel",
          "arabic": false
        }
      ]
    }' http://localhost:8000/tts
    ```
3.  **Check the job status:**
    ```bash
    curl -H "Authorization: Bearer <your_token>" http://localhost:8000/status/<job_id>
    ```
4.  **Get the result:**
    ```bash
    curl -H "Authorization: Bearer <your_token>" http://localhost:8000/result/<job_id>
    ```

### Contact & Contributing

For any questions or to contribute to the project, please open an issue on GitHub.

---

# Technical README (Developer-Focused)

## Distributed Multi-Provider Text-to-Speech (TTS) Service

This project is a robust, scalable, and secure API for converting ordered blocks of text into a single audio file. It uses a distributed architecture with background workers to handle long-running Text-to-Speech (TTS) tasks without blocking the API. The modular design allows for easy integration of multiple TTS providers like ElevenLabs, OpenAI-compatible APIs, and Ghaymah Pro.

### Live Deployment

The service is currently deployed and accessible at:
[https://tts-projects5-6b0213ee7492.hosted.ghaymah.systems](https://tts-projects5-6b0213ee7492.hosted.ghaymah.systems)

It is hosted on a server using Docker Compose to manage the application containers.

### Features

*   **Asynchronous API**: Built with FastAPI for high performance and non-blocking I/O.
*   **Parallel Processing**: Uses Celery and Redis to process multiple text blocks concurrently, significantly speeding up audio generation.
*   **Multi-Provider Architecture**: Easily extendable to support various TTS engines through a simple, configuration-driven provider system.
*   **Arabic Text Preprocessing**: Automatically adds diacritics to Arabic text before sending it to the TTS provider.
*   **Cloud Storage**: All audio files (individual blocks and the final result) are uploaded to Cloudinary for persistent storage.
*   **Direct Audio Streaming**: Endpoints are available to stream raw MP3 files directly, in addition to providing Cloudinary URLs.
*   **Secure by Design**: API endpoints are protected with JWT authentication.
*   **Scheduled Cleanup**: A Celery Beat task automatically cleans up temporary files to conserve server resources.
*   **Custom Audio Pauses**: Supports specifying custom silence durations between text blocks.
*   **Containerized**: Comes with a `Dockerfile` and `docker-compose.yml` for easy setup and deployment.
*   **Monitoring and Logging**: The application is configured to log to standard output, making it easy to monitor using container orchestration platforms. The `supervisord.conf` file ensures that logs from all services are readily accessible.

### Tech Stack

*   **Backend**: FastAPI
*   **Task Queue**: Celery
*   **Message Broker**: Redis
*   **Cloud Storage**: Cloudinary
*   **Containerization**: Docker
*   **Authentication**: JWT

### Architecture Flow

The service follows a distributed, asynchronous pattern to ensure scalability and responsiveness.

1.  **Client -> API (/tts)**: A user sends an authenticated request with an ordered list of text blocks. Each block can specify a different TTS provider and voice. If a block is marked as Arabic, the API first sends the text to a diacritization service.
2.  **API -> Redis**: The API validates the request, creates a unique `job_id`, and stores the job's initial data in a Redis hash.
3.  **API -> Celery Queue**: The API dispatches a `process_block` task to the Celery queue for each text block. It then immediately returns the `job_id` to the client with a `202 Accepted` status.
4.  **Celery Worker -> TTS Provider**: A worker picks up a task. It uses the provider factory to select the correct TTS engine (e.g., `ElevenLabsProvider`, `OpenAIProvider`, `GhaymahProProvider`), generates the audio, and saves it to a temporary file.
5.  **Celery Worker -> Cloudinary**: The worker uploads the temporary audio file to Cloudinary.
6.  **Celery Worker -> Redis**: The worker updates the job hash in Redis, adding the block's new Cloudinary URL and its local file path, then atomically increments a "blocks done" counter. The last worker to finish triggers the `combine_blocks` task.
7.  **Combine Task**: A worker reads the local file paths of the generated audio blocks from Redis, concatenates them directly from the local `temp` directory using `pydub` (respecting any specified pauses), and uploads the final combined MP3 to Cloudinary. This avoids unnecessary re-downloading.
8.  **Final Update**: The worker updates the job in Redis with the final URL and sets the status to `completed`. The temporary files are kept on the server for a configured duration for direct download.
9.  **Client -> API (/result)**: The client can poll the `/status` endpoint and, once completed, retrieve the final result, either as a JSON object with URLs or as a direct audio stream.

### Audio Generation Workflow

The service processes text-to-speech requests through a detailed, multi-step workflow designed for efficiency and scalability. Here’s how it works from job submission to final audio delivery:

1.  **User-Defined Text Blocks**: The client submits a request containing an array of "blocks." This approach is used instead of automatic splitting to give the user full control over the final audio. It allows using different TTS providers, voices, or languages for different segments of the text and inserting custom pauses between them. It also helps manage provider-specific character limits.

2.  **Asynchronous Block Processing**: For each block in the request, the API dispatches a `process_block` task to a Celery worker. The workers execute these tasks in parallel. Each worker selects the appropriate TTS provider (e.g., ElevenLabs, OpenAI) based on the block's configuration and calls its `generate_audio` method to convert the text into an audio segment.

3.  **Temporary Storage and Cloud Upload**: The generated audio for each block is first saved as a temporary MP3 file on the server's local filesystem inside the `temp/` directory. Immediately after, the worker uploads this file to Cloudinary, ensuring that even intermediate audio segments are persisted. The Cloudinary URL and the local file path are stored in Redis.

4.  **Combining Audio with `pydub`**: Once all blocks for a job have been processed, a final `combine_blocks` task is triggered. This task reads the local file paths of all audio segments from Redis. It then uses the `pydub` library to concatenate them in the correct order. If the user specified a `wait_after_ms` value for any block, a corresponding duration of silence is inserted between the audio segments.

5.  **Finalization and Delivery**: The combined audio is exported as a single MP3 file and uploaded to Cloudinary. The job's status in Redis is updated to `completed`, and the final Cloudinary URL is saved. The client can then retrieve the result via the `/result/{job_id}` endpoint, which provides the URL, or stream the final audio directly from the `/result/{job_id}/audio` endpoint.

## Architecture Diagram

```
+-----------------+      +-----------------+      +-----------------+      +-----------------+
|   Client        |----->|   FastAPI (API) |----->|   Redis         |      | Diacritizer API |
+-----------------+      +-----------------+      +-----------------+      +-----------------+
                           |                                                ^
                           |                                                |
                           v                                                |
+-----------------+      +-----------------+      +--------------------------+
|   Celery Worker |<-----|   Celery Queue  |
+-----------------+      +-----------------+
        |
        |
        v
+-----------------+      +-----------------+
|   TTS Provider  |----->|   Cloudinary    |
+-----------------+      +-----------------+
```

### Project Structure

```
tts_project/
├── api/
│   └── main.py             # FastAPI application (API Layer)
├── workers/
│   ├── providers/          # Modular TTS provider classes
│   │   ├── __init__.py     # Provider factory
│   │   ├── base.py         # Abstract base class for providers
│   │   ├── elevenlabs.py   # ElevenLabs provider
│   │   ├── openai.py       # OpenAI-compatible provider
│   │   └── ghaymah_pro.py  # Ghaymah Pro provider
│   └── tts_worker.py       # Celery tasks (Worker Layer)
├── utils/
│   ├── logger.py           # Centralized logger configuration
│   ├── redis_client.py     # Centralized Redis connection
│   └── schemas.py          # Shared data models (e.g., JobStatus enum)
├── temp/                   # Temporary audio files (auto-cleaned)
├── .env                    # Environment variables (MUST create)
├── config.py               # Central provider configuration
├── requirements.txt        # Python dependencies
├── Dockerfile              # Dockerfile for building the application image
├── docker-compose.yml      # Docker Compose for running the application stack
└── README.md               # This file
```

### Prerequisites

*   [Docker](https://docs.docker.com/get-docker/)
*   [Docker Compose](https://docs.docker.com/compose/install/)

### Setup and Installation

#### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd tts_project
```

#### 2. Configure Environment Variables

Create a file named `.env` in the project root and add the following content. This file is crucial for storing secret keys and configuration.

```
# Generate a new key with: openssl rand -hex 32
SECRET_KEY="your_strong_secret_key_here"

# Redis URL (if not using docker-compose)
# REDIS_URL="redis://localhost:6379/0"

# TTS Provider API Keys
ELEVENLABS_API_KEY="your_elevenlabs_api_key"
GHAYMAH_API_KEY="your_ghaymah_api_key"
GHAYMAH_API_BASE_URL="your_ghaymah_api_base_url"
GHAYMAH_PRO_API_KEY="your_ghaymah_pro_api_key"
GHAYMAH_PRO_API_BASE_URL="your_ghaymah_pro_api_base_url"


# Diacritizer API URL
DIACRITIZER_URL="your_diacritizer_api_url"

# Cloudinary Configuration
CLOUDINARY_URL="cloudinary://<api_key>:<api_secret>@<cloud_name>"
```

### Running the Application

#### Using Docker Compose (Recommended)

This is the easiest way to run the entire application stack, including the API, worker, and Redis. The `Dockerfile` uses a multi-stage build for a smaller and more secure final image. It also uses `supervisor` to manage the `redis`, `celery`, and `uvicorn` processes.

1.  **Build and start the services:**

    ```bash
    docker-compose up --build
    ```

2.  The API will be available at `http://localhost:8000`.

#### Running Locally (for development)

If you prefer to run the services manually without Docker, follow these steps.

**Prerequisites:**

*   Python 3.11
*   Redis
*   FFmpeg

1.  **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

2.  **Start Redis:**

    ```bash
    redis-server
    ```

3.  **Start the Celery Worker:**

    ```bash
    celery -A workers.tts_worker.celery_app worker --loglevel=info -P gevent
    ```

4.  **Start the Celery Beat Scheduler (for cleanup tasks):**

    ```bash
    celery -A workers.tts_worker.celery_app beat --loglevel=info
    ```

5.  **Start the FastAPI Server:**

    ```bash
    uvicorn api.main:app --reload --log-level info
    ```

### API Documentation

The API documentation is available at `http://localhost:8000/docs` when the application is running.

#### Authentication

**POST /token**

First, get an authentication token by sending your credentials.

*   **Request Body** (`x-www-form-urlencoded`):
    *   `username`: `admin`
    *   `password`: `secret`
*   **Response**: A JSON object with an `access_token`.

Include this token in the `Authorization` header for all subsequent requests as `Bearer <token>`.

#### Discovery Endpoints

*   **GET /tts/providers**: Returns a list of all configured provider names (e.g., `["elevenlabs", "ghaymah", "ghaymah_pro"]`).
*   **GET /tts/voices/{provider_name}**: Returns a list of available voices for a specific provider.

#### Generation Workflow

1.  **Create a Job**

    **POST /tts**: Submits a new text-to-speech job.

    *   **Request Body** (JSON):
        ```json
        {
          "project_id": "<your_project_id>",
          "blocks": [
            {
              "text": "Hello from an OpenAI voice.",
              "wait_after_ms": 500,
              "provider": "ghaymah",
              "voice": "tts-1",
              "arabic": false
            },
            {
              "text": "And hello from a different voice!",
              "wait_after_ms": 0,
              "provider": "elevenlabs",
              "voice": "rachel",
              "arabic": false
            },
            {
                "text": "مرحبا من صوت عربي",
                "wait_after_ms": 0,
                "provider": "ghaymah_pro",
                "voice": "male-1",
                "arabic": true
            }
          ]
        }
        ```
    *   **Response**: A JSON object with the `job_id` and a status of `queued`.

2.  **Check Job Status (Optional)**

    **GET /status/{job_id}**: Poll this endpoint to monitor the progress of a job.

3.  **Retrieve Results**

    Once the job status is `completed`, you can retrieve the audio.

    *   **GET /result/{job_id}**: Returns a JSON object containing the Cloudinary URLs for the final combined audio and each individual block.
    *   **GET /result/{job_id}/audio**: Returns the raw MP3 file for the final combined audio.
    *   **GET /result/{job_id}/block/{block_index}/audio**: Returns the raw MP3 file for a specific audio block.

### Configuration

The main configuration for TTS providers is in `config.py`. You can add new providers or.
To add a new provider, you need to:

1.  Create a new provider class in `workers/providers/` that inherits from `TTSProvider`.
2.  Implement the `generate_audio` and `get_voices` methods.
3.  Add the new provider to the `TTS_PROVIDERS` dictionary in `config.py`.
4.  Update the `PROVIDER_CLASS_MAP` in `workers/providers/__init__.py` to include your new provider class.

### Security Notes

*   **JWT Authentication**: All API endpoints are protected with JWT authentication.
*   **Scheduled Cleanup**: A Celery Beat task automatically cleans up temporary files to conserve server resources.

### License

This project is licensed under the MIT License.
