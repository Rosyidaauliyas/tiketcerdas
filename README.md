# 🎫 TiketCerdas — Triase Tiket Dukungan Pelanggan dengan LLM

Aplikasi fullstack kecil yang memakai **LLM API** untuk membaca tiket pelanggan lalu otomatis menghasilkan
**kategori, prioritas, sentimen, ringkasan satu kalimat, dan draf balasan**. Hasil disimpan di SQLite
dan ditampilkan sebagai riwayat di antarmuka web.

## Mengapa proyek ini?
Tim dukungan pelanggan sering menghabiskan waktu memilah tiket secara manual. Proyek ini menunjukkan LLM
sebagai **komponen produk nyata**: output terstruktur, validasi, penyimpanan data, REST API, dan UI.

## Arsitektur
```
Browser (static/index.html)
   │  POST /api/tickets
   ▼
FastAPI (app/main.py) ──► app/llm.py ──► mock | Groq/Gemini (gratis) | Anthropic
   │                                          │
   └── app/db.py (SQLite) ◄── validasi Pydantic (app/schemas.py)
```

Keputusan desain:
- **Provider dapat diganti lewat environment** (`LLM_PROVIDER`), kode aplikasi tidak berubah.
- **Output terstruktur**: JSON mode (Groq/Gemini) atau tool use (Anthropic), lalu divalidasi Pydantic (enum kategori/prioritas).
- **Mode `mock`** supaya siapa pun bisa menjalankan demo tanpa API key; tes juga tidak butuh key atau biaya.
- **Error handling**: kegagalan API/jaringan dikembalikan sebagai HTTP 502 dengan pesan jelas.
- **Keamanan dasar**: key hanya dari environment (`.env` ada di `.gitignore`); UI meng-escape HTML (anti-XSS).

## Tech stack
Python 3.11+ · FastAPI · Pydantic · SQLite · OpenAI-compatible SDK (Groq/Gemini) · Anthropic SDK · HTML/CSS/JS · pytest

## Menjalankan (tanpa API key, mode demo)
```bash
git clone https://github.com/Rosyidaauliyas/tiketcerdas.git
cd tiketcerdas
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # Windows: copy .env.example .env
uvicorn app.main:app --reload
```
Buka http://127.0.0.1:8000 (dokumentasi API di `/docs`).

## Memakai LLM sungguhan (gratis)
1. Buat API key gratis di **Groq** (https://console.groq.com/keys) atau **Google AI Studio** (https://aistudio.google.com/apikey). Kuota gratis dapat berubah, cek halaman penyedia.
2. Di `.env`, ubah:
```
LLM_PROVIDER=openai_compat
LLM_API_KEY=key_kamu
```
3. Jalankan ulang `uvicorn`. Lencana di atas halaman akan berubah menjadi "LLM aktif: ...".

Untuk Gemini, ganti `LLM_BASE_URL` dan `LLM_MODEL` sesuai komentar di `.env.example`.
Untuk Claude API (berbayar), pakai `LLM_PROVIDER=anthropic` dan isi `ANTHROPIC_API_KEY`.

## Tes
```bash
pytest -q
```

## Endpoint
| Method | Path | Deskripsi |
|---|---|---|
| POST | `/api/tickets` | Kirim `{"text": "..."}`, dapat hasil klasifikasi + tersimpan |
| GET | `/api/tickets` | 50 tiket terakhir |
| GET | `/api/health` | Provider dan model yang aktif |

## Ide pengembangan
- Autentikasi agen, filter prioritas/kategori
- Evaluasi akurasi dengan dataset tiket berlabel
- Deploy (Render/Railway) + Docker

## Screenshot
_Tambahkan screenshot (mode LLM aktif) di folder `docs/`._
