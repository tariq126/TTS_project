from abc import ABC, abstractmethod

class StorageAdapter(ABC):
    """
    Abstract base class for a storage provider.
    This defines the contract that all storage implementations must follow.
    """

    @abstractmethod
    def upload(self, file_path: str, resource_type: str = "raw") -> str:
        """
        Uploads a file to the storage provider.

        Args:
            file_path (str): The local path to the file to upload.
            resource_type (str): The type of resource being uploaded (e.g., 'raw', 'image').

        Returns:
            str: The public URL of the uploaded file.
        """
        pass

    @abstractmethod
    def delete(self, file_url: str) -> None:
        """
        Deletes a file from the storage provider using its public URL.

        Args:
            file_url (str): The public URL of the file to delete.
        """
        pass

    @abstractmethod
    def get_signed_url(self, file_key: str) -> str:
        """
        Generates a temporary, signed URL for private access to a file.

        Args:
            file_key (str): The unique identifier or key of the file in storage.

        Returns:
            str: A temporary signed URL.
        """
        pass