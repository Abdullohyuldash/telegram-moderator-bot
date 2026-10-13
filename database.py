from pathlib import Path
import aiosqlite
from config import DB_PATH

CREATE_WARNINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_warnings (
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    warn_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, chat_id)
);
"""


async def init_db(db_path: Path | str = DB_PATH) -> None:
    """SQLite ma'lumotlar bazasi va user_warnings jadvalini yaratadi."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(CREATE_WARNINGS_TABLE_SQL)
        await db.commit()


async def add_warning(
    user_id: int, chat_id: int, db_path: Path | str = DB_PATH
) -> int:
    """
    Foydalanuvchining ma'lum guruhdagi ogohlantirishlar sonini (warn_count) 1 taga oshiradi
    va yangilangan warn_count qiymatini qaytaradi.
    """
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO user_warnings (user_id, chat_id, warn_count, last_updated)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, chat_id) DO UPDATE SET
                warn_count = warn_count + 1,
                last_updated = CURRENT_TIMESTAMP;
            """,
            (user_id, chat_id),
        )
        await db.commit()

        async with db.execute(
            "SELECT warn_count FROM user_warnings WHERE user_id = ? AND chat_id = ?;",
            (user_id, chat_id),
        ) as cursor:
            row = await cursor.fetchone()
            return int(row[0]) if row else 1


async def get_warnings(
    user_id: int, chat_id: int, db_path: Path | str = DB_PATH
) -> int:
    """Foydalanuvchining joriy ogohlantirishlar sonini qaytaradi."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT warn_count FROM user_warnings WHERE user_id = ? AND chat_id = ?;",
            (user_id, chat_id),
        ) as cursor:
            row = await cursor.fetchone()
            return int(row[0]) if row else 0


async def reset_warnings(
    user_id: int, chat_id: int, db_path: Path | str = DB_PATH
) -> None:
    """Foydalanuvchining ogohlantirishlar sonini 0 ga tushiradi."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE user_warnings
            SET warn_count = 0, last_updated = CURRENT_TIMESTAMP
            WHERE user_id = ? AND chat_id = ?;
            """,
            (user_id, chat_id),
        )
        await db.commit()
