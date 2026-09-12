from fastapi import FastAPI

app = FastAPI(description="FastAPI集成的客服服务")

app.include_router()