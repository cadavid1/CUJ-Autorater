# Changelog

All notable changes to UXR CUJ Analysis will be documented in this file.

## [2.0.0] - 2024-11-24

### Added - Sprint 1: Foundation
- Real video upload and processing with Gemini AI
- Support for mp4, mov, avi, webm video formats
- Automatic video validation (format, size, duration)
- Video metadata extraction (duration, resolution, file size)
- Latest Gemini models integration (2.5 Flash-Lite, 2.5 Flash, 2.0 Flash Experimental)
- Real-time cost estimation per video
- Multi-stage progress tracking (upload → process → analyze)
- Enhanced error handling with retry logic
- Model selection UI with cost information
- Modular code architecture (config.py, gemini_client.py, video_processor.py)

### Added - Sprint 2: Persistence & Reliability
- SQLite database for persistent storage
- Automatic saving of CUJs, videos, and analysis results
- Settings persistence (API key, model selection)
- Database schema with proper foreign keys
- Data export to CSV format
- Data export to JSON format
- Statistics dashboard (total analyses, costs, friction scores)
- Video cleanup dialog after analysis
- Status breakdown by Pass/Fail/Partial

### Added - Sprint 3: Enhanced UX
- Manual video-CUJ mapping interface
- Assign specific videos to specific CUJs
- Live statistics display in Analysis Dashboard
- One-click export buttons (CSV/JSON)
- Enhanced status indicators
- Video management improvements
- Delete confirmation for videos
- Cost tracking per analysis

### Added - Sprint 4: Quality & Logging
- Comprehensive logging system
- Daily log files in data/logs/
- Activity tracking for all operations:
  - Video uploads
  - Analysis starts and completions
  - Exports
  - Errors
- Error logging with context
- Automatic log rotation

### Changed
- Updated model list to use latest Gemini models
- Improved UI layout and organization
- Better error messages and user guidance
- Enhanced progress indicators
- Optimized database queries

### Fixed
- Session state persistence issues
- Video file path handling
- Cost calculation accuracy
- Progress bar timing

## [1.0.0] - 2024-11-23

### Initial Release
- Basic Streamlit UI
- Text-based CUJ analysis (no real video)
- Manual video context descriptions
- Sample CUJs and videos
- Basic Gemini API integration
- Simple results display
- Executive report generation

---

## Version History

- **v2.0.0** - Complete rewrite with real video analysis, database persistence, and enhanced features (Sprints 1-4)
- **v1.0.0** - Initial proof-of-concept release
