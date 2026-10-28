import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_FILE = os.path.join(BASE_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
SCOPES = ['https://www.googleapis.com/auth/drive']

def main():
    print("=" * 60, flush=True)
    print("   Google Drive Personal Account Authorization Setup", flush=True)
    print("=" * 60, flush=True)
    
    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"ERROR: Cannot find client_secret.json at: {CLIENT_SECRET_FILE}", flush=True)
        return

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    
    print("\nStarting local authentication listener...", flush=True)
    print("Your browser should open automatically. If not, click the link shown below.\n", flush=True)
    
    # port=0 lets the OS pick an available open port
    creds = flow.run_local_server(port=0, prompt='consent', access_type='offline')
    
    with open(TOKEN_FILE, 'w') as f:
        f.write(creds.to_json())

    print("\n" + "=" * 60, flush=True)
    print("SUCCESS! Google Drive authorized successfully!", flush=True)
    print(f"Token saved to: {TOKEN_FILE}", flush=True)
    print("=" * 60, flush=True)

if __name__ == '__main__':
    main()
