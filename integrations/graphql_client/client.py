import httpx
import uuid
from urllib.parse import urlparse
from utils.schemas import JobStatus
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError, after_log, retry_if_exception_type
from utils.logger import logger
from core.config_loader import raw_config
from datetime import datetime, timezone

# A simple logger for tenacity to show retry attempts
import logging
logging.basicConfig()
log = logging.getLogger(__name__)

class GraphQLClientAdapter:
    """
    Adapter for sending job status updates to a Hasura GraphQL endpoint with a retry mechanism.
    """

    CREATE_PROJECT_MUTATION = """
    mutation CreateProject($id: uuid!, $blocks: jsonb) {
      insert_Voice_Studio_Projects_one(object: {id: $id, blocks: $blocks}) {
        id
      }
    }
    """

    LINK_PROJECT_STORAGE_MUTATION = """
    mutation LinkProjectStorage($projectid: uuid!, $project_link: String!) {
      insert_library_Project_link_Storage_one(object: {projectid: $projectid, project_link: $project_link}) {
        id
      }
    }
    """

    INSERT_BLOCKS_MUTATION = """
    mutation InsertBlocks($project_id: uuid, $content: String, $s3_url: String, $block_index: String, $created_at: timestamptz) {
      insert_Voice_Studio_blocks(objects: {project_id: $project_id, content: $content, s3_url: $s3_url, block_index: $block_index, created_at: $created_at}) {
        affected_rows
        returning {
          id
          project_id
          content
          s3_url
          block_index
          created_at
        }
      }
    }
    """

    INSERT_VOICE_LINKS_MUTATION = """
    mutation InsertVioceLinks($block_id: uuid, $link_url: String) {
        insert_Voice_Studio_vioce_links(objects: {block_id: $block_id, link_url: $link_url}) {
            affected_rows
            returning {
                id
                block_id
                link_url
            }
        }
    }
    """

    def __init__(self, endpoint: str, admin_secret: str):
        if not endpoint or not admin_secret:
            logger.warning("GraphQL endpoint or admin secret is not configured. Client is disabled.")
            self.client = None
            return

        self.endpoint = endpoint
        self.headers = {
            "x-hasura-admin-secret": admin_secret,
            "Content-Type": "application/json",
        }
        self.client = httpx.Client(headers=self.headers, timeout=10.0)
        self.max_retries = int(raw_config.get("task_max_retries", 3))
        self.retry_delay = int(raw_config.get("task_retry_delay_seconds", 60))
        logger.info("GraphQLClientAdapter initialized successfully with retry policy.")

    def _execute_mutation_with_retry(self, mutation: str, variables: dict):
        """
        Helper function that wraps the GraphQL mutation call with a retry policy.
        """
        try:
            # Define the retry decorator dynamically with configured values
            retry_decorator = retry(
                wait=wait_exponential(multiplier=1, min=2, max=self.retry_delay),
                stop=stop_after_attempt(self.max_retries),
                retry=retry_if_exception_type(httpx.RequestError),
                after=after_log(log, logging.INFO)
            )
            
            @retry_decorator
            def decorated_mutation():
                payload = {"query": mutation, "variables": variables}
                response = self.client.post(self.endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
                if "errors" in data:
                    # Raise an exception to allow tenacity to catch it and possibly retry
                    raise Exception("Hasura error: " + str(data["errors"]))
                return data

            return decorated_mutation()

        except RetryError as e:
            # This block is executed after all retries have failed
            logger.critical(
                f"GraphQL mutation failed after {self.max_retries} attempts for job {variables.get('id')}. "
                f"Final error: {e}. This job needs manual investigation."
            )
        except Exception as e:
            logger.error(f"An unexpected, non-retriable error occurred during GraphQL mutation: {e}")

    def create_project(self, job_id: str, blocks: str):
        """
        Creates a project record in Hasura.
        """
        if not self.client:
            logger.warning("GraphQL client is not initialized. Skipping mutation.")
            return

        try:
            uuid.UUID(job_id)
        except ValueError as e:
            logger.error(f"Validation failed for job {job_id}. Aborting GraphQL write. Error: {e}")
            return

        variables = {"id": job_id, "blocks": blocks}
        self._execute_mutation_with_retry(self.CREATE_PROJECT_MUTATION, variables)

    def link_project_storage(self, job_id: str, audio_url: str):
        """
        Links a project to a storage URL in Hasura.
        """
        if not self.client:
            logger.warning("GraphQL client is not initialized. Skipping mutation.")
            return

        try:
            uuid.UUID(job_id)
            parsed_url = urlparse(audio_url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                raise ValueError(f"Invalid audio_url: {audio_url}")
        except ValueError as e:
            logger.error(f"Validation failed for job {job_id}. Aborting GraphQL write. Error: {e}")
            return

        variables = {"projectid": job_id, "project_link": audio_url}
        self._execute_mutation_with_retry(self.LINK_PROJECT_STORAGE_MUTATION, variables)

    def insert_blocks(self, project_id: str, content: str, s3_url: str, block_index: str, created_at: str):
        """
        Inserts a block into the Voice_Studio_Blocks table.
        """
        if not self.client:
            logger.warning("GraphQL client is not initialized. Skipping mutation.")
            return

        variables = {
            "project_id": project_id,
            "content": content,
            "s3_url": s3_url,
            "block_index": block_index,
            "created_at": created_at,
        }
        return self._execute_mutation_with_retry(self.INSERT_BLOCKS_MUTATION, variables)

    def insert_voice_links(self, block_id: str, link_url: str):
        """
        Inserts a voice link into the Voice_Studio_vioce_links table.
        """
        if not self.client:
            logger.warning("GraphQL client is not initialized. Skipping mutation.")
            return

        variables = {
            "block_id": block_id,
            "link_url": link_url,
        }
        self._execute_mutation_with_retry(self.INSERT_VOICE_LINKS_MUTATION, variables)