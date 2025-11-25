# UXR Mate - AI-Powered UX Research Analysis Tool

An intelligent tool for analyzing user session videos against Critical User Journeys (CUJs) using Google's Gemini AI models.

## Features

- 🎥 **Real Video Analysis**: Upload and analyze actual user session videos with Gemini AI
- 📁 **Google Drive Integration**: Import videos directly from Drive, export results to Drive
- 📋 **CUJ Management**: Define and manage Critical User Journeys
- 🤖 **AI-Powered Insights**: Get automated friction scoring and recommendations
- 💰 **Cost Tracking**: See estimated and actual API costs for each analysis
- 📊 **Results Dashboard**: View comprehensive analysis results with executive reports
- ✨ **Latest Gemini Models**: Uses the newest Gemini 2.5 Flash-Lite and other cutting-edge models

## Latest Updates (Sprints 1-5 Complete!)

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

## Requirements

- Python 3.8+
- Google Gemini API Key ([Get one here](https://makersuite.google.com/app/apikey))
- OpenCV for video processing
- Streamlit for the web interface
- **Optional**: Google Cloud OAuth credentials for Drive integration ([Setup guide](https://console.cloud.google.com/))

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

1. **Start the application:**
```bash
streamlit run app.py
```

2. **System Setup** (First-time setup):
   - Enter your Gemini API Key
   - Select your preferred model (default: Gemini 2.5 Flash-Lite for cost efficiency)
   - Customize the system prompt if needed

3. **Define CUJs**:
   - Go to "CUJ Data Source" page
   - Add CUJs manually or use AI to generate them
   - Edit the task name and expected behavior for each CUJ

4. **Upload Videos**:
   - Go to "Video Assets" page
   - **Option A**: Upload from local files (mp4, mov, avi, webm)
   - **Option B**: Import from Google Drive (if connected)
   - Videos are automatically validated and stored locally
   - See cost estimates for each video

5. **Run Analysis**:
   - Go to "Analysis Dashboard"
   - Click "Run Analysis" to start
   - Watch real-time progress as videos are analyzed
   - View results with friction scores, observations, and recommendations

6. **Generate Reports**:
   - Click "Draft Executive Report" to generate a summary
   - Export results for stakeholder review

## Model Selection Guide

| Model | Best For | Cost (per M tokens) | Speed |
|-------|----------|---------------------|-------|
| **Gemini 2.5 Flash-Lite** | High-volume, cost-sensitive tasks | $0.10 / $0.40 | ⚡⚡⚡ |
| **Gemini 2.5 Flash** | Complex reasoning, detailed analysis | $0.30 / $2.50 | ⚡⚡ |
| **Gemini 2.0 Flash Exp** | Testing latest features | Free (preview) | ⚡⚡ |
| **Gemini 1.5 Pro** | Legacy, backward compatibility | $0.35 / $1.05 | ⚡ |

**Recommendation**: Start with **Gemini 2.5 Flash-Lite** for POC. Upgrade to Flash if you need better quality.

## Cost Estimates

For a typical 2-minute video:
- **Gemini 2.5 Flash-Lite**: ~$0.0034 per analysis
- **Gemini 2.5 Flash**: ~$0.0095 per analysis

For longer videos (e.g., 30 minutes):
- **Gemini 2.5 Flash-Lite**: ~$0.051 per analysis
- **Gemini 2.5 Flash**: ~$0.143 per analysis

**Example**: Analyzing 100 short videos (2 min each) costs approximately $0.34 - $0.95 depending on model choice.

**Note**: Costs scale linearly with video duration. Maximum supported video length is 90 minutes.

## Project Structure

```
CUJ-Autorater/
├── app.py                       # Main Streamlit application
├── config.py                    # Configuration & model settings
├── storage.py                   # Database layer (SQLite)
├── gemini_client.py             # Gemini API wrapper
├── video_processor.py           # Video validation & processing
├── drive_client.py              # Google Drive API client (NEW!)
├── logger.py                    # Logging system
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── SPRINT5_IMPLEMENTATION.md    # Drive integration guide (NEW!)
├── .gitignore                  # Git ignore rules
├── .streamlit/
│   └── secrets.toml.template   # OAuth config template (NEW!)
└── data/                        # Created automatically
    ├── videos/                 # Local video uploads
    ├── drive_videos/           # Cached Drive videos (NEW!)
    ├── exports/                # Exported results
    ├── logs/                   # Application logs
    └── uxr_mate.db             # SQLite database
```

## Configuration

### Video Constraints
- **Max file size**: 900 MB
- **Max duration**: 90 minutes (5400 seconds)
- **Supported formats**: mp4, mov, avi, webm, mkv, flv

### Customization
Edit `config.py` to adjust:
- Model configurations
- Video size/duration limits
- Token estimates
- Retry settings
- Cost calculations

## Troubleshooting

### "Failed to extract metadata"
- Ensure you have `opencv-python` installed: `pip install opencv-python`
- Check that the video file is not corrupted

### "Gemini API Error: 429"
- You've hit rate limits. Wait a moment and try again
- Consider upgrading your API quota

### "Video processing failed"
- Check file size (< 900MB)
- Check duration (< 90 minutes)
- Ensure the video format is supported

### "No module named 'config'"
- Make sure all files (app.py, config.py, gemini_client.py, video_processor.py) are in the same directory
- Run `python -c "import config"` to verify

## Roadmap

### ✅ Sprint 1-5: COMPLETED!
- ✅ Real video upload and analysis
- ✅ Latest Gemini models (2.5 Flash-Lite, 2.5 Flash, 2.0 Flash Experimental)
- ✅ Progress tracking with multi-stage indicators
- ✅ Cost estimation and tracking
- ✅ SQLite database for data persistence
- ✅ Settings auto-save (API key, model selection)
- ✅ Video cleanup options
- ✅ Manual video-CUJ mapping
- ✅ Export to CSV/JSON
- ✅ Statistics dashboard
- ✅ Comprehensive error logging
- ✅ **Google Drive Integration**: OAuth, file browser, video import, result export

### 🎯 Future Enhancements
- Unit tests and integration tests
- Video thumbnails
- Batch analysis pause/resume
- Export to PDF
- Multi-user support
- API rate limit handling improvements

## Contributing

This is a proof-of-concept project. Contributions welcome!

## License

MIT License - feel free to use and modify for your needs.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review the [Gemini API documentation](https://ai.google.dev/docs)
3. Open an issue on GitHub

## Acknowledgments

- Powered by [Google Gemini AI](https://deepmind.google/technologies/gemini/)
- Built with [Streamlit](https://streamlit.io/)
- Video processing with [OpenCV](https://opencv.org/)

---

**Note**: This tool requires a valid Gemini API key. Video analysis costs vary based on model selection and video duration. Always review cost estimates before processing large batches. Supports videos up to 900MB and 90 minutes in length.
