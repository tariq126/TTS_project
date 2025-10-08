import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from .base import StorageAdapter
from utils.logger import logger
from core.config_loader import raw_config

class S3Adapter(StorageAdapter):
    """
    Storage adapter for S3-compatible services.
    Uses boto3 to interact with the S3 API.
    """
    def __init__(self):
        try:
            self.endpoint_url = raw_config.get("s3_endpoint_url")
            self.bucket_name = raw_config.get("s3_bucket_name")
            self.access_key = raw_config.get("s3_access_key")
            self.secret_key = raw_config.get("s3_secret_key")
            self.region = raw_config.get("s3_region")

            if not all([self.bucket_name, self.access_key, self.secret_key]):
                raise ValueError("S3 bucket name and credentials must be configured.")

            self.s3_client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            logger.info("S3Adapter initialized successfully.")
        except (ValueError, NoCredentialsError, PartialCredentialsError) as e:
            logger.error(f"Failed to initialize S3Adapter: {e}")
            self.s3_client = None # Ensure client is None if initialization fails

    def upload(self, file_path: str, resource_type: str = "raw") -> str:
        """
        Uploads a file to the configured S3 bucket.

        Args:
            file_path (str): The local path to the file to upload.
            resource_type (str): This argument is ignored for S3 but kept for interface compatibility.

        Returns:
            str: The public URL of the uploaded file.
        """
        if not self.s3_client:
            raise ConnectionError("S3 client is not initialized. Cannot upload.")

        object_name = file_path.split('/')[-1]
        try:
            logger.info(f"Uploading {file_path} to S3 bucket '{self.bucket_name}' with public-read ACL...")
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                object_name,
                ExtraArgs={'ACL': 'public-read'}
            )
            
            # Construct the public URL using the base URL from the config
            public_base_url = raw_config.get("public_s3_base_url")
            if not public_base_url:
                raise ValueError("public_s3_base_url is not configured.")

            url = f"{public_base_url}/{self.bucket_name}/{object_name}"
            
            logger.info(f"Successfully uploaded to S3: {url}")
            return url
        except Exception as e:
            logger.error(f"Failed to upload {file_path} to S3: {e}")
            raise

    def delete(self, file_url: str) -> None:
        """
        Deletes a file from S3.
        (Note: This is a placeholder implementation.)
        """
        logger.warning(f"Deletion requested for {file_url}, but this is not yet implemented for S3.")
        pass

    def get_signed_url(self, file_key: str) -> str:
        """
        Generates a presigned URL for a file in S3.
        (Note: This is a placeholder implementation.)
        """
        logger.warning(f"Signed URL requested for {file_key}, but this is not yet implemented for S3.")
        # A real implementation would look like this:
        # return self.s3_client.generate_presigned_url(
        #     'get_object',
        #     Params={'Bucket': self.bucket_name, 'Key': file_key},
        #     ExpiresIn=3600  # URL expires in 1 hour
        # )
        return ""