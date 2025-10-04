import os
import uuid
import json
import httpx
from datetime import datetime, timedelta, timezone
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from jose import JWTError, jwt
from pydantic import BaseModel, Field

import config
from workers.providers import provider_factory
from utils.redis_client import redis_client
from utils.schemas import JobStatus
from workers.tts_worker import process_block

from utils.logger import logger


TEMP_DIR = "temp"

app = FastAPI()

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# --- Models ---
class TextBlock(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    wait_after_ms: int = Field(0, ge=0)
    provider: str = Field("elevenlabs", description="The TTS provider to use for this block.")
    voice: str = Field("default", description="The voice to use for this block.")
    arabic: bool = Field(False, description="Set to true to preprocess text for Arabic.")


class TTSRequest(BaseModel):
    blocks: List[TextBlock] = Field(..., min_length=1, max_items=50)


class Token(BaseModel):
    access_token: str
    token_type: str


# --- Auth Helpers ---
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise JWTError()
        return {"username": username}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# --- Routes ---
@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    if not (form_data.username == "admin" and form_data.password == "secret"):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "Incorrect username or password"
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": form_data.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/tts/providers", tags=["TTS Discovery"])
def list_providers(current_user: dict = Depends(get_current_user)):
    return list(provider_factory.keys())


@app.get("/tts/voices/{provider_name}", tags=["TTS Discovery"])
def list_voices(provider_name: str, current_user: dict = Depends(get_current_user)):
    if provider_name not in provider_factory:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found.")
    provider = provider_factory[provider_name]
    return provider.get_voices()


# --- Placeholder for Arabic Preprocessing ---
async def _preprocess_arabic_text(text: str) -> str:
    """
    Calls the diacritizer API to add diacritics to the given Arabic text.
    """
    logger.info(f"Using diacritizer URL: {config.DIACRITIZER_URL}")
    if not config.DIACRITIZER_URL:
        logger.warning("DIACRITIZER_URL is not set. Skipping Arabic preprocessing.")
        return text

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config.DIACRITIZER_URL,
                json={"text": text},
                timeout=10.0  # Set a timeout for the request
            )
            response.raise_for_status()  # Raise an exception for bad status codes
            data = response.json()
            processed_text = data.get("diacritized_text")
            if not processed_text:
                raise HTTPException(
                    status_code=500,
                    detail="Diacritizer API did not return processed text."
                )
            logger.info(f"Successfully diacritized text: {text} -> {processed_text}")
            return processed_text
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Error connecting to the diacritizer API: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during Arabic preprocessing: {e}"
        )


@app.post("/tts", status_code=status.HTTP_202_ACCEPTED, tags=["TTS Generation"])
async def create_tts_job(
    tts_request: TTSRequest,
    current_user: dict = Depends(get_current_user)
):
    job_id = str(uuid.uuid4())

    # --- Preprocessing Step ---
    processed_blocks = []
    for block in tts_request.blocks:
        if block.arabic:
            processed_text = await _preprocess_arabic_text(block.text)
            # Create a new block with the processed text, keeping other fields the same
            new_block = block.copy(update={"text": processed_text})
            processed_blocks.append(new_block)
        else:
            processed_blocks.append(block)

    blocks_data = [block.dict() for block in processed_blocks]

    for block in blocks_data:
        provider_name = block.get("provider")
        voice_name = block.get("voice")

        if provider_name not in provider_factory:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider '{provider_name}' in block. "
                       f"Available providers: {list(provider_factory.keys())}"
            )

        provider = provider_factory[provider_name]
        available_voices = [v["voice_id"] for v in provider.get_voices()]
        if voice_name not in available_voices:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid voice '{voice_name}' for provider '{provider_name}'. "
                       f"Available voices: {available_voices}"
            )

    job_data = {
        "status": JobStatus.QUEUED,
        "submitted_by": current_user["username"],
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "blocks": json.dumps(blocks_data),
        "blocks_total": len(blocks_data),
        "blocks_done": 0,
        "block_urls": json.dumps([]),
        "result_url": ""
    }

    redis_client.hset(f"job:{job_id}", mapping=job_data)

    for i, block in enumerate(blocks_data):
        process_block.delay(
            job_id,
            i,
            block['text'],
            block['wait_after_ms'],
            block['provider'],
            block['voice']
        )

    return {"job_id": job_id, "status": JobStatus.QUEUED}


@app.get("/status/{job_id}", tags=["TTS Generation"])
async def get_job_status(job_id: str, current_user: dict = Depends(get_current_user)):
    job_data = redis_client.hgetall(f"job:{job_id}")
    if not job_data:
        return JSONResponse(status_code=404, content={"error": "JOB_NOT_FOUND"})

    job = {k.decode('utf-8'): v.decode('utf-8') for k, v in job_data.items()}

    if job["submitted_by"] != current_user["username"]:
        return JSONResponse(status_code=403, content={"error": "UNAUTHORIZED_ACCESS"})

    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": f"{job.get('blocks_done', 0)}/{job.get('blocks_total', 0)}",
        "result_url": job.get("result_url"),
    }


@app.get("/result/{job_id}", tags=["TTS Generation"])
async def get_job_result(job_id: str, current_user: dict = Depends(get_current_user)):
    job_data = redis_client.hgetall(f"job:{job_id}")
    if not job_data:
        return JSONResponse(status_code=404, content={"error": "JOB_NOT_FOUND"})

    job = {k.decode('utf-8'): v.decode('utf-8') for k, v in job_data.items()}

    if job["submitted_by"] != current_user["username"]:
        return JSONResponse(status_code=403, content={"error": "UNAUTHORIZED_ACCESS"})

    if job["status"] != JobStatus.COMPLETED:
        return JSONResponse(status_code=400, content={"error": f"Job not complete. Status: {job['status']}"})

    return {
        "job_id": job_id,
        "result_url": job["result_url"],
        "block_urls": json.loads(job["block_urls"])
    }


@app.get("/result/{job_id}/block/{block_index}/audio", tags=["TTS Generation"])
async def get_block_audio(job_id: str, block_index: int, current_user: dict = Depends(get_current_user)):
    job_data = redis_client.hgetall(f"job:{job_id}")
    if not job_data:
        return JSONResponse(status_code=404, content={"error": "JOB_NOT_FOUND"})

    job = {k.decode('utf-8'): v.decode('utf-8') for k, v in job_data.items()}

    if job["submitted_by"] != current_user["username"]:
        return JSONResponse(status_code=403, content={"error": "UNAUTHORIZED_ACCESS"})

    if job["status"] != JobStatus.COMPLETED:
        return JSONResponse(status_code=400, content={"error": f"Job not complete. Status: {job['status']}"})

    block_path = os.path.join(TEMP_DIR, f"{job_id}_dl_block{block_index}.mp3")
    if not os.path.exists(block_path):
        return JSONResponse(status_code=404, content={"error": "FILE_NOT_FOUND"})

    return FileResponse(block_path, media_type="audio/mpeg", filename=f"block_{block_index}.mp3")


@app.get("/result/{job_id}/audio", tags=["TTS Generation"])
async def get_job_audio(job_id: str, current_user: dict = Depends(get_current_user)):
    job_data = redis_client.hgetall(f"job:{job_id}")
    if not job_data:
        return JSONResponse(status_code=404, content={"error": "JOB_NOT_FOUND"})

    job = {k.decode('utf-8'): v.decode('utf-8') for k, v in job_data.items()}

    if job["submitted_by"] != current_user["username"]:
        return JSONResponse(status_code=403, content={"error": "UNAUTHORIZED_ACCESS"})

    if job["status"] != JobStatus.COMPLETED:
        return JSONResponse(status_code=400, content={"error": f"Job not complete. Status: {job['status']}"})

    final_path = os.path.join(TEMP_DIR, f"{job_id}_final.mp3")
    if not os.path.exists(final_path):
        return JSONResponse(status_code=404, content={"error": "FILE_NOT_FOUND"})

    return FileResponse(final_path, media_type="audio/mpeg", filename="final_audio.mp3")