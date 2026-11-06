import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse

from app.config import settings
from app.utils.logger import setup_logging
from app.api.routes import router as api_router

# Initialize centralized logging (Console + logs/app.log)
setup_logging()
logger = logging.getLogger("app.main")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Autonomous AI Agent system that understands natural language requests, "
        "dynamically plans TODO tasks, orchestrates specialized tools, reflects on quality, "
        "and generates polished Microsoft Word (.docx) business documents."
    ),
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for open development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Router
app.include_router(api_router)

@app.get("/ui", include_in_schema=False)
async def serve_ui():
    """Serves the simple React frontend."""
    frontend_path = Path(__file__).parent.parent / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    return RedirectResponse(url="/docs")

@app.get("/", include_in_schema=False)
async def root():
    """Redirects base URL to the interactive Web UI."""
    return RedirectResponse(url="/ui")

logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} initialized successfully.")
