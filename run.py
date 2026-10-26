from pathlib import Path
import uvicorn
from app.config import settings
from app.utils.logger import setup_logging

if __name__ == "__main__":
    setup_logging()
    
    host = "127.0.0.1"
    port = settings.API_PORT

    print("=" * 65)
    print(f"  {settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 65)
    print(f"  Swagger UI Link : http://{host}:{port}/docs")
    print(f"  Live Log File   : logs/app.log")
    print("=" * 65)

    # Only watch 'app' folder for code changes; ignore logs and storage to prevent reload loops
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        reload_dirs=["app"],
        reload_excludes=["logs/*", "storage/*", "*.log", "*.docx"]
    )
