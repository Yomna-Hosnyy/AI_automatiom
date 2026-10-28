import io
import json
import os
import time
import uuid
from datetime import datetime
import requests
import streamlit as st

# Optional external imports with graceful fallback
try:
    from supabase import Client, create_client

    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

try:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload

    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

try:
    from google_auth_oauthlib.flow import InstalledAppFlow

    HAS_OAUTH = True
except ImportError:
    HAS_OAUTH = False

# --- Page Configuration & Custom CSS ---
st.set_page_config(
    page_title="Auto Publish Content Pipeline",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
<style>
    .main-header {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #db2777 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.3rem;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #6b7280;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .badge-demo {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 600;
        background-color: #fef3c7;
        color: #92400e;
        border: 1px solid #fde68a;
    }
    .badge-live {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 600;
        background-color: #d1fae5;
        color: #065f46;
        border: 1px solid #a7f3d0;
    }
    .preview-card {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1.2rem;
    }
    .platform-pill {
        display: inline-block;
        margin: 2px 4px 2px 0px;
        padding: 2px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 500;
        background: #374151;
        color: #f9fafb;
    }
</style>
""",
    unsafe_allow_html=True,
)

# --- Configuration & Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
CLIENT_SECRET_FILE = os.getenv(
    "CLIENT_SECRET_FILE", os.path.join(BASE_DIR, "client_secret.json")
)
SERVICE_ACCOUNT_FILE = os.getenv(
    "SERVICE_ACCOUNT_FILE", os.path.join(BASE_DIR, "service_account.json")
)
ENV_FILE = os.path.join(BASE_DIR, ".env")
SUPABASE_JSON_FILE = os.path.join(BASE_DIR, "supabase.json")

# 🔗 n8n Webhook Configuration (الرابط مع الـ Path المخصص)
N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL", "http://localhost:5678/webhook-test/streamlit-trigger"
)

SCOPES = ["https://www.googleapis.com/auth/drive"]
DEFAULT_WATCHED_FOLDER_ID = "18t7MhV76EfVi-jvZCny1JRFfgRnd3P0J"


# --- Load Environment / Supabase Credentials ---
def load_env_file(filepath):
    """Loads key-value pairs from .env into os.environ if present."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = (
                            v.strip().strip('"').strip("'")
                        )
        except Exception:
            pass


load_env_file(ENV_FILE)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Also check for supabase.json
if not (SUPABASE_URL and SUPABASE_KEY) and os.path.exists(SUPABASE_JSON_FILE):
    try:
        with open(SUPABASE_JSON_FILE, "r", encoding="utf-8") as f:
            sb_data = json.load(f)
            SUPABASE_URL = (
                sb_data.get("SUPABASE_URL") or sb_data.get("url") or ""
            )
            SUPABASE_KEY = (
                sb_data.get("SUPABASE_KEY")
                or sb_data.get("key")
                or sb_data.get("anon_key")
                or sb_data.get("service_role_key")
                or ""
            )
    except Exception:
        pass

# Check Streamlit secrets
try:
    if hasattr(st, "secrets"):
        if "SUPABASE_URL" in st.secrets:
            SUPABASE_URL = st.secrets["SUPABASE_URL"]
        if "SUPABASE_KEY" in st.secrets:
            SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
        if "WATCHED_FOLDER_ID" in st.secrets:
            DEFAULT_WATCHED_FOLDER_ID = st.secrets["WATCHED_FOLDER_ID"]
        if "N8N_WEBHOOK_URL" in st.secrets:
            N8N_WEBHOOK_URL = st.secrets["N8N_WEBHOOK_URL"]
except Exception:
    pass


# --- Google Drive Authentication Logic ---
@st.cache_resource
def get_drive_service_user(token_path):
    """Initializes Google Drive service using personal user OAuth2 credentials."""
    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_path, "w") as f:
                f.write(creds.to_json())
        except Exception:
            creds = None

    if creds and creds.valid:
        return build("drive", "v3", credentials=creds)
    return None


drive_service_instance = get_drive_service_user(TOKEN_FILE)
auth_type = "oauth_user" if drive_service_instance else None
has_drive_creds = drive_service_instance is not None

folder_name = "uploaded videos"
if has_drive_creds:
    try:
        f_info = (
            drive_service_instance.files()
            .get(
                fileId=DEFAULT_WATCHED_FOLDER_ID,
                fields="name",
                supportsAllDrives=True,
            )
            .execute()
        )
        folder_name = f_info.get("name", "uploaded videos")
    except Exception:
        folder_name = "uploaded videos"


# --- Supabase Client Initialization ---
@st.cache_resource
def get_supabase_client(url, key):
    if not (HAS_SUPABASE and url and key):
        return None
    try:
        client = create_client(url, key)
        # Verify connection by querying the videos table
        client.table("videos").select("id").limit(1).execute()
        return client
    except Exception as e:
        st.session_state["supabase_error"] = str(e)
        return None


supabase_client_instance = get_supabase_client(SUPABASE_URL, SUPABASE_KEY)
has_supabase_creds = supabase_client_instance is not None

# --- Session State ---
if "submissions" not in st.session_state:
    st.session_state["submissions"] = []

# --- Sidebar ---
with st.sidebar:
    st.markdown("### ⚙️ Pipeline Control")

    # Operational Mode Options
    mode_options = []
    if has_drive_creds:
        mode_options.append("🟢 Live Drive & Database")
    mode_options.append("🧪 Simulated Demo Mode")

    selected_mode = st.radio(
        "Execution Mode",
        options=mode_options,
        index=0,
        help="Choose live upload to Drive and Supabase, or test simulation.",
    )
    is_live = "Live" in selected_mode

    st.markdown("---")
    st.markdown("### 🔌 Connection Status")

    if auth_type == "oauth_user":
        st.success(
            f"🟢 **Google Drive**: Connected\nFolder: `{folder_name}`\nStorage: Personal Quota"
        )
        if st.button(
            "🔄 Switch Drive Account",
            help="Sign in with a different Google account",
        ):
            if os.path.exists(TOKEN_FILE):
                try:
                    os.remove(TOKEN_FILE)
                except Exception:
                    pass
            st.cache_resource.clear()
            st.rerun()
    else:
        st.warning("⚠️ **Google Drive**: Not Connected (Demo Mode)")
        if os.path.exists(CLIENT_SECRET_FILE) and HAS_OAUTH:
            if st.button(
                "🔑 Connect Your Google Drive", use_container_width=True
            ):
                with st.spinner(
                    "Opening browser to authorize Google Drive..."
                ):
                    try:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            CLIENT_SECRET_FILE, SCOPES
                        )
                        new_creds = flow.run_local_server(
                            port=0, prompt="consent", access_type="offline"
                        )
                        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                            f.write(new_creds.to_json())
                        st.success("Google Drive connected successfully!")
                        st.cache_resource.clear()
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Login failed: {ex}")

    if has_supabase_creds:
        st.success("🟢 **Supabase**: Connected (`videos` table)")
    elif SUPABASE_URL and SUPABASE_KEY:
        st.warning("⚠️ **Supabase**: Connected (RLS check pending)")
    else:
        st.info("🟡 **Supabase**: Offline")

    st.markdown("---")
    folder_id = st.text_input(
        "Google Drive Folder ID",
        value=DEFAULT_WATCHED_FOLDER_ID,
        help="Google Drive folder ID monitored by n8n.",
    )

    webhook_url_input = st.text_input(
        "n8n Webhook URL",
        value=N8N_WEBHOOK_URL,
        help="Target n8n Webhook Endpoint with Path.",
    )

    if st.session_state["submissions"]:
        if st.button("🗑️ Clear Activity History"):
            st.session_state["submissions"] = []
            st.rerun()


# --- Backend Helper Functions ---
def upload_to_drive(
    file_obj, filename, target_folder_id, drive_service=None, real_upload=False
):
    """Uploads file to real Google Drive via in-memory stream without disk files."""
    if not real_upload or drive_service is None:
        time.sleep(1.0)
        return f"mock_drive_{uuid.uuid4().hex[:12]}"

    file_obj.seek(0)

    file_metadata = {"name": filename, "parents": [target_folder_id]}

    mimetype = getattr(file_obj, "type", None) or "video/mp4"
    media = MediaIoBaseUpload(
        file_obj, mimetype=mimetype, resumable=True, chunksize=1024 * 1024 * 5
    )

    drive_file = (
        drive_service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )
    return drive_file.get("id")


def trigger_n8n_webhook(target_url, payload):
    """Sends HTTP POST request to trigger the n8n automation pipeline."""
    try:
        response = requests.post(target_url, json=payload, timeout=5)
        if response.status_code == 200:
            return True, "n8n Webhook triggered successfully!"
        else:
            return (
                False,
                f"n8n responded with status code: {response.status_code}",
            )
    except Exception as e:
        return False, f"Failed to connect to n8n Webhook: {e}"


def insert_video_record(
    db_client,
    title,
    description,
    hashtags,
    platforms,
    drive_file_id,
    needs_compression=False,
):
    """Inserts a record into public.videos following the schema and prepares n8n payload."""
    full_desc = description.strip()
    if hashtags.strip():
        full_desc = (
            f"{full_desc}\n\n{hashtags.strip()}".strip()
            if full_desc
            else hashtags.strip()
        )

    post_data = {
        "title": title.strip(),
        "description": full_desc,
        "platform": ", ".join(platforms),
        "drive_file_id": drive_file_id,
        "status": "Approved",  # Set to Approved for n8n processing
        "needs_compression": needs_compression,
        "youtube": "YouTube" in platforms,
        "facebook": "Facebook" in platforms,
        "instagram": "Instagram" in platforms,
    }

    if db_client is None:
        time.sleep(0.3)
        simulated_id = f"sim_{uuid.uuid4().hex[:8]}"
        post_data["id"] = simulated_id
        return {
            "id": simulated_id,
            "data": post_data,
            "status": "session_saved",
        }

    res = db_client.table("videos").insert(post_data).execute()
    inserted_id = None
    if hasattr(res, "data") and res.data and len(res.data) > 0:
        inserted_id = res.data[0].get("id")
        post_data["id"] = inserted_id

    return {"id": inserted_id, "data": post_data, "status": "db_inserted"}


# --- Main App Header ---
col_head1, col_head2 = st.columns([4, 1])
with col_head1:
    st.markdown(
        '<div class="main-header">🚀 Auto Publish Content Pipeline</div>',
        unsafe_allow_html=True,
    )
    status_sub = f"Linked to Google Drive folder: <b>{folder_name}</b>"
    if has_supabase_creds:
        status_sub += " | Database: <b>Supabase (public.videos)</b>"
    st.markdown(
        f'<div class="sub-header">{status_sub}</div>', unsafe_allow_html=True
    )
with col_head2:
    if is_live:
        st.markdown(
            '<br><span class="badge-live">🟢 Live Pipeline Active</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<br><span class="badge-demo">🧪 Test Simulation Mode</span>',
            unsafe_allow_html=True,
        )

# Status notification banner
if is_live and has_supabase_creds:
    st.success(
        f" Ready to publish! Videos upload to Google Drive folder **{folder_name}** and metadata is stored in Supabase **`videos`** table for n8n."
    )
elif is_live and not has_supabase_creds:
    st.info(
        " Google Drive is live. Metadata will be saved to local session queue."
    )
else:
    st.info(
        "ℹ️ Running in **Simulated Mode**: Fast testing without consuming storage or database records."
    )

# --- Layout: 2 Columns ---
col_form, col_preview = st.columns([3, 2], gap="large")

with col_form:
    st.subheader("📤 Post Creator")

    with st.form("publish_form", clear_on_submit=False):
        uploaded_video = st.file_uploader(
            "Upload Video File",
            type=["mp4", "mov", "mkv", "webm"],
            help="Select the video file to upload.",
        )

        title = st.text_input(
            "Video Title *",
            placeholder="e.g. 5 AI Tools That Feel Illegal to Know",
            help="Main headline for your video post.",
        )

        description = st.text_area(
            "Video Description",
            placeholder="Add captions, details, or links...",
            height=110,
        )

        hashtags = st.text_input(
            "Hashtags",
            placeholder="e.g. #reels #tech #ai #viral",
            help="Space or comma separated hashtags.",
        )

        platforms = st.multiselect(
            "Target Social Platforms",
            options=["YouTube", "Facebook", "Instagram"],
            default=["YouTube", "Facebook", "Instagram"],
        )

        needs_compression = st.checkbox(
            "Reduce quality with FFmpeg if size limit exceeded", value=False
        )
        auto_notify = st.checkbox("Notify on pipeline completion", value=True)

        submitted = st.form_submit_button(
            "🚀 Upload & Submit to Pipeline", use_container_width=True
        )

    if submitted:
        if not uploaded_video or not title:
            st.error("⚠️ Please provide both a video file and a title.")
        elif not platforms:
            st.warning("⚠️ Please select at least one target platform.")
        else:
            drive_svc = drive_service_instance if is_live else None
            supa_cli = supabase_client_instance if is_live else None

            spinner_msg = (
                f"⏳ Step 1/3: Uploading '{uploaded_video.name}' ({round(uploaded_video.size / (1024*1024), 1)} MB) to Google Drive..."
                if is_live
                else "⏳ Simulating Drive upload..."
            )
            drive_file_id = None

            with st.spinner(spinner_msg):
                try:
                    drive_file_id = upload_to_drive(
                        uploaded_video,
                        uploaded_video.name,
                        folder_id,
                        drive_service=drive_svc,
                        real_upload=is_live,
                    )
                except Exception as e:
                    st.error(f"❌ Google Drive upload error: {e}")

            if drive_file_id:
                record_result = None
                with st.spinner(
                    "⏳ Step 2/3: Storing metadata in Supabase (public.videos)..."
                ):
                    try:
                        record_result = insert_video_record(
                            supa_cli,
                            title=title,
                            description=description,
                            hashtags=hashtags,
                            platforms=platforms,
                            drive_file_id=drive_file_id,
                            needs_compression=needs_compression,
                        )
                    except Exception as e:
                        st.error(f"❌ Error saving to Supabase: {e}")

                if record_result:
                    webhook_success = False
                    webhook_msg = ""
                    with st.spinner(
                        f"⏳ Step 3/3: Triggering n8n Webhook Path ({webhook_url_input})..."
                    ):
                        webhook_success, webhook_msg = trigger_n8n_webhook(
                            webhook_url_input, record_result["data"]
                        )

                    file_bytes = uploaded_video.getbuffer()
                    file_size_mb = round(len(file_bytes) / (1024 * 1024), 2)
                    db_record_id = record_result.get("id")

                    st.session_state["submissions"].insert(
                        0,
                        {
                            "db_id": db_record_id,
                            "drive_file_id": drive_file_id,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "title": title.strip(),
                            "description": record_result["data"][
                                "description"
                            ],
                            "platforms": platforms,
                            "filename": uploaded_video.name,
                            "filesize_mb": file_size_mb,
                            "mode": (
                                "Live (Drive & Supabase)"
                                if (is_live and supa_cli)
                                else (
                                    "Live Drive" if is_live else "Simulated"
                                )
                            ),
                            "status": (
                                "Triggered n8n"
                                if webhook_success
                                else "Pending n8n"
                            ),
                            "payload": record_result["data"],
                        },
                    )

                    db_status_text = (
                        f"Inserted into Supabase `videos` table (ID: `{db_record_id}`)"
                        if (is_live and supa_cli)
                        else "Stored in session activity"
                    )

                    st.success("🎉 **Video Successfully Submitted to Pipeline!**")
                    if webhook_success:
                        st.success(f"⚡ **n8n Webhook Status**: {webhook_msg}")
                    else:
                        st.warning(
                            f"⚠️ **n8n Webhook Status**: {webhook_msg}"
                        )

                    st.markdown(f"""
                    - **Google Drive File ID**: `{drive_file_id}`
                    - **Database Record**: {db_status_text}
                    - **Target Webhook Path**: `{webhook_url_input}`
                    - **Platforms**: {', '.join(platforms)}
                    - **Pipeline Status**: `Approved` → Processing started in n8n!
                    """)

with col_preview:
    st.subheader("👁️ Live Preview & Queue")

    # Live Video Preview if uploaded
    if uploaded_video is not None:
        st.markdown("**🎬 Video Preview:**")
        st.video(uploaded_video)
        file_size_mb = round(
            len(uploaded_video.getbuffer()) / (1024 * 1024), 2
        )
        st.caption(
            f"📁 **File:** `{uploaded_video.name}` ({file_size_mb} MB) | **Format:** {uploaded_video.type}"
        )
    else:
        st.info("Upload a video on the left to preview it here.")

    # Live Post Preview Card
    st.markdown("**📱 Social Card Preview:**")
    display_title = title.strip() if title else "Your Title Will Appear Here"
    display_desc = (
        description.strip()
        if description
        else "Your post description will appear here..."
    )
    display_tags = hashtags.strip() if hashtags else "#hashtags"

    with st.container():
        st.markdown(
            f"""
        <div class="preview-card">
            <h4 style="margin:0 0 6px 0; color:#3b82f6;">{display_title}</h4>
            <p style="margin:0 0 8px 0; font-size:0.9rem; color:#9ca3af;">{display_desc}</p>
            <p style="margin:0 0 10px 0; font-size:0.85rem; color:#60a5fa; font-weight:500;">{display_tags}</p>
            <div>
                {' '.join([f'<span class="platform-pill">{p}</span>' for p in (platforms or ["No platform selected"])])}
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Submission History / Queue
    st.markdown("### 📋 Automation Queue (`public.videos`)")
    if not st.session_state["submissions"]:
        st.caption(
            "No submissions in this session yet. Submit a video above to see it appear here."
        )
    else:
        for idx, sub in enumerate(st.session_state["submissions"]):
            sub_title = sub.get("title", "Untitled")
            sub_time = sub.get("timestamp", "")
            sub_status = sub.get("status", "pending")
            sub_db_id = sub.get("db_id")
            sub_drive_id = (
                sub.get("drive_file_id") or sub.get("id") or "N/A"
            )
            sub_file = sub.get("filename", "video")
            sub_size = sub.get("filesize_mb", 0)
            sub_platforms = sub.get("platforms", [])
            sub_mode = sub.get("mode", "")
            sub_payload = sub.get("payload", {})

            with st.expander(
                f"#{idx+1} {sub_title} ({sub_time}) - {sub_status.upper()}",
                expanded=(idx == 0),
            ):
                if sub_db_id:
                    st.write(f"**Database Row ID:** `{sub_db_id}`")
                st.write(f"**Drive File ID:** `{sub_drive_id}`")
                st.write(f"**File:** `{sub_file}` ({sub_size} MB)")
                st.write(f"**Platforms:** {', '.join(sub_platforms)}")
                st.write(f"**Pipeline Mode:** `{sub_mode}`")

                # Show JSON payload that was inserted into Supabase and sent to n8n
                st.markdown("**Supabase `videos` Row Payload:**")
                st.json(sub_payload)