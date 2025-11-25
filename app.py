import streamlit as st
import json
import pandas as pd
import time
from datetime import datetime
from pathlib import Path

# Import new modules
from config import (
    MODELS, DEFAULT_MODEL, get_model_list, get_model_info,
    estimate_cost, format_cost, DEFAULT_SYSTEM_PROMPT
)
from video_processor import (
    validate_and_process_video, delete_video_file,
    format_duration, ensure_video_directory
)
from gemini_client import GeminiClient, GeminiAPIError, call_gemini_text
from storage import get_db
from logger import (log_video_upload, log_analysis_start,
                    log_analysis_complete, log_analysis_error, log_export)

# --- CONFIGURATION & STATE ---
st.set_page_config(page_title="UXR Mate", page_icon="🧪", layout="wide")

# Ensure data directories exist
ensure_video_directory()

# Initialize database
db = get_db()

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
    # Load from database settings
    saved_model = db.get_setting("selected_model", DEFAULT_MODEL)
    st.session_state.selected_model = saved_model

if "db_synced" not in st.session_state:
    st.session_state.db_synced = True

# --- HELPER FUNCTIONS ---

def call_gemini(api_key, model_name, prompt, system_instruction, response_mime_type="application/json"):
    """Legacy function for text-only Gemini calls (CUJ generation, reports, etc.)"""
    result = call_gemini_text(api_key, model_name, prompt, system_instruction, response_mime_type)

    if result and "error" in result:
        st.error(f"Gemini API Error: {result['error']}")
        return None

    if response_mime_type == "application/json":
        return result
    return result.get("text") if result else None

# --- SIDEBAR NAVIGATION ---

st.sidebar.title("🧪 UXR Mate")
st.sidebar.markdown("Powered by Gemini")
st.sidebar.markdown("---")

page = st.sidebar.radio("Navigation", ["System Setup", "CUJ Data Source", "Video Assets", "Analysis Dashboard"])

st.sidebar.markdown("---")
if st.session_state.api_key:
    st.sidebar.success("API Key Loaded")
else:
    st.sidebar.warning("No API Key")

# --- PAGE: SYSTEM SETUP ---

if page == "System Setup":
    st.header("⚙️ System Setup")
    
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

    with st.expander("System Prompt", expanded=True):
        st.session_state.system_prompt = st.text_area(
            "Analysis Instruction", 
            value=st.session_state.system_prompt,
            height=200
        )

# --- PAGE: CUJ DATA SOURCE ---

elif page == "CUJ Data Source":
    st.header("📋 CUJ Data Source")
    
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
                            st.session_state.cujs = pd.concat([st.session_state.cujs, new_df], ignore_index=True)
                            # Save to database
                            db.bulk_save_cujs(new_df)
                            st.rerun()

    with col2:
        st.markdown("### Critical User Journeys")
        # Editable Data Table
        edited_df = st.data_editor(
            st.session_state.cujs,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "id": "ID",
                "task": "Task Name",
                "expectation": st.column_config.TextColumn("Expected Behavior", width="large")
            }
        )
        # Save changes back to session state and database
        if not edited_df.equals(st.session_state.cujs):
            st.session_state.cujs = edited_df
            db.bulk_save_cujs(edited_df)

# --- PAGE: VIDEO ASSETS ---

elif page == "Video Assets":
    st.header("📹 Video Assets")

    st.info("💡 Upload real video files to analyze with Gemini. Videos will be validated and stored locally.")

    # File Uploader
    uploaded_files = st.file_uploader(
        "Upload Videos",
        accept_multiple_files=True,
        type=['mp4', 'mov', 'avi', 'webm'],
        help="Upload video files (max 100MB, up to 5 minutes)"
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

    st.markdown("### Manage Videos")
    st.caption("Upload videos above, then manage them in the table below. Delete videos you no longer need to save space.")

    if not st.session_state.videos.empty:
        # Display videos table
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
                    # Delete button
                    if st.button(f"🗑️ Delete", key=f"delete_{row['id']}"):
                        # Delete file if exists
                        if row.get('file_path'):
                            delete_video_file(row['file_path'])

                        # Delete from database
                        db.delete_video(row['id'])

                        # Remove from dataframe
                        st.session_state.videos = st.session_state.videos[
                            st.session_state.videos['id'] != row['id']
                        ].reset_index(drop=True)
                        st.success(f"Deleted {row['name']}")
                        st.rerun()
    else:
        st.info("No videos uploaded yet. Use the uploader above to add videos.")

# --- PAGE: ANALYSIS DASHBOARD ---

elif page == "Analysis Dashboard":
    st.header("🚀 Analysis Dashboard")

    # Check if we have videos with valid file paths
    valid_videos = st.session_state.videos[
        st.session_state.videos['file_path'].notna() &
        (st.session_state.videos['status'] == 'Ready')
    ]

    col_actions, col_summary = st.columns([1, 4])

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

        # Statistics
        stats = db.get_statistics()
        if stats['total_analyses'] > 0:
            st.markdown("### 📊 Statistics")
            st.metric("Total Analyses", stats['total_analyses'])
            st.metric("Total Cost", format_cost(stats['total_cost']))
            st.metric("Avg Friction", f"{stats['avg_friction_score']:.1f}/5")

            if stats['status_counts']:
                st.caption("**Status Breakdown:**")
                for status, count in stats['status_counts'].items():
                    st.caption(f"  • {status}: {count}")

        # Export options
        if st.session_state.results:
            st.markdown("### 📥 Export")

            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                if st.button("CSV", use_container_width=True):
                    filepath = db.export_results_to_csv()
                    log_export("CSV", filepath)
                    st.success(f"Exported to:\n`{filepath}`")

            with col_exp2:
                if st.button("JSON", use_container_width=True):
                    filepath = db.export_results_to_json()
                    log_export("JSON", filepath)
                    st.success(f"Exported to:\n`{filepath}`")

        st.markdown("---")

        # Video-CUJ Mapping
        if not st.session_state.cujs.empty and not valid_videos.empty:
            with st.expander("🎯 Manual Video-CUJ Mapping", expanded=False):
                st.caption("Assign specific videos to CUJs (optional)")

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

        # Analysis History
        with st.expander("📜 View Analysis History", expanded=False):
            history_df = db.get_analysis_results(limit=20)
            if not history_df.empty:
                st.dataframe(
                    history_df[[
                        'cuj_task', 'video_name', 'status', 'friction_score',
                        'model_used', 'cost', 'analyzed_at'
                    ]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No analysis history yet. Run your first analysis!")

        st.markdown("---")

        # Run Analysis button
        if st.button("▶️ Run Analysis", type="primary", use_container_width=True):
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
                                raw_response=json.dumps(analysis)
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

    # Results Display
    if st.session_state.results:
        col_summary_header, col_clear = st.columns([3, 1])
        with col_summary_header:
            st.markdown("### Results")
        with col_clear:
            if st.button("🗑️ Clear Results", help="Clear all results from display (data is still in database)"):
                st.session_state.results = {}
                st.rerun()
        
        # Report Generator
        if st.button("✨ Draft Executive Report"):
            with st.spinner("Writing report..."):
                report_prompt = f"""
                Write an executive summary markdown report based on these results:
                {json.dumps(st.session_state.results, indent=2)}
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

        # Cards
        for cuj_id, res in st.session_state.results.items():
            # Find CUJ name for header
            cuj_row = st.session_state.cujs[st.session_state.cujs['id'] == cuj_id].iloc[0]

            color = "green" if res['status'] == "Pass" else "red" if res['status'] == "Fail" else "orange"

            with st.expander(f"[{res['status']}] {cuj_row['task']} (Friction: {res['friction_score']}/5)"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.markdown(f"**Video:** `{res['video_used']}`")
                    st.markdown(f"**Friction Score:** {res['friction_score']}/5")

                    # Show model and cost if available
                    if 'model_used' in res:
                        model_info = get_model_info(res['model_used'])
                        st.caption(f"**Model:** {model_info['display_name']}")

                    if 'cost' in res:
                        st.caption(f"**Cost:** {format_cost(res['cost'])}")

                    if 'recommendation' in res:
                        st.info(f"💡 {res['recommendation']}")

                with c2:
                    st.markdown(f"**Observation:** {res['observation']}")
                    st.caption(f"CUJ ID: {cuj_id}")

    else:
        st.info("No analysis results yet. Click 'Run Analysis' to start.")