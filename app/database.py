from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# Используем SQLite для начала (создаст файл bot.db)
# В будущем легко сменим на postgresql://...
DATABASE_URL = "sqlite+aiosqlite:///./bot.db"

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# Функция для получения сессии БД (понадобится в хэндлерах)
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session