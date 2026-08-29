import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.add_event_data import add_event_data_to_db
from src.configs.config import Settings
from src.ioc import create_container
from src.presentation.router import router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:

    try:  # noqa: WPS229
        await add_event_data_to_db()
        yield
    except Exception as error:
        logging.error(f"Error during lifespan: {error}")
        raise
    finally:
        await container.close()

    logging.info("Lifespan completed successfully.")


settings = Settings()

app = FastAPI(title="API Афиши", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

container = create_container(settings)

setup_dishka(
    container=container,
    app=app,
)
