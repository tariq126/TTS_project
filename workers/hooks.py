import json
from datetime import time, datetime, timezone
from config import GRAPHQL_ENABLED
from integrations.graphql_client import graphql_client
from utils.logger import logger
from utils.redis_client import redis_client

def on_block_completed(job_id: str, project_id: str, block_index: int, urls: dict, duration: float = 0):
    """
    Hook called when a single text block has been successfully processed.
    """
    logger.info(f"[HOOK] Block completed for job {job_id}, index {block_index}. URLs: {urls}")
    if GRAPHQL_ENABLED and graphql_client:
        # Get the block text from Redis
        job_data = redis_client.hgetall(f"job:{job_id}")
        job = {k.decode('utf-8'): v.decode('utf-8') for k, v in job_data.items()}
        blocks_config = json.loads(job["blocks"])
        block_text = blocks_config[block_index]["text"]

        # Format the timestamp
        created_at = datetime.now(timezone.utc).isoformat()

        graphql_client.insert_blocks(
            project_id=project_id,
            content=block_text,
            s3_url=urls.get("primary_url"),
            block_index=str(block_index),
            created_at=created_at
        )

def on_job_completed(job_id: str, final_urls: dict, duration: float = 0, size: int = 0):
    """
    Hook called when a job is fully completed. This updates the job status in GraphQL.
    """
    logger.info(f"[HOOK] Job completed for {job_id}. Final URLs: {final_urls}")
    if GRAPHQL_ENABLED and graphql_client:
        job_data = redis_client.hgetall(f"job:{job_id}")
        job = {k.decode('utf-8'): v.decode('utf-8') for k, v in job_data.items()}
        project_id = job.get("project_id")

        created_at = datetime.now(timezone.utc).isoformat()

        graphql_client.insert_blocks(
            project_id=project_id,
            content="merged_blocks",
            s3_url=final_urls.get("primary_url"),
            block_index="merged_blocks",
            created_at=created_at,
        )

def on_block_failed(job_id: str, block_index: int, error: str):
    """
    Hook called when a block fails. This marks the entire job as failed in GraphQL.
    """
    logger.error(f"[HOOK] Block failed for job {job_id}, index {block_index}. Error: {error}")
    if GRAPHQL_ENABLED and graphql_client:
        pass

def on_job_failed(job_id: str, error: str):
    """
    Hook called when the job combination fails. This marks the job as failed in GraphQL.
    """
    logger.error(f"[HOOK] Job failed for {job_id}. Error: {error}")
    if GRAPHQL_ENABLED and graphql_client:
        pass