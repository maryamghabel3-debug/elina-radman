import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class ElinaStorage:
    """Adapter for Supabase Storage (private media bucket)."""

    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SECRET_KEY")
        self.bucket = os.environ.get("SUPABASE_BUCKET_NAME", "elina-media")

        if not url or not key:
            raise ValueError(
                "Supabase credentials (SUPABASE_URL, SUPABASE_SECRET_KEY) "
                "are missing from environment."
            )

        self.client: Client = create_client(url, key)

    def upload_file(
        self,
        local_file_path: str,
        destination_path: str,
        content_type: str | None = None,
    ) -> bool:
        """Upload a local file to the private bucket."""
        options = {"content-type": content_type} if content_type else {}
        with open(local_file_path, "rb") as f:
            self.client.storage.from_(self.bucket).upload(
                path=destination_path,
                file=f,
                file_options=options,
            )
        logger.info("Uploaded file to %s/%s", self.bucket, destination_path)
        return True

    def create_signed_url(self, file_path: str, expires_in_seconds: int = 3600) -> str:
        """Create a temporary signed URL (for Instagram Graph API delivery)."""
        response = self.client.storage.from_(self.bucket).create_signed_url(
            file_path, expires_in_seconds
        )
        if isinstance(response, dict):
            return response.get("signedURL") or response.get("signedUrl") or ""
        return str(response)

    def delete_file(self, file_path: str) -> bool:
        """Delete a file from the bucket."""
        self.client.storage.from_(self.bucket).remove([file_path])
        logger.info("Deleted file %s/%s", self.bucket, file_path)
        return True

    def list_files(self, folder: str = "") -> list:
        """List files inside a folder of the bucket."""
        return self.client.storage.from_(self.bucket).list(folder)

    def download_file(self, storage_path: str, local_path: str) -> str:
        data = self.client.storage.from_(self.bucket).download(storage_path)
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        with open(local_path, "wb") as f:
            if isinstance(data, bytes):
                f.write(data)
            else:
                f.write(bytes(data))
        return local_path
