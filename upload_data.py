import os
import config
from data_manager import DataManager

def upload_all_data():
    dm = DataManager()
    data_dir = config.DATA_DIR
    
    print(f"📂 Uploading files from {data_dir}...")
    
    files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
    
    for filename in files:
        local_path = os.path.join(data_dir, filename)
        print(f"⬆️ Uploading {filename}...")
        success = dm.upload_file(local_path)
        if success:
            print(f"✅ Uploaded.")
        else:
            print(f"❌ Failed to upload {filename}.")

if __name__ == "__main__":
    upload_all_data()
