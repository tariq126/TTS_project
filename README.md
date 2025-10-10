# Distributed Multi-Provider Text-to-Speech (TTS) Service

This project is a service that converts text into speech. You can submit multiple blocks of text, and the service will generate a single audio file. It supports multiple TTS providers like ElevenLabs, OpenAI, and Ghaymah Pro.

## Architecture

The system is designed as a scalable and robust TTS processing pipeline. The following diagram illustrates the high-level architecture and data flow:

```ascii
+--------+      1. Submit Job      +-----------------+
|        | ----------------------> |                 |
| Client |      (JSON Request)     |   FastAPI (API)   |
|        | <---------------------- |                 |
+--------+   5. Get Result (URL)   +-----------------+
                                           ^
                                           | 2. Enqueue Task
                                           v
+-----------------+      3. Process Task     +------------------+
|                 | ----------------------> |                  |
|  Celery Worker  |                         |  TTS Providers   |
| (with Redis)    | <---------------------- | (ElevenLabs, etc)|
|                 |      (Audio Chunks)     |                  |
+-----------------+                         +------------------+
                                                  | 4. Upload & Finalize
                                                  v
                                           +----------------+
                                           |                |
                                           |   Cloudinary   |
                                           |   (Storage)    |
                                           |                |
                                           +----------------+
```

## Features

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
*   **Monitoring and Logging**: The application is configured to log to standard output, making it easy to monitor using container orchestration platforms.

**Stack:** FastAPI, Celery, Redis, Cloudinary, FFmpeg, Docker, Supervisor

## Getting Started

### Prerequisites

*   [Docker](https://docs.docker.com/get-docker/)
*   [Docker Compose](https://docs.docker.com/compose/install/)
*   FFmpeg (required for local development if not using Docker)

### Setup & Installation

1.  **Clone the Repository**

    ```bash
    git clone <your-repository-url>
    cd tts_project
    ```

2.  **Configure Environment Variables**

    Create a file named `.env` in the project root. The application uses `python-dotenv` to automatically load these variables at startup. If you are not using a tool that loads `.env` files, you will need to export these variables into your shell environment manually.

    Fill the `.env` file with your secret keys and configuration:

    ```env
    # Generate a new key with: openssl rand -hex 32
    SECRET_KEY="your_strong_secret_key_here"

    # TTS Provider API Keys
    ELEVENLABS_API_KEY="your_elevenlabs_api_key"
    GHAYMAH_API_KEY="your_ghaymah_api_key"
    GHAYMAH_PRO_API_KEY="your_ghaymah_pro_api_key"

    # Diacritizer API URL
    DIACRITIZER_URL="your_diacritizer_api_url"

    # Cloudinary Configuration
    CLOUDINARY_URL="cloudinary://<api_key>:<api_secret>@<cloud_name>"
    ```

### Running the Application

#### Using Docker Compose (Recommended)

This is the easiest way to run the entire application stack, including the API, worker, and Redis.

1.  **Build and start the services:**

    ```bash
    docker-compose up --build
    ```

2.  The API will be available at `http://localhost:8000`.

#### Running Locally (for development)

If you prefer to run the services manually without Docker, follow these steps.

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
4.  **Start the FastAPI Server:**
    ```bash
    uvicorn api.main:app --reload --log-level info
    ```

## API Usage Examples

The API documentation is available at `http://localhost:8000/docs` when the application is running.

### 1. Get an Authentication Token

First, get a JWT token by providing the default credentials.

```bash
curl -X POST "http://localhost:8000/token" \
-H "Content-Type: application/x-www-form-urlencoded" \
-d "username=admin&password=secret"
```

The response will be a JSON object containing your `access_token`.

### 2. Submit a TTS Job

Next, use the `access_token` as a Bearer token to submit a new TTS job.

> **Note**: Replace `<your_token>` with the actual token obtained from the `/token` endpoint.

```bash
curl -X POST "http://localhost:8000/tts" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer <your_token>" \
-d \
'{
  "project_id": "my_curl_project",
  "blocks": [
    {
      "text": "This is a test from a curl command.",
      "wait_after_ms": 250,
      "provider": "elevenlabs",
      "voice": "rachel",
      "arabic": false
    },
    {
      "text": "مَرْحَبًا مِن العَالَمِ",
      "wait_after_ms": 0,
      "provider": "ghaymah_pro",
      "voice": "male-1",
      "arabic": true
    }
  ]'
```

The response will contain the `job_id`, which you can use to check the status and retrieve the final audio file.

## Future Improvements / Known Limitations

*   **Planned:** Add a caching layer for diacritized text to reduce latency and redundant API calls.
*   **Planned:** Implement more robust error handling and retry mechanisms for TTS provider failures.
*   **Known:** Cloudinary free tier quotas may limit audio storage for heavy users.
*   **Known:** The `/token` endpoint uses static credentials, which should be replaced with a more secure authentication system in a production environment.

## Project Structure

```
tts_project/
├── api/
│   └── main.py             # FastAPI application (API Layer)
├── workers/
│   ├── providers/          # Modular TTS provider classes
│   └── tts_worker.py       # Celery tasks (Worker Layer)
├── utils/
│   ├── logger.py           # Centralized logger configuration
│   └── schemas.py          # Shared data models
├── temp/                   # Temporary audio files (auto-cleaned)
├── .env                    # Environment variables (MUST create)
├── config.py               # Central provider configuration
├── requirements.txt        # Python dependencies
├── Dockerfile              # Dockerfile for building the application image
├── docker-compose.yml      # Docker Compose for running the application stack
└── README.md               # This file
```

## Security

*   **JWT Authentication**: API endpoints are protected with JWT authentication.
*   **Scheduled Cleanup**: A Celery Beat task automatically cleans up temporary files to conserve server resources.

## Contributing

Contributions are welcome! Please open an issue on GitHub to discuss any changes or new features.

## License

This project is under a private license.
