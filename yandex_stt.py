import os
import aiohttp

YC_API_KEY = os.getenv("YC_API_KEY", "").strip()
YC_STT_LANG = os.getenv("YC_STT_LANG", "ru-RU").strip()

STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"

class YandexSTTError(RuntimeError):
    pass

async def stt_oggopus(ogg_bytes: bytes, lang: str | None = None) -> str:
    if not YC_API_KEY:
        raise YandexSTTError("YC_API_KEY is not set (check .env)")

    params = {
        "lang": (lang or YC_STT_LANG or "ru-RU"),
        "format": "oggopus",
    }
    headers = {"Authorization": f"Api-Key {YC_API_KEY}"}

    async with aiohttp.ClientSession() as session:
        async with session.post(STT_URL, params=params, data=ogg_bytes, headers=headers) as r:
            raw = await r.text()
            if r.status != 200:
                raise YandexSTTError(f"HTTP {r.status}: {raw}")
            try:
                data = await r.json(content_type=None)
            except Exception:
                raise YandexSTTError(f"Bad JSON: {raw}")

    text = (data.get("result") or "").strip()
    if not text:
        raise YandexSTTError(f"Empty result: {data}")
    return text
