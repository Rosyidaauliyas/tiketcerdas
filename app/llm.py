"""Lapisan LLM dengan 3 mode: mock (tanpa key), openai_compat (Groq/Gemini gratis), anthropic.

Mode openai_compat punya: retry otomatis, timeout, model cadangan (fallback),
dan pesan error yang mudah dibaca.
"""
import json
import logging
import os
import re

from pydantic import ValidationError

from .schemas import Classification

log = logging.getLogger("tiketcerdas.llm")

PROVIDER = os.getenv("LLM_PROVIDER", "mock").strip().lower()

# Status HTTP yang layak dicoba ulang dengan model cadangan
FALLBACK_STATUS = {404, 408, 409, 429, 500, 502, 503, 504}

SYSTEM_PROMPT = (
    "Kamu adalah asisten triase tiket dukungan pelanggan untuk sebuah perusahaan di Indonesia. "
    "Klasifikasikan tiket, tentukan prioritas (kritis = layanan mati/kehilangan uang/data bocor; "
    "tinggi = fitur utama rusak; sedang = gangguan kecil; rendah = pertanyaan/saran), "
    "buat ringkasan satu kalimat, dan tulis draf balasan yang sopan dalam bahasa yang sama "
    "dengan pelanggan. Jangan menjanjikan hal yang tidak pasti."
)

JSON_INSTRUCTION = (
    "Balas HANYA dengan satu objek JSON valid, tanpa teks lain, dengan kunci: "
    "category (billing|teknis|akun|pengiriman|saran|lainnya), "
    "priority (rendah|sedang|tinggi|kritis), "
    "sentiment (positif|netral|negatif), "
    "summary (string, satu kalimat), "
    "suggested_reply (string, draf balasan sopan)."
)


def model_name() -> str:
    if PROVIDER == "openai_compat":
        return os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    if PROVIDER == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
    return "rule-based"


def _model_chain() -> list[str]:
    """Model utama + cadangan dari LLM_FALLBACK_MODELS (dipisah koma), tanpa duplikat."""
    chain = [model_name()]
    for m in os.getenv("LLM_FALLBACK_MODELS", "").split(","):
        m = m.strip()
        if m and m not in chain:
            chain.append(m)
    return chain


# ---------- Pesan error yang mudah dibaca ----------
_HINTS = {
    400: "Permintaan ditolak (cek nama model dan format request).",
    401: "API key tidak valid. Cek LLM_API_KEY di file .env.",
    403: "Akses ditolak. Key tidak punya izin atau wilayah tidak didukung.",
    404: "Model tidak ditemukan. Cek LLM_MODEL (atau LLM_BASE_URL) di file .env.",
    429: "Kuota/rate limit habis. Tunggu sebentar lalu coba lagi.",
    500: "Server LLM bermasalah. Coba lagi.",
    503: "Server LLM sedang sibuk. Coba lagi sebentar lagi.",
}


def _explain(e: Exception) -> str:
    status = getattr(e, "status_code", None)
    if status:
        return f"HTTP {status}: {_HINTS.get(status, 'Terjadi kesalahan dari server LLM.')}"
    if isinstance(e, KeyError):
        return f"Variabel environment {e} belum diisi di file .env."
    if isinstance(e, ValueError):
        return str(e)
    name = type(e).__name__
    if "Connection" in name or "Timeout" in name:
        return "Tidak bisa terhubung ke server LLM (cek internet atau LLM_BASE_URL)."
    return f"{name}: {e}"


# ---------- Mode 1: mock (tanpa API key) ----------
_REPLIES = {
    "billing": "Mohon maaf atas ketidaknyamanannya. Tim kami akan memeriksa tagihan Anda dan segera menghubungi Anda.",
    "teknis": "Terima kasih sudah melapor. Tim teknis kami akan menelusuri kendala ini dan mengabari Anda.",
    "akun": "Terima kasih sudah menghubungi kami. Demi keamanan, mohon konfirmasi email terdaftar agar kami bantu pulihkan akses akun Anda.",
    "pengiriman": "Mohon maaf atas keterlambatannya. Kami akan mengecek status pesanan Anda ke pihak ekspedisi.",
    "saran": "Terima kasih atas masukannya. Saran Anda sudah kami teruskan ke tim produk.",
    "lainnya": "Terima kasih sudah menghubungi kami. Mohon jelaskan lebih detail agar kami dapat membantu.",
}


def _has(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def _mock_classify(text: str) -> Classification:
    t = text.lower()
    if _has(t, ["login", "password", "kata sandi", "akun", "otp"]):
        cat = "akun"
    elif _has(t, ["tagihan", "ditagih", "bayar", "pembayaran", "invoice", "tertagih"]):
        cat = "billing"
    elif _has(t, ["kirim", "paket", "pesanan", "resi", "belum sampai", "ekspedisi"]):
        cat = "pengiriman"
    elif _has(t, ["error", "bug", "crash", "gagal", "lemot", "tidak bisa", "aplikasi"]):
        cat = "teknis"
    elif _has(t, ["saran", "usul", "fitur", "semoga"]):
        cat = "saran"
    else:
        cat = "lainnya"

    if _has(t, ["data bocor", "diretas", "hack", "dibobol", "kehilangan uang", "semua pengguna", "down"]):
        pri = "kritis"
    elif _has(t, ["refund", "belum sampai", "tidak bisa", "gagal", "error", "crash", "ditagih dua"]):
        pri = "tinggi"
    elif _has(t, ["lambat", "lemot", "salah", "kurang"]):
        pri = "sedang"
    else:
        pri = "rendah"

    neg = sum(w in t for w in ["kecewa", "marah", "buruk", "parah", "lambat", "refund", "gagal", "error", "belum", "tidak"])
    pos = sum(w in t for w in ["terima kasih", "bagus", "mantap", "puas", "suka"])
    sent = "negatif" if neg > pos else "positif" if pos > neg else "netral"

    snippet = " ".join(text.split())[:110]
    return Classification(
        category=cat, priority=pri, sentiment=sent,
        summary=f"Tiket {cat}: {snippet}", suggested_reply=_REPLIES[cat],
    )


# ---------- Mode 2: openai_compat (Groq / Gemini gratis) ----------
def _parse_json(raw: str) -> Classification:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return Classification.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError("Respons model bukan JSON klasifikasi yang valid.") from e


def _openai_compat(text: str) -> Classification:
    from openai import APIConnectionError, APIStatusError, OpenAI

    client = OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
        max_retries=2,  # retry otomatis untuk 429/5xx, dengan jeda yang bertambah
        timeout=60,
    )
    last_error: Exception | None = None

    for model in _model_chain():
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + " " + JSON_INSTRUCTION},
                    {"role": "user", "content": f"Tiket pelanggan:\n\n{text}"},
                ],
            )
            return _parse_json(resp.choices[0].message.content or "")
        except APIStatusError as e:
            if e.status_code not in FALLBACK_STATUS:
                raise  # 400/401/403: model cadangan tidak akan membantu
            last_error = e
            log.warning("Model %s gagal (HTTP %s), mencoba model berikutnya", model, e.status_code)
        except APIConnectionError as e:
            last_error = e
            log.warning("Model %s gagal tersambung (%s), mencoba model berikutnya", model, type(e).__name__)

    assert last_error is not None
    raise last_error


# ---------- Mode 3: anthropic (berbayar, tool use) ----------
def _anthropic(text: str) -> Classification:
    from anthropic import Anthropic

    tool = {
        "name": "classify_ticket",
        "description": "Simpan hasil triase tiket dukungan pelanggan.",
        "input_schema": Classification.model_json_schema(),
    }
    resp = Anthropic(max_retries=3, timeout=60).messages.create(
        model=model_name(), max_tokens=800, system=SYSTEM_PROMPT,
        tools=[tool], tool_choice={"type": "tool", "name": "classify_ticket"},
        messages=[{"role": "user", "content": f"Tiket pelanggan:\n\n{text}"}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return Classification.model_validate(block.input)
    raise ValueError("Model tidak mengembalikan hasil klasifikasi.")


# ---------- Titik masuk ----------
def classify_ticket(text: str) -> Classification:
    try:
        if PROVIDER == "openai_compat":
            return _openai_compat(text)
        if PROVIDER == "anthropic":
            return _anthropic(text)
        return _mock_classify(text)
    except Exception as e:
        # Pesan ini yang tampil di UI (HTTP 502 dari main.py)
        raise RuntimeError(_explain(e)) from e