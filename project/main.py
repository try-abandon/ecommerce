import uvicorn

from project.common.config import Settings

if __name__ == '__main__':
    settings = Settings()
    uvicorn.run(app="app.app:app", host=settings.api_host, port=settings.api_port)