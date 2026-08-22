import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.add_event_data import add_event_data_to_db
from src.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await add_event_data_to_db()

    # Потом добавляю сюда dependency injection для базы данных

    try:
        yield
    except Exception as error:
        logging.error(f"Error during lifespan: {error}")
        raise
    finally:
        logging.info("Lifespan completed successfully.")


app = FastAPI(title="API Афиши", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
