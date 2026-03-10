import os
import shutil
from supabase import create_client, Client
import config

class DataManager:
    def __init__(self):
        url: str = config.SUPABASE_URL
        key: str = config.SUPABASE_KEY
        
        if not url or not key:
            raise ValueError("Supabase URL and Key must be set in .env file")

        self.supabase: Client = create_client(url, key)
        self.bucket_name = "geoflow-data" # Default bucket name

    def upload_file(self, local_path, storage_path=None):
        """
        Uploads a local file to Supabase Storage.
        :param local_path: Path to the local file.
        :param storage_path: Path in the bucket (defaults to filename).
        """
        if not os.path.exists(local_path):
            print(f"Error: File not found at {local_path}")
            return False

        if storage_path is None:
            storage_path = os.path.basename(local_path)

        try:
            with open(local_path, 'rb') as f:
                self.supabase.storage.from_(self.bucket_name).upload(
                    path=storage_path,
                    file=f,
                    file_options={"x-upsert": "true"}
                )
            print(f"✅ Uploaded {local_path} to {self.bucket_name}/{storage_path}")
            return True
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return False

    def download_file(self, storage_path, local_dir=config.DATA_DIR):
        """
        Downloads a file from Supabase Storage to a local directory.
        :param storage_path: Path in the bucket.
        :param local_dir: Local directory to save the file.
        """
        try:
            # Create local path
            filename = os.path.basename(storage_path)
            local_path = os.path.join(local_dir, filename)

            # Download data
            response = self.supabase.storage.from_(self.bucket_name).download(storage_path)
            
            with open(local_path, 'wb') as f:
                f.write(response)
            
            print(f"✅ Downloaded {storage_path} to {local_path}")
            return local_path
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return None

    def list_files(self):
        """List all files in the bucket."""
        try:
            res = self.supabase.storage.from_(self.bucket_name).list()
            return res
        except Exception as e:
            print(f"❌ List failed: {e}")
            return []
            
    def cleanup_local_file(self, local_path):
        """Deletes a local file to save space."""
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
                print(f"🗑️ Deleted local file: {local_path}")
                return True
        except Exception as e:
            print(f"❌ Cleanup failed: {e}")
            return False

if __name__ == "__main__":
    # Test execution
    try:
        dm = DataManager()
        print("Supabase connection successful.")
        # dm.list_files()
    except Exception as e:
        print(f"Initialization failed: {e}")
