import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Token (.env faylidan yoki muhit o'zgaruvchisidan olinadi)
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# SQLite ma'lumotlar bazasi manzili
DB_PATH: Path = BASE_DIR / os.getenv("DB_NAME", "moderation.db")

# Nazorat jurnali kanali (Audit Log Channel) ID raqami
# O'chirilgan noqonuniy xabarlar, rasmlar va jazolanganlar ma'lumoti shu kanalga yuboriladi
LOG_CHANNEL_ID_RAW = os.getenv("LOG_CHANNEL_ID", "-1004334439051").strip()
try:
    LOG_CHANNEL_ID: int | str = int(LOG_CHANNEL_ID_RAW)
except ValueError:
    LOG_CHANNEL_ID = LOG_CHANNEL_ID_RAW

# 1. Umumiy NSFW (Porn / Hentai) ONNX modeli
MODEL_DIR: Path = BASE_DIR / "models"
MODEL_PATH: Path = MODEL_DIR / "nsfw_model.onnx"
MODEL_URL: str = (
    "https://huggingface.co/deepghs/imgutils-models/resolve/main/nsfw/nsfwjs.onnx"
)

# 2. Ochiq tana a'zolari detektori (NudeNet YOLOv8n 320x320 ONNX modeli)
# Bikinidagi yopiq ko'krak (FEMALE_BREAST_COVERED) va ochiq ko'krak (FEMALE_BREAST_EXPOSED) ni aniq ajratadi
NUDENET_MODEL_PATH: Path = MODEL_DIR / "nudenet_320n.onnx"
NUDENET_MODEL_URL: str = (
    "https://raw.githubusercontent.com/notAI-tech/NudeNet/v3/nudenet/320n.onnx"
)

# Media moderatsiyasi chegaralari (Thresholds)
# TZ: Porn > 0.60 (60%) bo'lsa VIOLATION_MEDIA, Sexy (bikini/ochiq kiyim) e'tiborsiz qoldiriladi.
PORN_THRESHOLD: float = float(os.getenv("PORN_THRESHOLD", "0.60"))
HENTAI_THRESHOLD: float = float(os.getenv("HENTAI_THRESHOLD", "0.65"))
EXPOSED_BODY_THRESHOLD: float = float(os.getenv("EXPOSED_BODY_THRESHOLD", "0.45"))

# Jazo zanjiri sozlamalari
MAX_WARNINGS: int = 3
MUTE_DURATION_HOURS: int = 24

# Qoidabuzarlik signallari
VIOLATION_TEXT: str = "VIOLATION_TEXT"
VIOLATION_MEDIA: str = "VIOLATION_MEDIA"
