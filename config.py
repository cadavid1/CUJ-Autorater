"""
Configuration and constants for UXR CUJ Analysis application
"""

# Model configurations
MODELS = {
    "gemini-3-pro-preview": {
        "display_name": "Gemini 3 Pro Preview (Most Advanced)",
        "cost_per_m_tokens_input": 2.00,
        "cost_per_m_tokens_output": 12.00,
        "best_for": "State-of-the-art reasoning, complex multimodal analysis",
        "supports_video": True,
    },
    "gemini-2.5-pro": {
        "display_name": "Gemini 2.5 Pro (Recommended - Best Reasoning)",
        "cost_per_m_tokens_input": 1.25,
        "cost_per_m_tokens_output": 10.00,
        "best_for": "Complex reasoning, detailed video analysis",
        "supports_video": True,
    },
    "gemini-2.5-flash": {
        "display_name": "Gemini 2.5 Flash (Best Quality)",
        "cost_per_m_tokens_input": 0.30,
        "cost_per_m_tokens_output": 2.50,
        "best_for": "Complex reasoning, detailed analysis",
        "supports_video": True,
    },
    "gemini-2.5-flash-lite": {
        "display_name": "Gemini 2.5 Flash-Lite (Fastest & Cheapest)",
        "cost_per_m_tokens_input": 0.10,
        "cost_per_m_tokens_output": 0.40,
        "best_for": "High-volume, cost-sensitive tasks",
        "supports_video": True,
    },
    "gemini-2.0-flash": {
        "display_name": "Gemini 2.0 Flash (Stable)",
        "cost_per_m_tokens_input": 0.10,
        "cost_per_m_tokens_output": 0.40,
        "best_for": "Fast, cost-effective video analysis",
        "supports_video": True,
    },
    "gemini-2.0-flash-lite": {
        "display_name": "Gemini 2.0 Flash-Lite (Ultra Budget)",
        "cost_per_m_tokens_input": 0.075,
        "cost_per_m_tokens_output": 0.30,
        "best_for": "Maximum cost efficiency",
        "supports_video": True,
    },
    "gemini-2.0-flash-exp": {
        "display_name": "Gemini 2.0 Flash Experimental (Cutting Edge)",
        "cost_per_m_tokens_input": 0.00,  # Free during preview
        "cost_per_m_tokens_output": 0.00,
        "best_for": "Testing latest features, real-time capabilities",
        "supports_video": True,
    },

}

# Default model
DEFAULT_MODEL = "gemini-2.5-pro"

# Video constraints
MAX_VIDEO_SIZE_MB = 900
MAX_VIDEO_DURATION_SECONDS = 5400  # 90 minutes
SUPPORTED_VIDEO_FORMATS = [".mp4", ".mov", ".avi", ".webm", ".mkv", ".flv"]
SUPPORTED_MIME_TYPES = [
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
    "video/x-matroska",
    "video/x-flv"
]

# Token estimates for cost calculation
TOKENS_PER_VIDEO_SECOND = 258  # Video frames
TOKENS_PER_AUDIO_SECOND = 25   # Audio
AVERAGE_PROMPT_TOKENS = 1000   # System prompt + CUJ description
AVERAGE_RESPONSE_TOKENS = 500  # Expected JSON response

# Database configuration
DATABASE_PATH = "./data/uxr_mate.db"
VIDEO_STORAGE_PATH = "./data/videos/"
EXPORT_STORAGE_PATH = "./data/exports/"

# Google Drive configuration
DRIVE_VIDEO_STORAGE_PATH = "./data/drive_videos/"  # Local cache for Drive videos
DRIVE_ENABLED = True  # Feature flag for Drive integration

# Default system prompt
DEFAULT_SYSTEM_PROMPT = """You are an expert UX Researcher. Your job is to evaluate user sessions against Critical User Journeys (CUJs).

CRITICAL INSTRUCTIONS:
1. Watch the ENTIRE video carefully before making any conclusions
2. Only describe what you ACTUALLY SEE in the video - do NOT make assumptions
3. Include SPECIFIC timestamps for key moments (e.g., "at 0:23, user clicked X")
4. If you cannot clearly see an action, say "unclear" or "not visible"
5. Rate your own confidence level (1-5) based on video quality and clarity

Your analysis must be EVIDENCE-BASED. Generic observations without specific details indicate you didn't watch carefully.

Rate "Friction" on a scale of 1 (Smooth) to 5 (Blocker):
- 1: Task completed smoothly, no hesitation
- 2: Minor confusion, but quickly resolved
- 3: Moderate friction, user had to retry or search
- 4: Major friction, user struggled significantly
- 5: Blocker, user could not complete the task

Output JSON format:
{
  "status": "Pass" | "Fail" | "Partial",
  "friction_score": number (1-5),
  "confidence_score": number (1-5, where 5 = very confident),
  "observation": "Detailed observation with specific timestamps and actions seen",
  "recommendation": "string",
  "key_moments": ["timestamp: description", "timestamp: description"]
}"""

# Retry configuration for API calls
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
EXPONENTIAL_BACKOFF = True

# UI Configuration
PROGRESS_UPLOAD_WEIGHT = 0.3    # 0-30% for upload
PROGRESS_PROCESS_WEIGHT = 0.4   # 30-70% for processing
PROGRESS_ANALYZE_WEIGHT = 0.3   # 70-100% for analysis


def get_model_list():
    """Get list of model IDs for dropdown"""
    return list(MODELS.keys())


def get_model_display_names():
    """Get list of display names for models"""
    return [MODELS[model]["display_name"] for model in MODELS.keys()]


def get_model_info(model_id):
    """Get configuration for a specific model"""
    return MODELS.get(model_id, MODELS[DEFAULT_MODEL])


def estimate_cost(video_duration_seconds, model_id=DEFAULT_MODEL):
    """
    Estimate the cost of analyzing a video

    Args:
        video_duration_seconds: Duration of video in seconds
        model_id: Model to use for analysis

    Returns:
        dict with cost breakdown
    """
    model_info = get_model_info(model_id)

    # Calculate input tokens
    video_tokens = video_duration_seconds * (TOKENS_PER_VIDEO_SECOND + TOKENS_PER_AUDIO_SECOND)
    total_input_tokens = video_tokens + AVERAGE_PROMPT_TOKENS

    # Calculate costs
    input_cost = (total_input_tokens / 1_000_000) * model_info["cost_per_m_tokens_input"]
    output_cost = (AVERAGE_RESPONSE_TOKENS / 1_000_000) * model_info["cost_per_m_tokens_output"]
    total_cost = input_cost + output_cost

    return {
        "input_tokens": int(total_input_tokens),
        "output_tokens": AVERAGE_RESPONSE_TOKENS,
        "total_tokens": int(total_input_tokens + AVERAGE_RESPONSE_TOKENS),
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "model": model_id,
        "model_display_name": model_info["display_name"]
    }


def format_cost(cost):
    """Format cost as currency string"""
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"
