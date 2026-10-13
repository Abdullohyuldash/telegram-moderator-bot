import asyncio
import io
import logging
import urllib.request
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, UnidentifiedImageError

from config import (
    EXPOSED_BODY_THRESHOLD,
    HENTAI_THRESHOLD,
    MODEL_PATH,
    MODEL_URL,
    NUDENET_MODEL_PATH,
    NUDENET_MODEL_URL,
    PORN_THRESHOLD,
    VIOLATION_MEDIA,
)

logger = logging.getLogger(__name__)

# 1. NSFWJS ONNX modelining klasslari tartibi (224x224)
NSFW_LABELS: list[str] = ["drawings", "hentai", "neutral", "porn", "sexy"]
NSFW_INPUT_SIZE: tuple[int, int] = (224, 224)

# 2. NudeNet 320n ONNX modelining 18 ta tana a'zolari klasslari (320x320)
NUDENET_LABELS: list[str] = [
    "FEMALE_GENITALIA_COVERED",
    "FACE_FEMALE",
    "BUTTOCKS_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_BREAST_EXPOSED",
    "ANUS_EXPOSED",
    "FEET_EXPOSED",
    "BELLY_COVERED",
    "FEET_COVERED",
    "ARMPITS_COVERED",
    "ARMPITS_EXPOSED",
    "FACE_MALE",
    "BELLY_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_COVERED",
    "FEMALE_BREAST_COVERED",
    "BUTTOCKS_COVERED",
]
NUDENET_INPUT_SIZE: int = 320

# Faqat BUTUNLAY OCHIQ (yalang'och) ko'krak va jinsiy a'zolar ro'yxati.
# E'tibor bering: FEMALE_BREAST_COVERED (bikini/suzish kiyimi) bu ro'yxatga kirmaydi!
EXPLICIT_EXPOSED_LABELS: set[str] = {
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
}

_nsfw_session: ort.InferenceSession | None = None
_nudenet_session: ort.InferenceSession | None = None


def _download_file_if_missing(file_path: Path, url: str, description: str) -> Path:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if not file_path.exists() or file_path.stat().st_size < 1024:
        logger.info("%s yuklab olinmoqda: %s -> %s", description, url, file_path)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Telegram-Moderator-Bot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=90) as response:
            data = response.read()
        temp_path = file_path.with_suffix(".onnx.tmp")
        temp_path.write_bytes(data)
        temp_path.replace(file_path)
        logger.info(
            "%s muvaffaqiyatli yuklandi (%.2f MB).",
            description,
            len(data) / (1024 * 1024),
        )
    return file_path


def ensure_model_exists(
    model_path: Path = MODEL_PATH, model_url: str = MODEL_URL
) -> Path:
    """NSFWJS va NudeNet ONNX modellarining mavjudligini tekshiradi va kerak bo'lsa yuklab oladi."""
    _download_file_if_missing(model_path, model_url, "NSFWJS ONNX modeli")
    _download_file_if_missing(
        NUDENET_MODEL_PATH, NUDENET_MODEL_URL, "NudeNet 320n ONNX detektori"
    )
    return model_path


def _create_cpu_session(path: Path) -> ort.InferenceSession:
    sess_options = ort.SessionOptions()
    sess_options.intra_op_num_threads = 2
    sess_options.inter_op_num_threads = 1
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(
        str(path),
        sess_options=sess_options,
        providers=["CPUExecutionProvider"],
    )


def get_onnx_session(model_path: Path = MODEL_PATH) -> ort.InferenceSession:
    """NSFWJS va NudeNet ONNX Runtime sessiyalarini (singleton) tayyorlaydi."""
    global _nsfw_session, _nudenet_session
    ensure_model_exists(model_path)
    if _nsfw_session is None:
        _nsfw_session = _create_cpu_session(model_path)
    if _nudenet_session is None:
        _nudenet_session = _create_cpu_session(NUDENET_MODEL_PATH)
    return _nsfw_session


def get_nudenet_session() -> ort.InferenceSession:
    global _nudenet_session
    if _nudenet_session is None:
        ensure_model_exists()
        _nudenet_session = _create_cpu_session(NUDENET_MODEL_PATH)
    return _nudenet_session


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """NSFWJS uchun 224x224 RGB NHWC (1, 224, 224, 3) float32 massiv tayyorlaydi."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        rgb_img = img.convert("RGB").resize(NSFW_INPUT_SIZE, Image.Resampling.BILINEAR)
        arr = np.asarray(rgb_img, dtype=np.float32) / 255.0
        return arr[None, ...]


def preprocess_nudenet_image(image_bytes: bytes) -> np.ndarray:
    """
    NudeNet YOLOv8n (320n.onnx) uchun rasmni kvadrat shaklga (padding bilan) keltirib,
    320x320 NCHW (1, 3, 320, 320) float32 massivga o'tkazadi.
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        rgb_img = img.convert("RGB")
        w, h = rgb_img.size
        max_side = max(w, h)
        padded = Image.new("RGB", (max_side, max_side), (0, 0, 0))
        padded.paste(rgb_img, (0, 0))
        resized = padded.resize(
            (NUDENET_INPUT_SIZE, NUDENET_INPUT_SIZE), Image.Resampling.BILINEAR
        )
        arr = np.asarray(resized, dtype=np.float32) / 255.0
        # HWC (320, 320, 3) -> NCHW (1, 3, 320, 320)
        return np.transpose(arr, (2, 0, 1))[None, ...]


def detect_exposed_body_parts(image_bytes: bytes) -> dict[str, float]:
    """
    NudeNet 320n.onnx yordamida rasm ichidagi har bir tana a'zosi toifasi bo'yicha
    maksimal aniqlangan ishonchlilik (score) ko'rsatkichini qaytaradi.
    Masalan: {'FEMALE_BREAST_EXPOSED': 0.84, 'FEMALE_BREAST_COVERED': 0.0, ...}
    """
    session = get_nudenet_session()
    input_tensor = preprocess_nudenet_image(image_bytes)
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    outputs = session.run([output_name], {input_name: input_tensor})
    # output[0] o'lchami: (1, 22, 2100) -> transpose: (2100, 22)
    predictions = np.transpose(np.squeeze(outputs[0]))
    class_probs = predictions[:, 4:]  # (2100, 18)
    max_scores = np.max(class_probs, axis=0)

    return {
        label: float(max_scores[idx]) for idx, label in enumerate(NUDENET_LABELS)
    }


def predict_nsfw_scores(image_bytes: bytes) -> dict[str, float]:
    """
    NSFWJS modelidan 5 ta toifa bo'yicha ehtimolliklarni hisoblaydi:
    {'drawings': ..., 'hentai': ..., 'neutral': ..., 'porn': ..., 'sexy': ...}
    """
    session = get_onnx_session()
    input_tensor = preprocess_image(image_bytes)
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    outputs = session.run([output_name], {input_name: input_tensor})
    probs = outputs[0][0]
    return {label: float(probs[idx]) for idx, label in enumerate(NSFW_LABELS)}


def _evaluate_media_sync(image_bytes: bytes) -> str | None:
    """
    Ikki bosqichli aniq tahlil:
    1. NudeNet 320n detektori:
       - Ayol ko'kragi uchlari ochiq (`FEMALE_BREAST_EXPOSED >= 0.45`) yoki
       - Ochiq jinsiy a'zolar (`FEMALE_GENITALIA_EXPOSED`, `MALE_GENITALIA_EXPOSED`, `ANUS_EXPOSED >= 0.45`)
       aniqlansa -> VIOLATION_MEDIA.
       - Bikini / yopiq ko'krak (`FEMALE_BREAST_COVERED`) e'tiborsiz qoldiriladi (o'chirilmaydi!).
    2. NSFWJS klassifikatori:
       - `Porn > 0.60` (60%) yoki ochiq `Hentai > 0.65` (65%) bo'lsa -> VIOLATION_MEDIA.
       - `Sexy` toifasi (bikini / ochiqroq kiyim) 100% e'tiborsiz qoldiriladi!
    """
    try:
        body_scores = detect_exposed_body_parts(image_bytes)
        nsfw_scores = predict_nsfw_scores(image_bytes)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning("Rasmni o'qishda xatolik (o'tkazib yuborildi): %s", exc)
        return None
    except Exception as exc:
        logger.error("ONNX model tahlilida xatolik: %s", exc)
        return None

    breast_exposed = body_scores.get("FEMALE_BREAST_EXPOSED", 0.0)
    breast_covered = body_scores.get("FEMALE_BREAST_COVERED", 0.0)
    f_genitalia = body_scores.get("FEMALE_GENITALIA_EXPOSED", 0.0)
    m_genitalia = body_scores.get("MALE_GENITALIA_EXPOSED", 0.0)
    anus_exposed = body_scores.get("ANUS_EXPOSED", 0.0)

    porn_score = nsfw_scores.get("porn", 0.0)
    hentai_score = nsfw_scores.get("hentai", 0.0)
    sexy_score = nsfw_scores.get("sexy", 0.0)

    logger.info(
        "📊 Media tahlili | Ochiq ko'krak=%.1f%% (Yopiq/Bikini=%.1f%%), Jinsiy a'zo=%.1f%% | Porn=%.1f%%, Hentai=%.1f%%, Sexy=%.1f%%",
        breast_exposed * 100,
        breast_covered * 100,
        max(f_genitalia, m_genitalia, anus_exposed) * 100,
        porn_score * 100,
        hentai_score * 100,
        sexy_score * 100,
    )

    # 1. NudeNet: Ayol ko'kragi butunlay ochiq (ko'krak uchi ko'ringan) yoki jinsiy a'zolar ochiq bo'lsa
    for label in EXPLICIT_EXPOSED_LABELS:
        if body_scores.get(label, 0.0) >= EXPOSED_BODY_THRESHOLD:
            return VIOLATION_MEDIA

    # 2. NSFWJS: Haqiqiy pornografiya (Porn > 60%)
    # Eslatma: Agar NudeNet rasmni aniq Bikini (FEMALE_BREAST_COVERED >= 0.45) deb ko'rsa
    # va hech qanday ochiq a'zo topilmasa, Porn chegarasi yanada qat'iy (0.75) olinadi.
    effective_porn_threshold = (
        0.75
        if (breast_covered >= 0.45 and breast_exposed < 0.25 and f_genitalia < 0.25 and m_genitalia < 0.25)
        else PORN_THRESHOLD
    )
    if porn_score > effective_porn_threshold:
        return VIOLATION_MEDIA

    # 3. Ochiq 18+ Hentai (Hentai > 65%)
    if hentai_score > HENTAI_THRESHOLD:
        return VIOLATION_MEDIA

    return None


async def check_media(image_bytes: bytes | None) -> str | None:
    """
    Asinxron media tekshiruvi: CPU'dagi ONNX hisoblashni alohida oqimda (thread)
    bajarib, VIOLATION_MEDIA yoki None qaytaradi.
    """
    if not image_bytes:
        return None
    return await asyncio.to_thread(_evaluate_media_sync, image_bytes)
