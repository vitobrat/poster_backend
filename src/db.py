from sqlalchemy.ext.asyncio import create_async_engine

from src.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
