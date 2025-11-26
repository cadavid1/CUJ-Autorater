import streamlit as st
import json
import pandas as pd
import time
from datetime import datetime
from pathlib import Path

# Import new modules
from config import (
    MODELS, DEFAULT_MODEL, get_model_list, get_model_info,
    estimate_cost, format_cost, DEFAULT_SYSTEM_PROMPT, DRIVE_ENABLED
)
from video_processor import (
    validate_and_process_video, delete_video_file,
    format_duration, ensure_video_directory
)
from gemini_client import GeminiClient, GeminiAPIError, call_gemini_text
from storage import get_db
from logger import (log_video_upload, log_analysis_start,
                    log_analysis_complete, log_analysis_error, log_export)

# Google Drive integration (optional)
try:
    from drive_client import (
        DriveClient, DriveAPIError, is_drive_authenticated,
        get_drive_client, handle_drive_oauth_callback, logout_drive
    )
    DRIVE_AVAILABLE = DRIVE_ENABLED
except ImportError:
    DRIVE_AVAILABLE = False
    print("Google Drive integration not available. Install google-api-python-client to enable.")

# --- CONFIGURATION & STATE ---
st.set_page_config(page_title="UXR CUJ Analysis", page_icon="🧪", layout="wide")

# Ensure data directories exist
ensure_video_directory()

# Initialize database
db = get_db()

# Handle Drive OAuth callback if Drive is available
if DRIVE_AVAILABLE:
    handle_drive_oauth_callback()

SAMPLE_CUJS = [
    {"id": "CUJ-001", "task": "Sign Up", "expectation": "User finds the 'Sign Up' button on the homepage and completes the email form without validation errors."},
    {"id": "CUJ-002", "task": "Search for Product", "expectation": "User uses the search bar to find 'Wireless Headphones' and clicks on the first relevant result."},
    {"id": "CUJ-003", "task": "Checkout", "expectation": "User adds item to cart, proceeds to checkout, and enters shipping info successfully."}
]

SAMPLE_VIDEOS = [
    {"id": 1, "name": "Sample_Session_1.mp4", "status": "No file", "file_path": None, "duration": None, "size_mb": None, "description": "Upload a real video to analyze"}
]

# Initialize Session State
if "cujs" not in st.session_state:
    # Load from database, fall back to sample data
    loaded_cujs = db.get_cujs()
    if loaded_cujs.empty:
        st.session_state.cujs = pd.DataFrame(SAMPLE_CUJS)
        # Save sample data to database
        db.bulk_save_cujs(st.session_state.cujs)
    else:
        st.session_state.cujs = loaded_cujs

if "videos" not in st.session_state:
    # Load from database, fall back to sample data
    loaded_videos = db.get_videos()
    if loaded_videos.empty:
        st.session_state.videos = pd.DataFrame(SAMPLE_VIDEOS)
    else:
        st.session_state.videos = loaded_videos

if "results" not in st.session_state:
    # Load latest results from database
    st.session_state.results = db.get_latest_results()

if "api_key" not in st.session_state:
    # Load from database settings
    saved_key = db.get_setting("api_key", "")
    st.session_state.api_key = saved_key

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT

if "selected_model" not in st.session_state:
    # Load from database settings - check for custom default first, then fall back to DEFAULT_MODEL
    user_default = db.get_setting("default_model", DEFAULT_MODEL)
    saved_model = db.get_setting("selected_model", user_default)
    st.session_state.selected_model = saved_model

if "db_synced" not in st.session_state:
    st.session_state.db_synced = True

# --- HELPER FUNCTIONS ---

def get_confidence_indicator(score):
    """Generate monochrome confidence indicator based on score (1-5)

    Returns filled/empty circles to avoid color theory confusion with Pass/Fail status.
    High confidence (4-5): ●●●●● or ●●●●○
    Medium confidence (3): ●●●○○
    Low confidence (1-2): ●○○○○ or ●●○○○
    """
    filled = "●"
    empty = "○"

    if score >= 5:
        return f"{filled * 5}"
    elif score == 4:
        return f"{filled * 4}{empty}"
    elif score == 3:
        return f"{filled * 3}{empty * 2}"
    elif score == 2:
        return f"{filled * 2}{empty * 3}"
    else:  # score 1
        return f"{filled}{empty * 4}"

def get_friction_label(friction_score):
    """Generate descriptive friction label

    Makes friction scores immediately understandable:
    1-2: Smooth/Minimal friction
    3: Moderate friction
    4-5: High friction/Blocker
    """
    if friction_score <= 2:
        return "Smooth"
    elif friction_score == 3:
        return "Moderate"
    else:  # 4-5
        return "High"

def check_first_time_user():
    """Show welcome message for first-time users"""
    if 'welcome_shown' not in st.session_state:
        stats = db.get_statistics()
        is_first_time = (
            stats['total_analyses'] == 0 and
            not st.session_state.api_key
        )
        if is_first_time:
            st.info("""
            👋 **Welcome to UXR CUJ Analysis!**

            This tool uses AI to analyze user session videos against Critical User Journeys (CUJs).

            **Quick Start:**
            1. Add your Gemini API key in System Setup
            2. Define CUJs (test scenarios) or generate with AI
            3. Upload session recording videos
            4. Run analysis to evaluate each session

            💡 Follow the Workflow Progress tracker in the sidebar →
            """)
        st.session_state.welcome_shown = True

def render_progress_stepper():
    """Render workflow progress stepper in sidebar"""
    has_api_key = bool(st.session_state.api_key)
    has_cujs = not st.session_state.cujs.empty
    valid_videos = st.session_state.videos[
        st.session_state.videos.get('file_path', pd.Series(dtype='object')).notna() &
        (st.session_state.videos.get('status', pd.Series(dtype='str')).str.lower() == 'ready')
    ]
    has_videos = not valid_videos.empty
    has_results = bool(st.session_state.results)

    st.sidebar.markdown("### Workflow Progress")

    steps = [
        ("Setup", has_api_key, "Configure API key & model"),
        ("CUJs", has_cujs, "Define test scenarios"),
        ("Videos", has_videos, "Upload recordings"),
        ("Analyze", has_results, "Run AI analysis")
    ]

    for i, (label, is_complete, description) in enumerate(steps, 1):
        if is_complete:
            st.sidebar.success(f"**{i}. ✓ {label}**")
        else:
            st.sidebar.info(f"**{i}. ○ {label}**")
        st.sidebar.caption(f"   {description}")

    st.sidebar.markdown("---")

def call_gemini(api_key, model_name, prompt, system_instruction, response_mime_type="application/json"):
    """Legacy function for text-only Gemini calls (CUJ generation, reports, etc.)"""
    result = call_gemini_text(api_key, model_name, prompt, system_instruction, response_mime_type)

    if result and "error" in result:
        st.error(f"Gemini API Error: {result['error']}")
        return None

    if response_mime_type == "application/json":
        return result
    return result.get("text") if result else None

# --- SIDEBAR ---

st.sidebar.title("🧪 UXR CUJ Analysis")
st.sidebar.markdown("Powered by Gemini")
st.sidebar.warning("⚠️ This application is currently under development and not private. Don't test with any production data (run locally for privacy). Ask David Pearl if unsure how to get this deployed.")
st.sidebar.markdown("---")

# Workflow Progress Stepper
render_progress_stepper()

# Enhanced Status Indicators
st.sidebar.markdown("### System Status")

# API Key status
if st.session_state.api_key:
    st.sidebar.success("🔑 API Key: Connected")
else:
    st.sidebar.error("🔑 API Key: Not Set")
    st.sidebar.caption("   → Go to System Setup tab")

# CUJ status
cuj_count = len(st.session_state.cujs)
if cuj_count > 0:
    st.sidebar.success(f"📋 CUJs: {cuj_count} defined")
else:
    st.sidebar.warning("📋 CUJs: None defined")
    st.sidebar.caption("   → Go to Define CUJs tab")

# Video status
valid_video_count = len(st.session_state.videos[
    st.session_state.videos.get('file_path', pd.Series(dtype='object')).notna() &
    (st.session_state.videos.get('status', pd.Series(dtype='str')).str.lower() == 'ready')
])
if valid_video_count > 0:
    st.sidebar.success(f"📹 Videos: {valid_video_count} ready")
else:
    st.sidebar.warning("📹 Videos: None uploaded")
    st.sidebar.caption("   → Go to Upload Videos tab")

# Drive status
if DRIVE_AVAILABLE:
    st.sidebar.markdown("")
    if is_drive_authenticated():
        st.sidebar.info("📁 Drive: Connected")
        if st.sidebar.button("Logout from Drive", key="sidebar_logout"):
            logout_drive()
            st.rerun()
    else:
        st.sidebar.info("📁 Drive: Not connected")

st.sidebar.markdown("---")

# Keyboard Shortcuts & Tips
with st.sidebar.expander("⌨️ Shortcuts & Tips"):
    st.markdown("""
    **Navigation:**
    - Tab through fields with `Tab` key
    - Press `Enter` in forms to submit
    - Use `Esc` to close dialogs

    **Quick Tips:**
    - Check Workflow Progress above to see next steps
    - Green status = ready to proceed
    - Cost Estimator in Upload Videos tab
    - Low confidence results auto-expand for review

    **Getting Help:**
    - Hover over (?) icons for field help
    - Check empty states for guidance
    - Contact support if stuck
    """)

# --- MAIN CONTENT WITH HORIZONTAL TABS ---

# Show welcome message for first-time users
check_first_time_user()

tab_home, tab_setup, tab_cujs, tab_videos, tab_analysis = st.tabs([
    "🏠 Home",
    "⚙️ System Setup",
    "📋 Define CUJs",
    "📹 Upload Videos",
    "🚀 Run Analysis"
])

# --- TAB: HOME/OVERVIEW ---

with tab_home:
    st.header("Welcome to UXR CUJ Analysis")

    # Quick stats overview
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 CUJs", len(st.session_state.cujs))
    with col2:
        valid_video_count_home = len(st.session_state.videos[
            st.session_state.videos.get('file_path', pd.Series(dtype='object')).notna() &
            (st.session_state.videos.get('status', pd.Series(dtype='str')).str.lower() == 'ready')
        ])
        st.metric("📹 Videos", valid_video_count_home)
    with col3:
        stats_home = db.get_statistics()
        st.metric("🔬 Analyses", stats_home['total_analyses'])
    with col4:
        st.metric("💰 Total Cost", format_cost(stats_home['total_cost']))

    st.markdown("---")

    # Two-column layout for overview
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("### 🚀 Quick Start Guide")
        st.markdown("""
        **1. System Setup**
        - Add your Gemini API key
        - Select AI model (default: Gemini 2.5 Pro)
        - Optional: Connect Google Drive

        **2. Define CUJs**
        - Create Critical User Journeys manually
        - Or generate with AI
        - Import from CSV for bulk operations

        **3. Upload Videos**
        - Upload session recordings (MP4, MOV, AVI, WebM)
        - Max 900 MB, up to 90 minutes
        - Check cost estimates before uploading

        **4. Run Analysis**
        - AI evaluates videos against CUJs
        - Review confidence scores
        - Verify and override results
        - Export to CSV/JSON
        """)

        st.markdown("---")

        # System readiness check
        st.markdown("### ✅ System Readiness")
        if st.session_state.api_key:
            st.success("🔑 API Key configured")
        else:
            st.error("🔑 API Key missing - Go to System Setup")

        if len(st.session_state.cujs) > 0:
            st.success(f"📋 {len(st.session_state.cujs)} CUJ(s) defined")
        else:
            st.warning("📋 No CUJs - Go to Define CUJs")

        if valid_video_count_home > 0:
            st.success(f"📹 {valid_video_count_home} video(s) ready")
        else:
            st.warning("📹 No videos - Go to Upload Videos")

    with col_right:
        st.markdown("### 📊 Recent Activity")

        # Show recent analyses
        recent_df = db.get_analysis_results(limit=5)
        if not recent_df.empty:
            for _, row in recent_df.iterrows():
                status_emoji = "✅" if row['status'] == "Pass" else "❌" if row['status'] == "Fail" else "⚠️"
                st.caption(f"{status_emoji} **{row['cuj_task']}** - Friction: {row['friction_score']}/5")
                st.caption(f"   ↳ {row['video_name']} • {row['analyzed_at'][:10]}")
                st.markdown("")
        else:
            st.info("No analyses yet. Ready to start!")

        st.markdown("---")

        # Key features highlight
        st.markdown("### ✨ Key Features")
        st.markdown("""
        - **7 AI Models** - From fast/cheap to advanced reasoning
        - **Cost Transparency** - See estimates before analysis
        - **Confidence Scores** - AI rates its own certainty
        - **Human Verification** - Override and validate results
        - **Google Drive** - Import videos, export results
        - **Bulk Operations** - Import/export CUJs via CSV
        - **Rich Analytics** - Status breakdown, friction trends
        """)

        if stats_home['total_analyses'] > 0:
            st.markdown("---")
            st.markdown("### 📈 Performance Summary")
            if stats_home.get('status_counts'):
                total = sum(stats_home['status_counts'].values())
                for status, count in stats_home['status_counts'].items():
                    pct = (count / total * 100) if total > 0 else 0
                    st.caption(f"• **{status}**: {count} ({pct:.0f}%)")

# --- TAB: SYSTEM SETUP ---

with tab_setup:
    st.header("System Setup")
    
    with st.expander("Gemini Configuration", expanded=True):
        new_api_key = st.text_input("Gemini API Key", value=st.session_state.api_key, type="password")

        # Save API key if changed
        if new_api_key != st.session_state.api_key:
            st.session_state.api_key = new_api_key
            if new_api_key:  # Only save non-empty keys
                db.save_setting("api_key", new_api_key)

        # Get model list from config
        model_ids = get_model_list()
        model_display_names = [get_model_info(m)["display_name"] for m in model_ids]

        # Find current selection index
        try:
            current_index = model_ids.index(st.session_state.selected_model)
        except ValueError:
            current_index = 0
            st.session_state.selected_model = model_ids[0]

        selected_display = st.selectbox(
            "Select Model",
            model_display_names,
            index=current_index,
            help="Choose the Gemini model for analysis"
        )

        # Update session state with actual model ID
        selected_idx = model_display_names.index(selected_display)
        new_model = model_ids[selected_idx]

        # Save model if changed
        if new_model != st.session_state.selected_model:
            st.session_state.selected_model = new_model
            db.save_setting("selected_model", new_model)

        # Show model info
        model_info = get_model_info(st.session_state.selected_model)
        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"**Best for:** {model_info['best_for']}")
        with col2:
            if model_info["cost_per_m_tokens_input"] > 0:
                st.caption(f"**Cost:** ${model_info['cost_per_m_tokens_input']:.2f} / ${model_info['cost_per_m_tokens_output']:.2f} per M tokens")
            else:
                st.caption("**Cost:** Free during preview")

        # Default model preference
        st.markdown("---")
        current_default = db.get_setting("default_model", DEFAULT_MODEL)
        current_default_info = get_model_info(current_default)

        col1, col2 = st.columns([2, 1])
        with col1:
            st.caption(f"**Current Default:** {current_default_info['display_name']}")
        with col2:
            if st.session_state.selected_model != current_default:
                if st.button("Set as Default", key="set_default_btn"):
                    db.save_setting("default_model", st.session_state.selected_model)
                    st.success(f"Default model updated to {model_info['display_name']}")
                    st.rerun()
            else:
                st.caption("✓ This is default")

    with st.expander("System Prompt", expanded=True):
        st.session_state.system_prompt = st.text_area(
            "Analysis Instruction",
            value=st.session_state.system_prompt,
            height=200
        )

    # Google Drive OAuth
    if DRIVE_AVAILABLE:
        with st.expander("Google Drive Integration (Optional)", expanded=False):
            st.markdown("Connect to Google Drive to import videos and export results.")

            if is_drive_authenticated():
                st.success("✅ Connected to Google Drive")
                st.caption("You can now import videos from Drive and export results to Drive.")

                if st.button("Disconnect from Drive"):
                    logout_drive()
                    st.rerun()
            else:
                st.info("Sign in to access your Google Drive files")

                try:
                    _, auth_url = DriveClient.get_auth_url()
                    st.markdown(f"### [🔐 Sign in with Google]({auth_url})")
                    st.caption("You'll be redirected to Google to authorize UXR CUJ Analysis")
                except Exception as e:
                    st.error(f"Drive configuration error: {e}")
                    st.caption("Make sure you've configured Drive OAuth in `.streamlit/secrets.toml`")

# --- TAB: CUJ DATA SOURCE ---

with tab_cujs:
    st.header("CUJ Data Source")

    # Show helpful empty state if no CUJs
    if st.session_state.cujs.empty:
        st.info("""
        📋 **No CUJs defined yet**

        Critical User Journeys define the tasks you want to test.

        **Get started:**
        - Click "Generate with AI" to create sample CUJs
        - Or add rows manually in the table below

        **Example:** "Sign up for account" with expectation "User completes signup form without errors"
        """)

    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown("### Actions")
        
        # AI Generator
        with st.popover("✨ Generate with AI"):
            topic = st.text_input("Feature/Topic")
            if st.button("Generate CUJs"):
                if not st.session_state.api_key:
                    st.error("API Key required")
                else:
                    with st.spinner("Brainstorming..."):
                        prompt = f"""Generate 4 distinct Critical User Journeys (CUJs) for testing: "{topic}". 
                        Return strictly a JSON array of objects with keys: "id", "task", "expectation"."""
                        
                        new_data = call_gemini(
                            st.session_state.api_key, 
                            st.session_state.selected_model, 
                            prompt, 
                            "You are a QA Lead.", 
                            "application/json"
                        )
                        
                        if new_data:
                            # Append new data
                            new_df = pd.DataFrame(new_data)
                            if st.session_state.cujs.empty:
                                st.session_state.cujs = new_df
                            else:
                                st.session_state.cujs = pd.concat([st.session_state.cujs, new_df], ignore_index=True)
                            # Save to database
                            db.bulk_save_cujs(new_df)
                            st.rerun()

        st.markdown("")

        # Import/Export
        with st.popover("📁 Import/Export CUJs"):
            st.markdown("**Import from CSV**")
            st.caption("CSV must have columns: id, task, expectation")

            uploaded_csv = st.file_uploader("Upload CSV", type=['csv'], key="cuj_import")

            if uploaded_csv:
                try:
                    imported_df = pd.read_csv(uploaded_csv)
                    required_cols = {'id', 'task', 'expectation'}

                    if not required_cols.issubset(imported_df.columns):
                        st.error(f"Missing columns: {', '.join(required_cols - set(imported_df.columns))}")
                    else:
                        st.success(f"Found {len(imported_df)} CUJs")
                        if st.button("Import CUJs", type="primary"):
                            if st.session_state.cujs.empty:
                                st.session_state.cujs = imported_df[['id', 'task', 'expectation']]
                            else:
                                st.session_state.cujs = pd.concat([
                                    st.session_state.cujs,
                                    imported_df[['id', 'task', 'expectation']]
                                ], ignore_index=True)

                            db.bulk_save_cujs(imported_df)
                            st.success(f"Imported {len(imported_df)} CUJs!")
                            st.rerun()
                except Exception as e:
                    st.error(f"Import failed: {e}")

            st.markdown("---")
            st.markdown("**Export to CSV**")

            if not st.session_state.cujs.empty:
                csv_data = st.session_state.cujs.to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    data=csv_data,
                    file_name=f"cujs_export_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.caption("No CUJs to export")

    with col2:
        st.markdown("### Critical User Journeys")
        # Editable Data Table
        edited_df = st.data_editor(
            st.session_state.cujs,
            num_rows="dynamic",
            width='stretch',
            column_config={
                "id": "ID",
                "task": "Task Name",
                "expectation": st.column_config.TextColumn("Expected Behavior", width="large")
            }
        )
        # Save changes back to session state and database
        if not edited_df.equals(st.session_state.cujs):
            # Filter out rows with missing required fields before saving
            valid_rows = edited_df[
                edited_df['id'].notna() &
                edited_df['task'].notna() &
                edited_df['expectation'].notna() &
                (edited_df['id'].astype(str).str.strip() != '') &
                (edited_df['task'].astype(str).str.strip() != '') &
                (edited_df['expectation'].astype(str).str.strip() != '')
            ]

            # Show warning if any rows were invalid
            invalid_count = len(edited_df) - len(valid_rows)
            if invalid_count > 0:
                st.warning(f"⚠️ Skipped {invalid_count} row(s) with missing required fields (ID, Task, or Expectation)")

            # Update session state with valid rows only
            st.session_state.cujs = valid_rows.reset_index(drop=True)
            db.bulk_save_cujs(valid_rows)

# --- TAB: VIDEO ASSETS ---

with tab_videos:
    st.header("Video Assets")

    # Create tabs for local upload and Drive import
    if DRIVE_AVAILABLE and is_drive_authenticated():
        tab1, tab2 = st.tabs(["📤 Local Upload", "📁 Import from Drive"])
    else:
        tab1 = st.container()
        tab2 = None

    with tab1:
        st.info("💡 Upload real video files to analyze with Gemini. Videos will be validated and stored locally.")

        # Cost Estimator
        with st.expander("💰 Cost Estimator", expanded=False):
            st.markdown("**Estimate analysis costs before uploading**")

            col1, col2 = st.columns(2)
            with col1:
                duration_input = st.number_input(
                    "Video duration (minutes)",
                    min_value=1,
                    max_value=90,
                    value=5,
                    help="Enter expected video length"
                )
            with col2:
                model_info = get_model_info(st.session_state.selected_model)
                st.caption(f"**Using:** {model_info['display_name']}")

            cost_info = estimate_cost(duration_input * 60, st.session_state.selected_model)

            st.metric(
                "Estimated Cost per Video",
                format_cost(cost_info['total_cost']),
                help="Actual cost may vary based on exact video length and audio content"
            )

            st.caption(f"💡 For a {duration_input}-minute video • Based on {model_info['display_name']}")

            # Show examples
            st.markdown("**Quick Reference:**")
            for mins in [1, 5, 30]:
                cost = estimate_cost(mins * 60, st.session_state.selected_model)
                st.caption(f"• {mins} min video ≈ {format_cost(cost['total_cost'])}")

        st.markdown("---")

        # File Uploader
        uploaded_files = st.file_uploader(
            "Upload Videos",
            accept_multiple_files=True,
            type=['mp4', 'mov', 'avi', 'webm'],
            help="Upload video files (max 900MB, up to 90 minutes)"
        )

        if uploaded_files:
            # Track processed files in session state to avoid duplicates
            if "processed_files" not in st.session_state:
                st.session_state.processed_files = set()

            progress_container = st.container()
            files_to_process = []

            # Check which files are new
            for uploaded_file in uploaded_files:
                # Create unique identifier for file
                file_id = f"{uploaded_file.name}_{uploaded_file.size}"
                if file_id not in st.session_state.processed_files:
                    files_to_process.append((uploaded_file, file_id))

            if files_to_process:
                with progress_container:
                    for uploaded_file, file_id in files_to_process:
                        with st.spinner(f"Processing {uploaded_file.name}..."):
                            # Validate and process video
                            result = validate_and_process_video(uploaded_file)

                        if result["valid"]:
                            # Save to database first
                            video_id = db.save_video(
                                name=uploaded_file.name,
                                file_path=result["file_path"],
                                duration_seconds=result["metadata"].get("duration_seconds"),
                                file_size_mb=result["metadata"].get("file_size_mb"),
                                resolution=result["metadata"]["resolution"],
                                description=f"Duration: {format_duration(result['metadata']['duration_seconds'])}, Resolution: {result['metadata']['resolution']}"
                            )

                            # Add to videos dataframe
                            new_entry = {
                                "id": video_id,
                                "name": uploaded_file.name,
                                "status": "Ready",
                                "file_path": result["file_path"],
                                "duration": result["metadata"].get("duration_seconds"),
                                "size_mb": result["metadata"].get("file_size_mb"),
                                "description": f"Duration: {format_duration(result['metadata']['duration_seconds'])}, Resolution: {result['metadata']['resolution']}"
                            }

                            new_df = pd.DataFrame([new_entry])
                            if st.session_state.videos.empty:
                                st.session_state.videos = new_df
                            else:
                                st.session_state.videos = pd.concat([st.session_state.videos, new_df], ignore_index=True)

                            # Log upload
                            log_video_upload(
                                uploaded_file.name,
                                result["metadata"].get("file_size_mb"),
                                result["metadata"].get("duration_seconds")
                            )

                            # Show success with metadata
                            st.success(f"✅ {uploaded_file.name} uploaded successfully!")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Duration", format_duration(result["metadata"]["duration_seconds"]))
                            with col2:
                                st.metric("Size", f"{result['metadata']['file_size_mb']:.1f} MB")
                            with col3:
                                st.metric("Resolution", result["metadata"]["resolution"])

                            # Show cost estimate
                            cost_info = estimate_cost(
                                result["metadata"]["duration_seconds"],
                                st.session_state.selected_model
                            )
                            st.caption(f"📊 Estimated analysis cost: {format_cost(cost_info['total_cost'])} using {cost_info['model_display_name']}")

                            # Mark as processed
                            st.session_state.processed_files.add(file_id)

                        else:
                            # Show errors
                            st.error(f"❌ Failed to process {uploaded_file.name}")
                            for error in result["errors"]:
                                st.error(f"  • {error}")
                            # Mark as processed even if failed
                            st.session_state.processed_files.add(file_id)

                    # Rerun to update UI
                    time.sleep(1)
                    st.rerun()

    # Drive Import Tab
    if tab2:
        with tab2:
            st.info("📁 Browse and import videos from your Google Drive")

            drive_client = get_drive_client()
            if drive_client:
                # Initialize folder navigation state
                if 'drive_current_folder' not in st.session_state:
                    st.session_state.drive_current_folder = None  # None = root
                if 'drive_search_query' not in st.session_state:
                    st.session_state.drive_search_query = ""

                try:
                    # Drive link navigation
                    st.markdown("**🔗 Navigate by Link**")
                    link_input = st.text_input(
                        "Paste Drive link",
                        placeholder="https://drive.google.com/drive/folders/... or .../file/d/...",
                        help="Paste a Google Drive folder or file link to navigate directly",
                        key="drive_link_input"
                    )

                    if link_input:
                        from drive_client import DriveClient
                        parsed = DriveClient.parse_drive_url(link_input)

                        if parsed:
                            file_id, file_type = parsed
                            if file_type == 'folder':
                                # Navigate to folder
                                if st.button("📁 Go to this folder", type="primary"):
                                    st.session_state.drive_current_folder = file_id
                                    st.rerun()
                            elif file_type == 'file':
                                # Show single file for import
                                st.info("📹 File link detected - loading video...")
                                if 'drive_link_file_id' not in st.session_state:
                                    st.session_state.drive_link_file_id = None
                                if st.session_state.drive_link_file_id != file_id:
                                    st.session_state.drive_link_file_id = file_id
                                    st.rerun()
                        else:
                            st.error("Invalid Drive link. Please paste a valid Google Drive folder or file URL.")

                    st.markdown("---")

                    # Search and navigation controls
                    col_search, col_recursive = st.columns([3, 1])

                    with col_search:
                        search_input = st.text_input(
                            "Search videos",
                            value=st.session_state.drive_search_query,
                            placeholder="Search by filename...",
                            key="drive_search_input"
                        )
                        if search_input != st.session_state.drive_search_query:
                            st.session_state.drive_search_query = search_input
                            st.rerun()

                    with col_recursive:
                        recursive_search = st.checkbox(
                            "Search all folders",
                            value=False,
                            help="Search in all subfolders (may be slower)"
                        )

                    # Breadcrumb navigation
                    if 'drive_link_file_id' in st.session_state and st.session_state.drive_link_file_id:
                        # Show that we're viewing a specific file
                        col_breadcrumb, col_clear = st.columns([3, 1])
                        with col_breadcrumb:
                            st.caption("📹 Viewing file from link")
                        with col_clear:
                            if st.button("← Back to browsing"):
                                st.session_state.drive_link_file_id = None
                                st.rerun()
                    elif st.session_state.drive_current_folder:
                        # Get folder path for breadcrumbs
                        try:
                            folder_path = drive_client.get_folder_path(st.session_state.drive_current_folder)

                            # Build breadcrumb
                            breadcrumb_parts = []
                            if st.button("🏠 My Drive", key="breadcrumb_root"):
                                st.session_state.drive_current_folder = None
                                st.rerun()

                            for i, folder in enumerate(folder_path):
                                st.caption(" → " + folder['name'])
                        except:
                            st.caption(f"📁 Current folder")
                            if st.button("← Back to My Drive"):
                                st.session_state.drive_current_folder = None
                                st.rerun()
                    else:
                        st.caption("📁 My Drive")

                    st.markdown("---")

                    # Show folders in current directory (unless searching all folders)
                    if not recursive_search and not st.session_state.drive_search_query:
                        with st.spinner("Loading folders..."):
                            folders = drive_client.list_folders(
                                parent_folder_id=st.session_state.drive_current_folder,
                                page_size=20
                            )

                        if folders:
                            st.markdown("**📁 Folders**")
                            folder_cols = st.columns(min(len(folders), 4))
                            for idx, folder in enumerate(folders[:8]):  # Show max 8 folders
                                with folder_cols[idx % 4]:
                                    if st.button(f"📁 {folder['name']}", key=f"folder_{folder['id']}", use_container_width=True):
                                        st.session_state.drive_current_folder = folder['id']
                                        st.rerun()

                            if len(folders) > 8:
                                st.caption(f"...and {len(folders) - 8} more folders")

                            st.markdown("---")

                    # List video files from current folder, search results, or specific file link
                    with st.spinner("Loading videos..."):
                        # Check if a specific file was requested via link
                        if 'drive_link_file_id' in st.session_state and st.session_state.drive_link_file_id:
                            try:
                                # Fetch specific file metadata
                                file_metadata = drive_client.service.files().get(
                                    fileId=st.session_state.drive_link_file_id,
                                    fields='id, name, mimeType, size, modifiedTime, webViewLink'
                                ).execute()

                                # Check if it's a video file
                                if any(mime in file_metadata.get('mimeType', '') for mime in drive_client.VIDEO_MIME_TYPES):
                                    video_files = [file_metadata]
                                    st.info(f"📹 Showing file from link: {file_metadata['name']}")
                                else:
                                    st.error("The linked file is not a supported video format.")
                                    video_files = []
                            except Exception as e:
                                st.error(f"Could not load file from link: {str(e)}")
                                video_files = []
                                st.session_state.drive_link_file_id = None
                        else:
                            # Normal browsing/search
                            video_files = drive_client.list_video_files(
                                page_size=50,
                                folder_id=st.session_state.drive_current_folder if not recursive_search else None,
                                search_query=st.session_state.drive_search_query if st.session_state.drive_search_query else None,
                                recursive=recursive_search
                            )

                    if video_files:
                        if not ('drive_link_file_id' in st.session_state and st.session_state.drive_link_file_id):
                            st.success(f"Found {len(video_files)} video(s) in your Drive")

                        # Display videos with import button
                        for file in video_files:
                            with st.expander(f"📹 {file['name']}", expanded=False):
                                col1, col2, col3 = st.columns([2, 1, 1])

                                with col1:
                                    size_mb = int(file.get('size', 0)) / (1024*1024)
                                    st.caption(f"**Size:** {size_mb:.1f} MB")
                                    modified = file.get('modifiedTime', 'Unknown')[:10]
                                    st.caption(f"**Modified:** {modified}")

                                with col2:
                                    if st.button("View in Drive", key=f"view_{file['id']}", width='stretch'):
                                        st.write(f"[Open]({file.get('webViewLink', '#')})")

                                with col3:
                                    if st.button("Import", key=f"import_{file['id']}", type="primary", width='stretch'):
                                        try:
                                            # Create destination path
                                            from config import DRIVE_VIDEO_STORAGE_PATH
                                            Path(DRIVE_VIDEO_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
                                            dest_path = Path(DRIVE_VIDEO_STORAGE_PATH) / file['name']

                                            # Download with progress
                                            progress_bar = st.progress(0)
                                            status_text = st.empty()

                                            def update_progress(percent):
                                                progress_bar.progress(percent / 100)
                                                status_text.text(f"Downloading: {percent}%")

                                            drive_client.download_file(
                                                file['id'],
                                                str(dest_path),
                                                progress_callback=update_progress
                                            )

                                            progress_bar.progress(100)
                                            status_text.text("Extracting metadata...")

                                            # Extract video metadata
                                            from video_processor import extract_video_metadata
                                            metadata = extract_video_metadata(str(dest_path))

                                            # Save to database
                                            video_id = db.save_drive_video(
                                                name=file['name'],
                                                drive_file_id=file['id'],
                                                drive_web_link=file.get('webViewLink', ''),
                                                file_path=str(dest_path),
                                                duration_seconds=metadata['duration_seconds'],
                                                file_size_mb=size_mb,
                                                resolution=metadata['resolution'],
                                                description=f"Imported from Drive - Duration: {format_duration(metadata['duration_seconds'])}, Resolution: {metadata['resolution']}"
                                            )

                                            # Add to session state
                                            new_entry = {
                                                "id": video_id,
                                                "name": file['name'],
                                                "status": "Ready",
                                                "file_path": str(dest_path),
                                                "duration": metadata['duration_seconds'],
                                                "size_mb": size_mb,
                                                "description": f"From Drive - {format_duration(metadata['duration_seconds'])}, {metadata['resolution']}"
                                            }

                                            new_df = pd.DataFrame([new_entry])
                                            if st.session_state.videos.empty:
                                                st.session_state.videos = new_df
                                            else:
                                                st.session_state.videos = pd.concat([st.session_state.videos, new_df], ignore_index=True)

                                            # Log import
                                            log_video_upload(file['name'], size_mb, metadata['duration_seconds'])

                                            st.success(f"✅ Imported {file['name']} from Drive!")
                                            time.sleep(1)
                                            st.rerun()

                                        except Exception as e:
                                            st.error(f"Import failed: {str(e)}")

                    else:
                        st.info("No videos found in your Drive. Upload videos to Drive first.")

                except DriveAPIError as e:
                    st.error(f"Drive error: {e}")
                    st.caption("Try refreshing the page or reconnecting to Drive.")
                except Exception as e:
                    st.error(f"Unexpected error: {e}")
            else:
                st.error("Failed to connect to Drive. Please check your connection in System Setup.")

    st.markdown("### Manage Videos")
    st.caption("Upload videos above, then manage them below. Delete videos you no longer need to save space.")

    if not st.session_state.videos.empty:
        # View toggle
        col_view, col_bulk = st.columns([2, 3])
        with col_view:
            view_mode = st.radio(
                "View mode",
                ["Cards", "Table"],
                horizontal=True,
                label_visibility="collapsed",
                key="video_view_mode"
            )

        with col_bulk:
            # Bulk actions only shown in table view
            if view_mode == "Table" and 'selected_videos' in st.session_state and st.session_state.selected_videos:
                if st.button(f"Delete {len(st.session_state.selected_videos)} selected video(s)", type="secondary"):
                    st.session_state.confirm_bulk_delete = True

        # Handle bulk delete confirmation
        if st.session_state.get('confirm_bulk_delete', False):
            st.warning(f"⚠️ Delete {len(st.session_state.selected_videos)} selected video(s)? This cannot be undone.")
            col_cancel, col_confirm = st.columns(2)
            with col_cancel:
                if st.button("Cancel Bulk Delete", key="cancel_bulk", use_container_width=True):
                    st.session_state.confirm_bulk_delete = False
                    st.rerun()
            with col_confirm:
                if st.button("Confirm Bulk Delete", key="confirm_bulk", type="secondary", use_container_width=True):
                    deleted_count = 0
                    for video_id in st.session_state.selected_videos:
                        # Find video row
                        video_row = st.session_state.videos[st.session_state.videos['id'] == video_id]
                        if not video_row.empty:
                            # Delete file if exists
                            file_path = video_row.iloc[0].get('file_path')
                            if file_path:
                                delete_video_file(file_path)

                            # Delete from database
                            db.delete_video(video_id)

                            # Remove from dataframe
                            st.session_state.videos = st.session_state.videos[
                                st.session_state.videos['id'] != video_id
                            ].reset_index(drop=True)
                            deleted_count += 1

                    st.session_state.confirm_bulk_delete = False
                    st.session_state.selected_videos = []
                    st.success(f"Deleted {deleted_count} video(s)")
                    st.rerun()

        st.markdown("---")

        # Display based on view mode
        if view_mode == "Cards":
            # Card view (original implementation)
            for idx, row in st.session_state.videos.iterrows():
                with st.expander(f"📹 {row['name']} - {row['status']}", expanded=False):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.markdown(f"**Status:** {row['status']}")
                        if row.get('description'):
                            st.markdown(f"**Details:** {row['description']}")
                        if row.get('file_path') and Path(row['file_path']).exists():
                            st.markdown(f"**File:** `{row['file_path']}`")

                    with col2:
                        # Delete button with confirmation
                        if st.button("Delete", key=f"delete_{row['id']}", type="secondary"):
                            st.session_state[f"confirm_delete_{row['id']}"] = True

                    # Confirmation dialog
                    if st.session_state.get(f"confirm_delete_{row['id']}", False):
                        st.warning("⚠️ Delete this video? This cannot be undone.")
                        col_cancel, col_confirm = st.columns(2)
                        with col_cancel:
                            if st.button("Cancel", key=f"cancel_{row['id']}", use_container_width=True):
                                st.session_state[f"confirm_delete_{row['id']}"] = False
                                st.rerun()
                        with col_confirm:
                            if st.button("Confirm Delete", key=f"confirm_{row['id']}", type="secondary", use_container_width=True):
                                # Delete file if exists
                                if row.get('file_path'):
                                    delete_video_file(row['file_path'])

                                # Delete from database
                                db.delete_video(row['id'])

                                # Remove from dataframe
                                st.session_state.videos = st.session_state.videos[
                                    st.session_state.videos['id'] != row['id']
                                ].reset_index(drop=True)

                                st.session_state[f"confirm_delete_{row['id']}"] = False
                                st.success(f"Deleted {row['name']}")
                                st.rerun()

        else:  # Table view
            # Initialize selected videos in session state
            if 'selected_videos' not in st.session_state:
                st.session_state.selected_videos = []

            # Create table with checkboxes
            table_data = []
            for idx, row in st.session_state.videos.iterrows():
                is_selected = row['id'] in st.session_state.selected_videos

                # Create row with checkbox
                col_check, col_name, col_status, col_size, col_duration = st.columns([0.5, 3, 1.5, 1.5, 1.5])

                with col_check:
                    if st.checkbox("", value=is_selected, key=f"check_{row['id']}", label_visibility="collapsed"):
                        if row['id'] not in st.session_state.selected_videos:
                            st.session_state.selected_videos.append(row['id'])
                    else:
                        if row['id'] in st.session_state.selected_videos:
                            st.session_state.selected_videos.remove(row['id'])

                with col_name:
                    st.markdown(f"📹 **{row['name']}**")

                with col_status:
                    status_emoji = "✅" if row['status'].lower() == 'ready' else "⏳"
                    st.markdown(f"{status_emoji} {row['status']}")

                with col_size:
                    if row.get('size_mb'):
                        st.caption(f"{row['size_mb']:.1f} MB")
                    else:
                        st.caption("—")

                with col_duration:
                    if row.get('duration'):
                        st.caption(format_duration(row['duration']))
                    else:
                        st.caption("—")
    else:
        st.info("""
        📹 **No videos uploaded**

        Upload user session recordings to analyze.

        **Supported:** MP4, MOV, AVI, WebM
        **Max size:** 900 MB per video
        **Max duration:** 90 minutes

        💡 Use the Cost Estimator above to preview costs
        """)

# --- TAB: ANALYSIS DASHBOARD ---

with tab_analysis:
    st.header("Analysis Dashboard")

    # Check if we have videos with valid file paths
    valid_videos = st.session_state.videos[
        st.session_state.videos['file_path'].notna() &
        (st.session_state.videos['status'].str.lower() == 'ready')
    ]

    # Top stats banner
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.metric("CUJs Defined", len(st.session_state.cujs))
    with col_s2:
        st.metric("Videos Ready", len(valid_videos))
    with col_s3:
        if st.session_state.results:
            st.metric("Analyses Complete", len(st.session_state.results))
        else:
            st.metric("Analyses Complete", 0)
    with col_s4:
        stats = db.get_statistics()
        st.metric("Total Spent", format_cost(stats['total_cost']))

    st.markdown("---")

    col_actions, col_summary = st.columns([1, 2.5])

    with col_actions:
        st.markdown("### Actions")

        # Show status
        if not st.session_state.api_key:
            st.warning("⚠️ No API Key")
        elif valid_videos.empty:
            st.warning("⚠️ No videos uploaded")
        elif st.session_state.cujs.empty:
            st.warning("⚠️ No CUJs defined")
        else:
            st.success("✅ Ready to analyze")

        st.markdown("")  # Spacing

        # Run Analysis button (PRIMARY ACTION - at top)
        if st.button("Run Analysis", type="primary", use_container_width=True):
            if not st.session_state.api_key:
                st.error("Missing API Key")
            elif valid_videos.empty:
                st.error("No videos with valid files. Please upload videos first.")
            elif st.session_state.cujs.empty:
                st.error("No CUJs defined. Please add CUJs first.")
            else:
                # Pre-flight validation
                validation_errors = []

                # Check API key format
                if not st.session_state.api_key.startswith("AIza"):
                    validation_errors.append("⚠️ API key doesn't look valid (should start with 'AIza')")

                # Check video file paths
                missing_videos = []
                for _, video in valid_videos.iterrows():
                    if not Path(video['file_path']).exists():
                        missing_videos.append(video['name'])

                if missing_videos:
                    validation_errors.append(f"⚠️ Missing video files: {', '.join(missing_videos[:3])}")

                if validation_errors:
                    for error in validation_errors:
                        st.warning(error)
                    st.stop()

                # Initialize Gemini client
                try:
                    client = GeminiClient(st.session_state.api_key)
                except GeminiAPIError as e:
                    st.error(f"Failed to initialize Gemini client: {str(e)}")
                    st.stop()

                progress_bar = st.progress(0)
                status_text = st.empty()
                stage_text = st.empty()
                error_container = st.container()
                results_buffer = {}

                cujs = st.session_state.cujs.to_dict('records')
                videos = valid_videos.to_dict('records')

                total_cost = 0.0
                successes = 0
                failures = 0
                errors_list = []

                for i, cuj in enumerate(cujs):
                    status_text.markdown(f"**Analyzing:** {cuj['task']} ({i+1}/{len(cujs)})")

                    # Check for manual mapping first
                    if cuj['id'] in st.session_state.get('cuj_video_mapping', {}):
                        video_id = st.session_state.cuj_video_mapping[cuj['id']]
                        video = next((v for v in videos if v['id'] == video_id), videos[i % len(videos)])
                    else:
                        # Round robin video assignment
                        video = videos[i % len(videos)]

                    # Check if video file exists
                    if not Path(video['file_path']).exists():
                        error_msg = f"Video file not found: {video['file_path']}"
                        with error_container:
                            st.error(f"❌ {cuj['task']}: {error_msg}")
                        errors_list.append(f"{cuj['task']}: {error_msg}")
                        failures += 1
                        log_analysis_error(cuj['id'], error_msg)
                        continue

                    # Create prompt for video analysis
                    prompt = f"""
                    Analyze this user session video against the following Critical User Journey (CUJ):

                    **CUJ Task:** {cuj['task']}
                    **Expected Behavior:** {cuj['expectation']}

                    Watch the video carefully and evaluate:
                    1. Did the user successfully complete the task?
                    2. What friction points did they encounter?
                    3. Rate the friction on a scale of 1-5 (1=Smooth, 5=Blocker)
                    4. Provide specific observations and recommendations

                    Be specific about what you observe in the video.
                    """

                    # Progress callback
                    def update_progress(stage, prog):
                        stage_text.text(f"📍 {stage}")
                        base_progress = i / len(cujs)
                        progress_increment = prog / len(cujs)
                        progress_bar.progress(base_progress + progress_increment)

                    try:
                        # Log analysis start
                        log_analysis_start(cuj['id'], video['name'], st.session_state.selected_model)

                        # Analyze video
                        analysis = client.analyze_video_with_retry(
                            video['file_path'],
                            prompt,
                            st.session_state.system_prompt,
                            st.session_state.selected_model,
                            progress_callback=update_progress
                        )

                        if analysis:
                            # Add metadata
                            analysis['video_used'] = video['name']
                            analysis['video_id'] = video['id']
                            analysis['model_used'] = st.session_state.selected_model

                            # Calculate cost
                            cost_info = estimate_cost(video['duration'], st.session_state.selected_model)
                            analysis['cost'] = cost_info['total_cost']
                            total_cost += cost_info['total_cost']

                            # Extract new fields with defaults for backwards compatibility
                            confidence_score = analysis.get('confidence_score')
                            key_moments = analysis.get('key_moments')
                            # Always convert key_moments list to JSON string for database storage
                            if key_moments:
                                if isinstance(key_moments, list):
                                    key_moments = json.dumps(key_moments)
                                elif not isinstance(key_moments, str):
                                    key_moments = json.dumps([key_moments])
                            else:
                                key_moments = None

                            # Save to database
                            db.save_analysis(
                                cuj_id=cuj['id'],
                                video_id=video['id'],
                                model_used=st.session_state.selected_model,
                                status=analysis['status'],
                                friction_score=analysis['friction_score'],
                                observation=analysis['observation'],
                                recommendation=analysis.get('recommendation', ''),
                                cost=cost_info['total_cost'],
                                raw_response=json.dumps(analysis),
                                confidence_score=confidence_score,
                                key_moments=key_moments
                            )

                            results_buffer[cuj['id']] = analysis

                            # Log completion
                            log_analysis_complete(
                                cuj['id'],
                                analysis['status'],
                                analysis['friction_score'],
                                cost_info['total_cost']
                            )

                            successes += 1

                    except GeminiAPIError as e:
                        error_msg = str(e)
                        log_analysis_error(cuj['id'], error_msg)
                        with error_container:
                            st.error(f"❌ {cuj['task']}: {error_msg}")
                        errors_list.append(f"{cuj['task']}: {error_msg}")
                        failures += 1
                        # Continue with next CUJ even if this one fails
                        continue
                    except Exception as e:
                        error_msg = f"Unexpected error: {str(e)}"
                        log_analysis_error(cuj['id'], error_msg)
                        with error_container:
                            st.error(f"❌ {cuj['task']}: {error_msg}")
                        errors_list.append(f"{cuj['task']}: {error_msg}")
                        failures += 1
                        continue

                    progress_bar.progress((i + 1) / len(cujs))

                # Save results even if some failed
                st.session_state.results = results_buffer

                # Show summary
                progress_bar.progress(1.0)
                if failures == 0:
                    status_text.markdown(f"✅ **Analysis Complete!** All {successes} analyses succeeded.")
                else:
                    status_text.markdown(f"⚠️ **Analysis Complete:** {successes} succeeded, {failures} failed")

                stage_text.markdown(f"💰 Total cost: {format_cost(total_cost)}")

                # Show error summary if there were failures
                if errors_list:
                    with error_container:
                        st.warning(f"### ⚠️ {failures} Analysis Failed")
                        for error in errors_list[:5]:  # Show first 5 errors
                            st.caption(f"• {error}")
                        if len(errors_list) > 5:
                            st.caption(f"... and {len(errors_list) - 5} more errors (check logs)")

                # Ask about video cleanup
                st.session_state.show_cleanup_dialog = True
                time.sleep(1)
                st.rerun()

        # Video cleanup dialog
        if st.session_state.get('show_cleanup_dialog', False):
            st.markdown("---")
            st.info("### 🗑️ Clean Up Videos?")
            st.markdown("Analysis complete! Would you like to delete the analyzed videos to save disk space?")

            col_keep, col_delete = st.columns(2)
            with col_keep:
                if st.button("Keep Videos", use_container_width=True):
                    st.session_state.show_cleanup_dialog = False
                    st.rerun()

            with col_delete:
                if st.button("Delete Analyzed Videos", type="secondary", use_container_width=True):
                    # Delete videos that were analyzed
                    videos_to_delete = valid_videos.to_dict('records')
                    deleted_count = 0

                    for video in videos_to_delete:
                        if video.get('file_path'):
                            if delete_video_file(video['file_path']):
                                deleted_count += 1

                    st.success(f"Deleted {deleted_count} video file(s)")
                    st.session_state.show_cleanup_dialog = False
                    time.sleep(1)
                    st.rerun()

        st.markdown("---")

        # Statistics (detailed breakdown)
        with st.expander("📊 Statistics"):
            stats = db.get_statistics()
            if stats['total_analyses'] > 0:
                st.metric("Total Analyses", stats['total_analyses'])
                st.metric("Total Cost", format_cost(stats['total_cost']))
                st.metric("Avg Friction", f"{stats['avg_friction_score']:.1f}/5")

                if stats['status_counts']:
                    st.markdown("")  # Spacing
                    st.markdown("**Status Breakdown:**")
                    for status, count in stats['status_counts'].items():
                        st.caption(f"• {status}: {count}")

                # Cost tracking chart
                st.markdown("")  # Spacing
                st.markdown("**📈 Cost Trend (Last 30 Days)**")

                cost_history = db.get_cost_history(days=30)
                if cost_history:
                    # Convert to pandas DataFrame for charting
                    import pandas as pd
                    chart_df = pd.DataFrame(cost_history)
                    chart_df['date'] = pd.to_datetime(chart_df['date'])
                    chart_df = chart_df.set_index('date')

                    st.line_chart(chart_df, use_container_width=True)
                    st.caption(f"Total spend over {len(cost_history)} day(s) with analyses")
                else:
                    st.caption("No cost data available yet")
            else:
                st.info("No analyses yet")

        # Export options
        with st.expander("📥 Export"):
            if st.session_state.results:
                st.markdown("Export results to file")
                if st.button("Export CSV", use_container_width=True):
                    filepath = db.export_results_to_csv()
                    log_export("CSV", filepath)
                    st.success("✓ Exported to CSV")
                    st.caption(f"`{filepath}`")

                if st.button("Export JSON", use_container_width=True):
                    filepath = db.export_results_to_json()
                    log_export("JSON", filepath)
                    st.success("✓ Exported to JSON")
                    st.caption(f"`{filepath}`")
            else:
                st.info("No results to export")

        st.markdown("---")

        # Video-CUJ Mapping
        with st.expander("🎯 Video Mapping"):
            if not st.session_state.cujs.empty and not valid_videos.empty:
                st.caption("Assign specific videos to CUJs")

                # Initialize mapping in session state
                if "cuj_video_mapping" not in st.session_state:
                    st.session_state.cuj_video_mapping = {}

                video_options = valid_videos['name'].tolist()
                video_dict = dict(zip(valid_videos['name'], valid_videos['id']))

                for _, cuj in st.session_state.cujs.iterrows():
                    selected_video = st.selectbox(
                        f"{cuj['task']}",
                        ["Auto (Round Robin)"] + video_options,
                        key=f"mapping_{cuj['id']}"
                    )

                    if selected_video != "Auto (Round Robin)":
                        st.session_state.cuj_video_mapping[cuj['id']] = video_dict[selected_video]
                    elif cuj['id'] in st.session_state.cuj_video_mapping:
                        del st.session_state.cuj_video_mapping[cuj['id']]
            else:
                st.info("Add CUJs and videos first")

        # Analysis History
        with st.expander("📜 History"):
            history_df = db.get_analysis_results(limit=20)
            if not history_df.empty:
                st.dataframe(
                    history_df[[
                        'cuj_task', 'video_name', 'status', 'friction_score',
                        'model_used', 'cost', 'analyzed_at'
                    ]],
                    width='stretch',
                    hide_index=True
                )
            else:
                st.info("No analysis history yet. Run your first analysis!")

    # Results Display
    with col_summary:
        if st.session_state.results:
            col_summary_header, col_clear = st.columns([3, 1])
            with col_summary_header:
                st.markdown("### 📊 Analysis Results")
            with col_clear:
                if st.button("Clear Results", help="Clear all results from display (data is still in database)"):
                    st.session_state.results = {}
                    st.rerun()

            st.markdown("")  # Spacing

            # Report Generator
            if st.button("Generate Report", use_container_width=True):
                with st.spinner("Writing report..."):
                    report_prompt = f"""
                    Write an executive summary markdown report based on these results:
                    {json.dumps(st.session_state.results, indent=2)}

                    IMPORTANT: When mentioning costs, use "USD" instead of "$" symbol to avoid rendering issues.
                    For example, write "0.29 USD" instead of "$0.29".
                    """
                    report = call_gemini(
                        st.session_state.api_key,
                        st.session_state.selected_model,
                        report_prompt,
                        "You are a Research Lead.",
                        "text/plain"
                    )
                    if report:
                        st.markdown("---")
                        st.markdown(report)
                        st.markdown("---")

            st.markdown("")  # Spacing

            # Confidence Overview
            st.markdown("### Confidence Overview")

            confidence_counts = {"High (4-5)": 0, "Medium (3)": 0, "Low (1-2)": 0}
            for res in st.session_state.results.values():
                score = res.get('confidence_score', 5)
                if score >= 4:
                    confidence_counts["High (4-5)"] += 1
                elif score == 3:
                    confidence_counts["Medium (3)"] += 1
                else:
                    confidence_counts["Low (1-2)"] += 1

            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1:
                st.metric("●●●●● High (4-5)", confidence_counts["High (4-5)"],
                          help="AI is very confident in these results")
            with col_c2:
                st.metric("●●●○○ Medium (3)", confidence_counts["Medium (3)"],
                          help="AI has moderate confidence")
            with col_c3:
                st.metric("●○○○○ Low (1-2)", confidence_counts["Low (1-2)"],
                          help="These results should be reviewed - AI is uncertain")

            st.markdown("---")

            # Cards
            for cuj_id, res in st.session_state.results.items():
                # Find CUJ name for header
                cuj_matches = st.session_state.cujs[st.session_state.cujs['id'] == cuj_id]

                # Skip if CUJ no longer exists
                if cuj_matches.empty:
                    continue

                cuj_row = cuj_matches.iloc[0]

                # Determine effective status and friction (human override takes precedence)
                effective_status = res.get('human_override_status') or res['status']
                effective_friction = res.get('human_override_friction') or res['friction_score']
                is_verified = res.get('human_verified', False)

                # Determine confidence-based expansion
                confidence_score = res.get('confidence_score', 5)

                if confidence_score >= 4:
                    expanded = False
                    review_flag = ""
                elif confidence_score == 3:
                    expanded = False
                    review_flag = ""
                else:
                    expanded = True  # Auto-expand for review
                    review_flag = " ⚠️ REVIEW NEEDED"

                # Build friction display with descriptive label
                friction_label = get_friction_label(effective_friction)

                # Build compact, scannable header
                # Format: [Status] Task Name • Friction: 5/5 (High) • AI: 5●
                header = f"[{effective_status}] {cuj_row['task']} • Friction: {effective_friction}/5 ({friction_label}) • AI: {confidence_score}●{review_flag}"

                if is_verified:
                    header = f"✅ {header}"
                    expanded = False  # Collapse verified results

                with st.expander(header, expanded=expanded):
                    # Show confidence warning if low (at top of card)
                    if confidence_score < 3:
                        st.error(f"⚠️ Low AI Confidence ({confidence_score}/5) - Human review required")

                    # Verification status banner
                    if is_verified:
                        st.success("✓ Human Verified")
                        if res.get('human_notes'):
                            st.info(f"**Reviewer Notes:** {res['human_notes']}")

                    st.markdown("")  # Add spacing

                    c1, c2 = st.columns([1.2, 2.8])

                    with c1:
                        st.markdown(f"**Video:** `{res['video_used']}`")
                        st.markdown(f"**AI Friction Score:** {res['friction_score']}/5")

                        # Show confidence score
                        if res.get('confidence_score'):
                            confidence_emoji = "🟢" if res['confidence_score'] >= 4 else "🟡" if res['confidence_score'] == 3 else "🔴"
                            st.markdown(f"**AI Confidence:** {confidence_emoji} {res['confidence_score']}/5")

                        # Show model and cost if available
                        if 'model_used' in res:
                            model_info = get_model_info(res['model_used'])
                            st.caption(f"**Model:** {model_info['display_name']}")

                        if 'cost' in res:
                            st.caption(f"**Cost:** {format_cost(res['cost'])}")

                        # Show video player if video exists
                        if res.get('video_path') and Path(res['video_path']).exists():
                            st.markdown("---")
                            st.markdown("**🎥 Review Video:**")
                            with open(res['video_path'], 'rb') as video_file:
                                video_bytes = video_file.read()
                                st.video(video_bytes)

                    with c2:
                        st.markdown(f"**Observation:**")
                        st.markdown(res['observation'])

                        # Show key moments if available
                        if res.get('key_moments'):
                            try:
                                moments = json.loads(res['key_moments']) if isinstance(res['key_moments'], str) else res['key_moments']
                                if moments:
                                    st.markdown("")  # Spacing
                                    st.markdown("**📍 Key Moments:**")
                                    for moment in moments:
                                        st.caption(f"• {moment}")
                            except:
                                pass

                        if 'recommendation' in res and res['recommendation']:
                            st.markdown("")  # Spacing
                            st.info(f"💡 **Recommendation:** {res['recommendation']}")

                        st.markdown("")  # Spacing
                        st.caption(f"CUJ ID: {cuj_id}")

                    # Human Verification Section
                    if not is_verified:
                        st.markdown("---")
                        st.markdown("### 👤 Human Verification")

                        with st.form(key=f"verify_form_{cuj_id}"):
                            col_verify1, col_verify2, col_verify3 = st.columns(3)

                            with col_verify1:
                                override_status = st.selectbox(
                                    "Override Status?",
                                    ["Keep AI", "Pass", "Fail", "Partial"],
                                    key=f"status_{cuj_id}"
                                )

                            with col_verify2:
                                override_friction = st.selectbox(
                                    "Override Friction?",
                                    ["Keep AI", "1", "2", "3", "4", "5"],
                                    key=f"friction_{cuj_id}"
                                )

                            with col_verify3:
                                st.markdown("")  # Spacing

                            notes = st.text_area(
                                "Reviewer Notes",
                                placeholder="What did you actually observe in the video?",
                                key=f"notes_{cuj_id}"
                            )

                            if st.form_submit_button("✓ Mark as Verified", type="primary"):
                                # Prepare overrides
                                final_status = None if override_status == "Keep AI" else override_status
                                final_friction = None if override_friction == "Keep AI" else int(override_friction)

                                # Save verification
                                if 'analysis_id' in res:
                                    success = db.verify_analysis(
                                        res['analysis_id'],
                                        override_status=final_status,
                                        override_friction=final_friction,
                                        notes=notes
                                    )

                                    if success:
                                        # Update session state so the expander auto-collapses on rerun
                                        st.session_state.results[cuj_id]['human_verified'] = True
                                        if final_status:
                                            st.session_state.results[cuj_id]['human_override_status'] = final_status
                                        if final_friction:
                                            st.session_state.results[cuj_id]['human_override_friction'] = final_friction
                                        if notes:
                                            st.session_state.results[cuj_id]['human_notes'] = notes

                                        st.success("✅ Verification saved!")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error("Failed to save verification")
                    else:
                        # Show override info if present
                        if res.get('human_override_status') or res.get('human_override_friction'):
                            st.markdown("---")
                            st.markdown("### 👤 Human Overrides Applied")
                            if res.get('human_override_status'):
                                st.caption(f"**Status Override:** {res['status']} → {res['human_override_status']}")
                            if res.get('human_override_friction'):
                                st.caption(f"**Friction Override:** {res['friction_score']} → {res['human_override_friction']}")

        else:
            st.info("""
            🚀 **Ready to start analyzing!**

            Click "Run Analysis" to evaluate your videos.

            **What happens:**
            1. Each CUJ is tested against a video
            2. AI evaluates task completion and friction
            3. Results show Pass/Fail status and recommendations
            4. You can verify and override AI results

            ⏱️ **Time:** ~2-5 minutes per video
            """)