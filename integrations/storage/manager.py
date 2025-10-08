from utils.logger import logger
from config import STORAGE_BACKEND, STORAGE_MIRRORING
from .cloudinary import CloudinaryAdapter
from .s3 import S3Adapter

class StorageManager:
    """
    Manages storage operations, including mirroring to a secondary provider.
    """
    def __init__(self):
        self.primary_provider = None
        self.secondary_provider = None

        # Initialize providers based on the configuration
        if STORAGE_BACKEND == 'cloudinary':
            self.primary_provider = CloudinaryAdapter()
            if STORAGE_MIRRORING:
                self.secondary_provider = S3Adapter()
        elif STORAGE_BACKEND == 's3':
            self.primary_provider = S3Adapter()
            if STORAGE_MIRRORING:
                self.secondary_provider = CloudinaryAdapter()
        else:
            raise ValueError(f"Unsupported storage backend: {STORAGE_BACKEND}")

        logger.info(f"StorageManager initialized. Primary: {STORAGE_BACKEND}")
        if self.secondary_provider:
            logger.info("Storage mirroring is enabled.")

    def upload(self, file_path: str, resource_type: str = "raw") -> dict:
        """
        Uploads a file to the primary storage provider and, if enabled, to the secondary provider.

        Args:
            file_path (str): The local path to the file to upload.
            resource_type (str): The type of resource being uploaded.

        Returns:
            dict: A dictionary containing the URLs from the primary and secondary uploads.
                  Example: {'primary_url': '...', 'secondary_url': '...'}
        """
        if not self.primary_provider:
            raise ConnectionError("Primary storage provider is not initialized.")

        # Upload to the primary provider
        primary_url = self.primary_provider.upload(file_path, resource_type)
        urls = {"primary_url": primary_url, "secondary_url": None}

        # If mirroring is enabled, upload to the secondary provider
        if self.secondary_provider:
            try:
                secondary_url = self.secondary_provider.upload(file_path, resource_type)
                urls["secondary_url"] = secondary_url
            except Exception as e:
                logger.error(f"Failed to upload to secondary storage provider: {e}")
                # We don't re-raise the exception because the primary upload succeeded.
                # The mirroring is for testing and should not block the main flow.

        return urls