# UXR CUJ Analysis - AI-Powered UX Research Analysis Tool

An intelligent tool for analyzing user session videos against Critical User Journeys (CUJs) using Google's Gemini AI models.

**Version:** 2.2.0
**Status:** Development/POC (Use locally for privacy)

## Features

- 🎭 **Demo Mode**: Try the app without creating an account - full functionality with no data persistence
- 🔐 **Multi-User Support**: User authentication with isolated data per account
- 🎥 **Real Video Analysis**: Upload and analyze actual user session videos with Gemini AI
- 📁 **Google Drive Integration**: Import videos directly from Drive, export results to Drive
- 📋 **CUJ Management**: Define and manage Critical User Journeys
- 🤖 **AI-Powered Insights**: Get automated friction scoring and recommendations
- 👤 **Human Verification**: Review and override AI analysis with confidence scores
- 📍 **Key Moments Tracking**: Timestamped observations from video analysis
- 🎬 **Video Playback**: Review videos directly in the results panel
- 💰 **Cost Tracking**: See estimated and actual API costs for each analysis
- 📊 **Results Dashboard**: View comprehensive analysis results with executive reports
- ✨ **Latest Gemini Models**: 7 models including Gemini 3 Pro Preview and 2.5 Flash-Lite

## Latest Updates (Sprints 1-7 Complete!)

### Sprint 7: Authentication & Demo Mode ✨ (Latest!)
- 🎭 **Demo Mode**: Click "Try Demo Mode" on login to test without account creation
  - Full app functionality with no registration required
  - Unique session IDs for isolated multi-user demo testing
  - Automatic data cleanup on browser close (no persistence)
  - Usage limits: max 2 CUJs, 10 videos per demo session
  - Conversion prompt to create account and keep data
- 🔐 **User Authentication System**:
  - Secure bcrypt password hashing
  - Email optional for registration
  - Session-based authentication with data isolation per user
  - Full user profile management (username, email, full name)
- 👥 **Multi-User Data Isolation**: Each user has private access to their own CUJs, videos, and analysis results
- 🚪 **Logout with Data Clearing**: Secure session cleanup prevents data leakage between users
- 💾 **Per-User Persistence**: API keys, model preferences, and all data saved per account

### Sprint 1: Foundation ✅
- 🎥 **Real Video Processing**: Upload videos (mp4, mov, avi, webm) up to 900MB and 90 minutes
- ✨ **Gemini 2.5 Integration**: Updated to latest models (2.5 Flash-Lite, 2.5 Flash, 2.0 Flash Experimental)
- 💰 **Cost Estimation**: Real-time cost tracking for each video analysis
- 📊 **Progress Tracking**: Multi-stage progress indicators for uploads and analysis
- 🛡️ **Error Handling**: Comprehensive error handling with retry logic
- ✓ **Video Validation**: Automatic format, size, and duration validation

### Sprint 2: Persistence & Reliability ✅
- 💾 **SQLite Database**: All data persists across sessions (CUJs, videos, results)
- 🔄 **Auto-Save**: Settings, API key, and model selection automatically saved
- 📥 **Export Functionality**: Export results to CSV or JSON
- 🗑️ **Video Cleanup**: Optional deletion of analyzed videos to save disk space
- 📈 **Statistics Dashboard**: View total analyses, costs, and performance metrics

### Sprint 3: Enhanced UX ✅
- 🎯 **Manual Video-CUJ Mapping**: Assign specific videos to specific CUJs
- 📊 **Live Statistics**: Real-time stats showing total analyses, costs, and friction scores
- 📁 **Export Options**: One-click export to CSV/JSON formats
- 🎨 **Improved UI**: Better status indicators and action buttons

### Sprint 4: Quality & Logging ✅
- 📝 **Error Logging**: Comprehensive logging system for debugging and audit trails
- 🔍 **Activity Tracking**: All uploads, analyses, and exports logged automatically
- 📂 **Log Management**: Daily log files in `data/logs/` directory

### Sprint 5: Google Drive Integration ✅
- 🔐 **OAuth 2.0 Authentication**: Secure Google Drive connection with token management
- 📁 **Drive File Browser**: Browse and import videos directly from your Google Drive
- ⬇️ **Video Import**: Download videos from Drive with progress tracking (up to 900MB)
- ⬆️ **Result Export**: Export analysis results directly to your Google Drive
- 💾 **Local Caching**: Drive videos cached locally for fast re-analysis
- 🔄 **Seamless Integration**: Tabbed interface for local uploads and Drive imports

### Sprint 6: Major UX/UI Overhaul ✨ (Latest!)
- 🎨 **Horizontal Tab Navigation**: Replaced sidebar with intuitive top tabs (Home, Setup, CUJs, Videos, Analysis)
- 🏠 **Home Dashboard**: New overview page with quick stats, system readiness, recent activity, and getting started guide
- 📊 **Workflow Progress Stepper**: Visual progress tracker in sidebar showing completion of each step (Setup → CUJs → Videos → Analyze)
- 🎯 **Enhanced Status Indicators**: Color-coded system status with counts and navigation hints
- 💰 **Cost Preview Calculator**: Estimate costs before uploading videos with quick reference table
- 🎨 **Custom Theme**: Professional indigo theme with improved visual hierarchy
- 📁 **Advanced Drive Navigation**:
  - Folder browser with breadcrumb navigation
  - Search by filename with recursive folder search
  - Paste Drive links to navigate directly to folders or files
  - Click-to-navigate folder grid
- 🔍 **Improved Scannability**:
  - Monochrome confidence indicators (●●●●● instead of colored emojis)
  - Compact result headers: `[Status] Task • Friction: 5/5 (High) • AI: 5●`
  - Descriptive friction labels (Smooth/Moderate/High)
- 📋 **Bulk CUJ Operations**: Import/export CUJs via CSV for batch management
- ✅ **Better Empty States**: Helpful guidance when no CUJs, videos, or results exist
- ⌨️ **Keyboard Shortcuts Guide**: Quick tips and shortcuts reference in sidebar
- 🔘 **Button Hierarchy**: Clear visual priority (primary/secondary/default actions)

### Previous Enhancements ✅
- 👤 **Human Verification Workflow**: Mark analyses as verified, override AI decisions, add notes
- 📊 **Confidence Scores**: AI rates its own certainty (1-5 scale) with low-confidence warnings
- 📍 **Key Moments**: Timestamped observations extracted from video analysis
- 🎬 **Video Playback**: Embedded video player in results panel for verification
- 🧠 **New AI Models**: Gemini 3 Pro Preview, 2.0 Flash-Lite for more options
- 🔄 **Retry Logic**: Automatic exponential backoff for API rate limits (Gemini: 3x, Drive: 5x)
- 🗄️ **Database Migrations**: Automatic schema updates for backward compatibility

## Requirements

### System Requirements
- Python 3.8+ (tested on 3.13)
- macOS, Linux, or Windows
- 2GB+ disk space (for video storage and caching)

### API Keys & Services
- **Required**: Google Gemini API Key ([Get one here](https://aistudio.google.com/app/apikey))
- **Optional**: Google Cloud OAuth credentials for Drive integration ([Setup guide](https://console.cloud.google.com/))

### Core Dependencies
- `streamlit` - Web application framework
- `opencv-python-headless` - Video metadata extraction (headless for server deployment)
- `google-generativeai` & `google-genai` - Gemini AI SDK
- `google-api-python-client` - Google Drive API (optional)
- `pandas` - Data manipulation
- See [requirements.txt](requirements.txt) for complete list

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd CUJ-Autorater
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your API key:
   - Option 1: Enter it directly in the System Setup page when running the app
   - Option 2: Create `.streamlit/secrets.toml`:
   ```toml
   GEMINI_API_KEY = "your-api-key-here"
   ```

4. **Optional: Set up Google Drive** (if you want Drive integration):
   - Copy the template: `cp .streamlit/secrets.toml.template .streamlit/secrets.toml`
   - Add your Google Cloud OAuth credentials to `.streamlit/secrets.toml`:
   ```toml
   [google_drive]
   client_id = "YOUR_CLIENT_ID.apps.googleusercontent.com"
   client_secret = "YOUR_CLIENT_SECRET"
   redirect_uri = "http://localhost:8501"
   ```
   - See [SPRINT5_IMPLEMENTATION.md](SPRINT5_IMPLEMENTATION.md) for detailed setup instructions

## Usage

### 🎭 Quick Start with Demo Mode (No Account Needed!)

**Try the app instantly without creating an account:**

1. **Start the application:**
```bash
streamlit run app.py
```

2. **Click "Try Demo Mode"** on the login screen
   - Get full app functionality immediately
   - No email or password required
   - Data is temporary and clears when you close the browser
   - Usage limits: max 2 CUJs and 10 videos per demo session
   - Click "Create Account" banner anytime to save your work

**Ready to keep your data?** Create a free account to save everything permanently!

---

### 📋 Full Account Setup & Usage

1. **Start the application:**
```bash
streamlit run app.py
```

2. **Create an account or login:**
   - **New users**: Click "Register" tab and create your account
   - **Returning users**: Use "Login" tab with your credentials
   - **Quick demo**: Click "Try Demo Mode" to test without signup

3. **🏠 Home Dashboard** (First stop):
   - View quick stats: CUJs defined, videos uploaded, analyses complete, total cost
   - Check system readiness with color-coded status indicators
   - See recent activity and analysis history
   - Follow the Quick Start Guide to get oriented
   - Monitor your workflow progress in the sidebar (Setup → CUJs → Videos → Analyze)

3. **⚙️ System Setup** (First-time setup):
   - Click the "System Setup" tab at the top
   - Enter your Gemini API Key
   - Select your preferred model (default: Gemini 2.5 Flash-Lite for cost efficiency)
   - Customize the system prompt if needed
   - **Optional**: Connect Google Drive for video imports

4. **📋 Define CUJs**:
   - Click the "Define CUJs" tab
   - **Option A**: Add CUJs manually in the editable table
   - **Option B**: Use "Generate with AI" to create CUJs from a topic/feature
   - **Option C**: Import from CSV for bulk operations
   - Export your CUJs to CSV for backup or sharing

5. **📹 Upload Videos**:
   - Click the "Upload Videos" tab
   - **Use the Cost Estimator** to preview analysis costs before uploading
   - **Local Upload**: Upload from your computer (mp4, mov, avi, webm)
   - **Drive Import** (if connected):
     - Browse folders with breadcrumb navigation
     - Search videos by filename (with recursive search option)
     - Paste Drive links to jump directly to folders or files
     - Click folder buttons to navigate through your Drive
   - Videos are automatically validated and stored locally

6. **🚀 Run Analysis**:
   - Click the "Run Analysis" tab
   - Review the top stats banner (CUJs, Videos, Analyses, Cost)
   - Check readiness status (green = ready to go)
   - Click "Run Analysis" button to start
   - Watch real-time progress with stage indicators
   - View results with friction scores, observations, and recommendations

7. **📊 Review & Verify Results**:
   - View the Confidence Overview with clear indicators (●●●●● High, ●●●○○ Medium, ●○○○○ Low)
   - Scan result headers: `[Status] Task • Friction: 5/5 (High) • AI: 5●`
   - Low confidence results auto-expand for review
   - Check confidence scores (AI rates its own certainty 1-5)
   - Review key moments (timestamped observations)
   - Watch videos directly in the results panel
   - Mark analyses as verified with optional overrides
   - Add reviewer notes for manual observations

8. **📥 Generate Reports & Export**:
   - Click "Generate Report" to create an executive summary
   - Use the Export expander for CSV/JSON downloads
   - Check Statistics expander for detailed breakdowns
   - View Analysis History for past results

## Model Selection Guide

| Model | Best For | Cost (in/out per M tokens) | Speed |
|-------|----------|---------------------------|-------|
| **Gemini 3 Pro Preview** | Most advanced reasoning | $2.00 / $12.00 | ⚡ |
| **Gemini 2.5 Pro** | Recommended for quality | $1.25 / $10.00 | ⚡⚡ |
| **Gemini 2.5 Flash** | Balanced quality/cost | $0.30 / $2.50 | ⚡⚡⚡ |
| **Gemini 2.5 Flash-Lite** | Fastest & cheapest | $0.10 / $0.40 | ⚡⚡⚡⚡ |
| **Gemini 2.0 Flash** | Stable, cost-effective | $0.10 / $0.40 | ⚡⚡⚡ |
| **Gemini 2.0 Flash-Lite** | Ultra budget | $0.075 / $0.30 | ⚡⚡⚡⚡ |
| **Gemini 2.0 Flash Exp** | Free preview | $0.00 / $0.00 | ⚡⚡⚡ |

**Recommendation**: Start with **Gemini 2.5 Flash-Lite** for POC. Upgrade to **2.5 Pro** for production-quality analysis.

## Cost Estimates

For a typical 2-minute video:
- **Gemini 2.0 Flash-Lite**: ~$0.0025 per analysis (ultra budget)
- **Gemini 2.5 Flash-Lite**: ~$0.0034 per analysis (recommended)
- **Gemini 2.5 Flash**: ~$0.0095 per analysis (balanced)
- **Gemini 2.5 Pro**: ~$0.025 per analysis (high quality)

For longer videos (e.g., 30 minutes):
- **Gemini 2.0 Flash-Lite**: ~$0.038 per analysis
- **Gemini 2.5 Flash-Lite**: ~$0.051 per analysis
- **Gemini 2.5 Flash**: ~$0.143 per analysis
- **Gemini 2.5 Pro**: ~$0.375 per analysis

**Example**: Analyzing 100 short videos (2 min each) costs approximately $0.25 - $2.50 depending on model choice.

**Note**: Costs scale linearly with video duration. Maximum supported video length is 90 minutes.

## Project Structure

```
CUJ-Autorater/
├── app.py                       # Main Streamlit application (1,900+ lines)
├── auth.py                      # Authentication & demo mode manager (248 lines)
├── config.py                    # Configuration & model settings (184 lines)
├── storage.py                   # Database layer with SQLite (653 lines)
├── gemini_client.py             # Gemini API wrapper with retry logic (286 lines)
├── video_processor.py           # Video validation & OpenCV processing (292 lines)
├── drive_client.py              # Google Drive API client with OAuth (426 lines)
├── logger.py                    # Centralized logging system (83 lines)
├── requirements.txt             # Python dependencies (15 packages)
├── README.md                    # This file (comprehensive documentation)
├── CHANGELOG.md                 # Version history and sprint tracking
├── SPRINT5_IMPLEMENTATION.md    # Drive integration technical guide
├── .gitignore                   # Git ignore rules (protects secrets & data)
├── .streamlit/
│   ├── config.toml             # Streamlit settings (max upload 1024MB)
│   └── secrets.toml.template   # OAuth & API key template
├── tests/
│   └── test_drive_auth.py      # Drive OAuth diagnostic tool
└── data/                        # Created automatically (gitignored)
    ├── videos/                 # Local video uploads
    ├── drive_videos/           # Cached videos from Google Drive
    ├── exports/                # Exported analysis results (CSV/JSON)
    ├── logs/                   # Daily rotating log files
    └── uxr_mate.db             # SQLite database (5 tables, auto-migration)
```

## Configuration

### Video Constraints
- **Max file size**: 900 MB
- **Max duration**: 90 minutes (5400 seconds)
- **Supported formats**: mp4, mov, avi, webm, mkv, flv

### Database Schema
The SQLite database (`data/uxr_mate.db`) contains 6 tables:
- **users**: User accounts with authentication (username, email, password_hash, full_name)
- **cujs**: Critical User Journeys per user (id, task, expectation, user_id)
- **videos**: Video metadata per user (file_path, duration, size, resolution, drive info, user_id)
- **analysis_results**: AI analysis results with human verification fields
- **sessions**: Batch tracking (future feature)
- **settings**: App preferences per user (API key, model selection, user_id)

**Note**: Schema migrations run automatically on startup for backward compatibility.

### Customization
Edit [config.py](config.py) to adjust:
- Model configurations (add new models, change defaults)
- Video size/duration limits
- Token estimation formulas (258 tokens/video sec, 25 tokens/audio sec)
- Retry settings (max attempts, backoff timing)
- Cost calculations per model
- Default system prompt for analysis

## Advanced Features

### Human Verification Workflow
After AI analysis completes, each result can be human-verified:
1. Review AI analysis (status, friction score, observations)
2. Check AI confidence score (1-5 scale, < 3 triggers warning)
3. Watch video directly in the results panel
4. Override status or friction score if needed
5. Add reviewer notes with manual observations
6. Mark as verified (expands auto-collapse)

**Why verify?** AI confidence scores help identify uncertain analyses. Low confidence (< 3) suggests the video may be ambiguous or the CUJ unclear.

### Confidence Scores
The AI rates its own certainty on each analysis using a **monochrome indicator system** (to avoid color theory confusion with Pass/Fail status):
- **●●●●● (5)**: Very confident, clear success/failure
- **●●●●○ (4)**: Confident, minor ambiguity
- **●●●○○ (3)**: Moderate confidence, some uncertainty (⚠️ review recommended)
- **●●○○○ (2)**: Low confidence, significant ambiguity (⚠️ review required)
- **●○○○○ (1)**: Very uncertain, needs human review (⚠️ review required)

**Why monochrome?** Filled/empty circles clearly indicate AI certainty without conflicting with status colors. A high confidence (●●●●●) score next to [Fail] means the AI is certain about the failure, not that the result is "good".

### Key Moments
The AI extracts timestamped observations from videos:
- Important user actions with timestamps
- Friction points and where they occur
- Success indicators and confirmation moments
- Displayed as bulleted list in results panel

### Retry Logic
Automatic exponential backoff protects against transient failures:
- **Gemini API**: 3 retry attempts with 2x backoff (handles rate limits, 429 errors)
- **Drive API**: 5 retry attempts with 2x backoff (handles quota, network issues)
- Progress preserved across retries

## Troubleshooting

### "Failed to extract metadata"
- Ensure you have `opencv-python-headless` installed: `pip install opencv-python-headless`
- Check that the video file is not corrupted
- Verify the video format is supported (.mp4, .mov, .avi, .webm, .mkv, .flv)

### "Gemini API Error: 429"
- Rate limit hit. The app will automatically retry with exponential backoff (3 attempts)
- If it still fails, wait 1-2 minutes before retrying
- Consider upgrading your API quota at [Google AI Studio](https://aistudio.google.com/)

### "Video processing failed"
- Check file size (must be < 900MB)
- Check duration (must be < 90 minutes / 5400 seconds)
- Ensure the video format is supported
- Check disk space in `data/videos/` or `data/drive_videos/`

### "No module named 'config'"
- Make sure all Python files are in the project root
- Verify virtual environment is activated
- Run `python -c "import config"` to test
- Reinstall dependencies: `pip install -r requirements.txt`

### "Drive authentication failed"
- Check OAuth credentials in `.streamlit/secrets.toml`
- Verify redirect URI is `http://localhost:8501`
- Ensure Drive API is enabled in Google Cloud Console
- See [SPRINT5_IMPLEMENTATION.md](SPRINT5_IMPLEMENTATION.md) for detailed setup

### "Low confidence score on analysis"
- This is expected! The AI is telling you to review manually
- Watch the video in the results panel
- Add human verification with your observations
- Override AI decision if needed

### Database Errors
- Database auto-migrates on startup
- If corrupted, delete `data/uxr_mate.db` (loses all data!)
- Check logs in `data/logs/` for details

## Roadmap

### ✅ Completed (v1.0.0 - v2.2.0)
**Sprint 1-7 Complete:**
- ✅ Real video upload and analysis
- ✅ 7 Gemini models (3 Pro, 2.5 Pro, 2.5 Flash, 2.0 Flash variants)
- ✅ Progress tracking with multi-stage indicators
- ✅ Cost estimation and tracking with preview calculator
- ✅ SQLite database with auto-migration
- ✅ Settings auto-save (API key, model selection)
- ✅ Video cleanup options
- ✅ Manual video-CUJ mapping
- ✅ Export to CSV/JSON
- ✅ Statistics dashboard
- ✅ Comprehensive error logging
- ✅ Google Drive integration (OAuth, folder navigation, link import, export)
- ✅ Human verification workflow
- ✅ Confidence scores with monochrome indicators
- ✅ Key moments extraction
- ✅ Video playback in results
- ✅ Automatic retry logic with exponential backoff
- ✅ Horizontal tab navigation with Home dashboard
- ✅ Workflow progress stepper in sidebar
- ✅ Enhanced Drive navigation (folders, search, paste links)
- ✅ Bulk CUJ import/export via CSV
- ✅ Custom indigo theme
- ✅ Improved result scannability with compact headers
- ✅ Empty states with helpful guidance
- ✅ Demo mode with session isolation and usage limits
- ✅ User authentication system with bcrypt password hashing
- ✅ Multi-user support with per-user data isolation
- ✅ Account creation and login workflow

### 🎯 Future Enhancements
**High Priority:**
- Unit tests and integration tests
- Export results to Google Drive (UI integration)
- Session tracking for batch analysis
- Encrypted API key storage
- Password reset/recovery workflow

**Medium Priority:**
- Video thumbnails for quick preview
- Batch analysis pause/resume
- Export to PDF with charts
- API rate limit dashboard
- Email verification for accounts
- Role-based access control (admin, reviewer, viewer)

**Low Priority:**
- Video editing/trimming before analysis
- Collaborative review with comments
- Custom model fine-tuning

## Privacy & Security

**⚠️ Important:** This application is currently in development and not designed for production use with sensitive data.

### Current Status
- ✅ User authentication with bcrypt password hashing
- ✅ Per-user data isolation (each user sees only their data)
- ✅ Session-based authentication
- ✅ Demo mode with no data persistence
- ⚠️ Local deployment recommended
- ⚠️ No encryption for API keys (stored in database per user)
- ⚠️ OAuth tokens in session state (temporary, not persisted)
- ⚠️ Logs may contain video filenames and analysis text

### For Production Use
Before deploying with real user data, implement:
1. Encrypted storage for API keys and OAuth tokens (in progress)
2. HTTPS deployment with proper certificate management
3. Role-based access control (RBAC) for team collaboration
4. Audit logging with user attribution
5. Data retention and deletion policies
6. Email verification and password reset workflows
7. Rate limiting and brute-force protection

### Data Storage
All data is stored locally:
- Videos: `data/videos/` and `data/drive_videos/`
- Database: `data/uxr_mate.db` (SQLite)
- Logs: `data/logs/` (daily rotation)
- Exports: `data/exports/`

**Note**: Videos uploaded to Gemini API are automatically deleted after analysis. Google Drive videos are cached locally but not uploaded to Gemini from Drive directly.

## Contributing

This is a proof-of-concept project in active development. Contributions welcome!

### How to Contribute
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup
1. Clone the repo
2. Create virtual environment: `python -m venv .venv`
3. Activate: `source .venv/bin/activate` (macOS/Linux) or `.venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Configure API keys in `.streamlit/secrets.toml`
6. Run: `streamlit run app.py`

## License

MIT License - feel free to use and modify for your needs.

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section above
2. Review the [Gemini API documentation](https://ai.google.dev/docs)
3. Check logs in `data/logs/` for error details
4. Open an issue on GitHub or contact the maintainer

## Acknowledgments

- Powered by [Google Gemini AI](https://deepmind.google/technologies/gemini/)
- Built with [Streamlit](https://streamlit.io/)
- Video processing with [OpenCV](https://opencv.org/)

---

## Quick Start

```bash
# Clone and setup
git clone <your-repo-url>
cd CUJ-Autorater
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

**First time?** Click "Try Demo Mode" on the login screen to test immediately (no signup needed)!

**Want to keep your data?** Create a free account, then configure your Gemini API key in System Setup.

---

**Version**: 2.2.0 | **Last Updated**: November 2025 | **Status**: Active Development

**Note**: This tool now supports multi-user authentication and demo mode! Try it without creating an account by clicking "Try Demo Mode" on the login screen. For full functionality and data persistence, create a free account. Video analysis requires a valid Gemini API key. Costs vary based on model selection and video duration. Supports videos up to 900MB and 90 minutes. For privacy, use local deployment only.
