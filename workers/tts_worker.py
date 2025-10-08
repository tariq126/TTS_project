import os
import json
import time
import requests
from celery import Celery
from datetime import timedelta
from pydub import AudioSegment
from integrations.storage import storage_manager
from dotenv import load_dotenv

from workers.providers import provider_factory
from utils.redis_client import redis_client
from utils.schemas import JobStatus

from utils.logger import logger
from .hooks import on_block_completed, on_job_completed, on_block_failed, on_job_failed

# --- Celery Initialization (Updated for Beat Scheduler) ---
celery_app = Celery(
    "tts_worker",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0")
)

# --- ## NEW: Add Beat Schedule Configuration ## ---
celery_app.conf.beat_schedule = {
    'cleanup-old-temp-files-every-hour': {
        'task': 'workers.tts_worker.cleanup_temp_files',
        'schedule': timedelta(hours=1),  # Runs every hour
        'args': (3600,)  # Files older than 3600 seconds (1 hour) will be deleted
    },
}
celery_app.conf.timezone = 'UTC'
# --- End New Config ---

TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)


# --- ## NEW: Cleanup Task ## ---
@celery_app.task
def cleanup_temp_files(max_age_seconds: int):
    """
    Scans the TEMP_DIR and deletes any files older than max_age_seconds.
    """
    logger.info(f"Running scheduled cleanup of files older than {max_age_seconds} seconds...")
    now = time.time()
    deleted_count = 0
    for filename in os.listdir(TEMP_DIR):
        file_path = os.path.join(TEMP_DIR, filename)
        try:
            if os.path.isfile(file_path):
                # Get the file's last modification time
                file_mtime = os.path.getmtime(file_path)
                # If the file is older than the max age, delete it
                if (now - file_mtime) > max_age_seconds:
                    os.remove(file_path)
                    deleted_count += 1
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
    logger.info(f"Cleanup complete. Deleted {deleted_count} old file(s).")
# --- End New Task ---


# --- Existing Celery Tasks (Unchanged) ---
@celery_app.task
def process_block(job_id, block_index, text, wait_after_ms, provider_name, voice_id):
    """
    Delegates audio generation to the correct provider, uploads the result,
    and updates the job status in Redis.
    """
    file_path = ""
    try:
        provider = provider_factory.get(provider_name)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' not found in factory.")

        file_path = os.path.join(TEMP_DIR, f"{job_id}_block{block_index}.wav")

        provider.generate_audio(text=text, voice_id=voice_id, output_path=file_path)

        upload_urls = storage_manager.upload(file_path, resource_type="raw")
        cloud_url = upload_urls["primary_url"] # The primary URL is still treated as the main one

        pipe = redis_client.pipeline()
        current_urls_str = redis_client.hget(f"job:{job_id}", "block_urls")
        current_urls = json.loads(current_urls_str)
        current_urls.append({
            "index": block_index,
            "urls": upload_urls,
            "local_path": file_path
        })
        pipe.hset(f"job:{job_id}", "block_urls", json.dumps(current_urls))
        pipe.hset(f"job:{job_id}", "status", JobStatus.PROCESSING)
        pipe.hincrby(f"job:{job_id}", "blocks_done", 1)
        results = pipe.execute()
        new_done_count = results[-1]

        project_id = redis_client.hget(f"job:{job_id}", "project_id").decode('utf-8')
        on_block_completed(job_id, project_id, block_index, urls=upload_urls)

        total_blocks = int(redis_client.hget(f"job:{job_id}", "blocks_total"))
        if new_done_count >= total_blocks:
            combine_blocks.delay(job_id)

    except Exception as e:
        redis_client.hset(f"job:{job_id}", "status", JobStatus.FAILED)
        error_message = f"Error processing block {block_index} for job {job_id} using provider '{provider_name}': {e}"
        logger.error(error_message) # Keep the original log for now
        on_block_failed(job_id, block_index, error=str(e))
    finally:
        # The local file is intentionally not deleted here.
        # The scheduled cleanup task will handle it later.
        pass


@celery_app.task
def combine_blocks(job_id):
    """Combines audio blocks from local files and finalizes the job."""
    final_path = os.path.join(TEMP_DIR, f"{job_id}_final.mp3")

    try:
        job_data = redis_client.hgetall(f"job:{job_id}")
        job = {k.decode('utf-8'): v.decode('utf-8') for k, v in job_data.items()}

        block_info = sorted(json.loads(job["block_urls"]), key=lambda x: x['index'])
        blocks_config = json.loads(job["blocks"])

        final_audio = AudioSegment.empty()

        for i, block_data in enumerate(block_info):
            local_path = block_data["local_path"]

            if not os.path.exists(local_path):
                raise FileNotFoundError(f"Local file not found for block {i}: {local_path}")

            audio_segment = AudioSegment.from_file(local_path)
            final_audio += audio_segment

            wait_ms = blocks_config[i]["wait_after_ms"]
            if wait_ms > 0:
                final_audio += AudioSegment.silent(duration=wait_ms)

        final_audio.export(final_path, format="mp3")

        upload_urls = storage_manager.upload(final_path, resource_type="raw")
        final_url = upload_urls["primary_url"] # The primary URL is still the main result

        redis_client.hset(f"job:{job_id}", "result_url", final_url)
        redis_client.hset(f"job:{job_id}", "status", JobStatus.COMPLETED)

        on_job_completed(job_id, final_urls=upload_urls)

    except Exception as e:
        redis_client.hset(f"job:{job_id}", "status", JobStatus.FAILED)
        error_message = f"Error combining blocks for job {job_id}: {e}"
        logger.error(error_message) # Keep the original log for now
        on_job_failed(job_id, error=str(e))
    finally:
        # The cleanup of individual block files is handled by the scheduled task.
        pass