# 🎓 İTÜ OBS Ders Kayıt Otomasyonu (Otostop)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

İTÜ Öğrenci Bilgi Sistemi (OBS) üzerinden ders kayıt işlemini otomatikleştiren full-stack uygulama. Milisaniye düzeyinde zamanlama hassasiyeti ile kayıt saati geldiğinde derslere anında kayıt olmanızı sağlar.

> **⚠️ Sorumluluk Reddi:** Bu araç eğitim ve öğretim amaçlıdır.

## ✨ Özellikler

| Özellik | Açıklama |
|---------|----------|
| 🎯 **Hassas Zamanlama** | HTTP `Date` header geçişi ile sunucu saati ±3ms doğrulukta ölçülür |
| ⚡ **Sıfır Gecikme** | TCP+TLS bağlantı ısıtma + PreparedRequest ile ilk istek ~6ms |
| 📡 **Gerçek Zamanlı UI** | WebSocket üzerinden canlı log, geri sayım ve CRN durum takibi |
| 🔄 **Akıllı Retry** | 3sn debounce'a uygun VAL02/VAL16 retry stratejisi |
| ➕ **Toplu Kayıt** | Birden fazla CRN'yi tek istekte kayıt (maks. 12) |
| ➖ **Ders Değiştirme** | Mevcut dersleri bırakıp yerine yenisini alma (SCRN) |
| 📊 **Kalibrasyon Paneli** | Sunucu offset, RTT metrikleri ve NTP karşılaştırması |
| 🌙 **Tema Desteği** | Karanlık/aydınlık tema (next-themes) |
| 🔐 **Bulut Senkronizasyon** | Clerk auth + Supabase ile ayar/preset yedekleme |
| 🔔 **Bildirimler** | Tarayıcı bildirimi + ses efekti ile tamamlanma uyarısı |

## 🏗️ Mimari

```
┌──────────────────┐     WebSocket      ┌──────────────────┐
│   Next.js 16     │◄──────────────────►│   FastAPI         │
│   React 19       │     REST API       │   Uvicorn         │
│   shadcn/ui      │◄──────────────────►│   Pydantic v2     │
└──────────────────┘                    └────────┬─────────┘
     :3000                                       │
                                                 │ HTTPS POST
                                                 ▼
                                    ┌──────────────────────┐
                                    │  OBS API (v21)       │
                                    │  obs.itu.edu.tr      │
                                    └──────────────────────┘
```

## 🛠️ Teknoloji Yığını

| Katman | Teknoloji |
|--------|-----------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS v4 |
| **UI** | shadcn/ui, Radix UI, Lucide Icons, Motion (Framer Motion v12) |
| **Backend** | FastAPI, Uvicorn, Pydantic v2, Requests |
| **Gerçek Zamanlı** | WebSocket (FastAPI ↔ React) |
| **Auth** | Clerk (frontend) |
| **Veritabanı** | Supabase (PostgreSQL — config/preset RPC) |
| **Deploy** | Google Cloud Run (backend), Vercel (frontend) |
| **Paket Yönetimi** | Bun (frontend), pip (backend) |

## 📂 Proje Yapısı

```
├── backend/                      # FastAPI backend
│   ├── main.py                   # REST + WebSocket endpoints
│   ├── engine.py                 # Kayıt motoru (kalibrasyon, zamanlama, retry)
│   ├── models.py                 # Pydantic veri modelleri
│   ├── obs_course_service.py     # OBS ders arama proxy (LRU cache + HTML parser)
│   ├── Dockerfile                # Cloud Run container
│   └── requirements.txt          # Python bağımlılıkları
├── frontend/                     # Next.js frontend
│   ├── src/
│   │   ├── app/                  # App Router + Clerk auth
│   │   ├── components/
│   │   │   ├── dashboard.tsx     # Ana orkestratör (~900 satır)
│   │   │   ├── crn-manager.tsx   # CRN ekleme/bırakma yöneticisi
│   │   │   ├── token-input.tsx   # JWT token girişi + rehber
│   │   │   ├── calibration-card.tsx  # Kalibrasyon metrikleri
│   │   │   ├── countdown-timer.tsx   # Animasyonlu geri sayım
│   │   │   ├── live-logs.tsx     # Terminal tarzı log görüntüleyici
│   │   │   ├── settings-panel.tsx    # Kayıt ayarları
│   │   │   ├── preset-manager.tsx    # Preset kaydetme/yükleme
│   │   │   └── ...               # Diğer UI bileşenleri
│   │   ├── hooks/
│   │   │   ├── use-websocket.ts  # WebSocket + auto-reconnect
│   │   │   ├── use-notification.ts   # Bildirim + ses
│   │   │   └── use-presets.ts    # Supabase preset yönetimi
│   │   ├── lib/
│   │   │   ├── api.ts            # Typed API client
│   │   │   ├── config-service.ts # Supabase config RPC
│   │   │   ├── preset-service.ts # Supabase preset RPC
│   │   │   ├── supabase.ts       # Supabase client
│   │   │   └── utils.ts          # Yardımcı fonksiyonlar
│   │   └── proxy.ts             # Clerk auth proxy (Next.js 16)
│   ├── sql/                      # Supabase tablo + RPC tanımları
│   └── public/guide/             # Token rehberi görselleri
└── calibration/                  # Sunucu saat kalibrasyon aracı
    ├── obs_clock_calibration.py  # Cloud Run üzerinde kalibrasyon
    └── Dockerfile
```

## 🚀 Hızlı Başlangıç

### Gereksinimler

- Python 3.11+
- Node.js 18+ veya [Bun](https://bun.sh) (önerilen)
- İTÜ OBS hesabı + geçerli JWT token

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
# → http://localhost:8000  (API docs: /docs)
```

### 2. Frontend

```bash
cd frontend
cp .env.example .env.local
# .env.local içine Clerk ve Supabase anahtarlarını ekleyin

bun install          # veya: npm install
bun run dev          # veya: npm run dev
# → http://localhost:3000
```

### 3. Ortam Değişkenleri

| Değişken | Konum | Açıklama |
|----------|-------|----------|
| `NEXT_PUBLIC_API_URL` | `frontend/.env` | Backend API URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `frontend/.env.local` | Clerk public key |
| `CLERK_SECRET_KEY` | `frontend/.env.local` | Clerk secret key |
| `NEXT_PUBLIC_SUPABASE_URL` | `frontend/.env.local` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `frontend/.env.local` | Supabase anon key |

## 📖 Kullanım

1. Tarayıcıda `http://localhost:3000` adresini açın
2. OBS web arayüzünden JWT token'ı kopyalayın *(DevTools → Network → Authorization header)*
3. Token'ı yapıştırın (uygulama geçerliliği otomatik kontrol eder)
4. **Eklenecek Dersler** bölümüne CRN'leri ekleyin (maks. 12)
5. Gerekirse **Bırakılacak Dersler** bölümüne bırakılacak CRN'leri ekleyin
6. Kayıt saatini ayarlayın (varsayılan: `14:00:00`)
7. **"Kayıt Başlat"** butonuna basın *(kayıt saatinden 2-5 dakika önce)*
8. Sistem otomatik kalibre olacak ve tam saatte isteği gönderecektir

## ⏱️ Zamanlama Mekanizması

```
tetik = hedef_epoch + server_offset - rtt_tek_yon + buffer
```

| Bileşen | Açıklama |
|---------|----------|
| `server_offset` | OBS sunucu saati ile local saat farkı (HTTP Date header ile ölçülür) |
| `rtt_tek_yon` | Tek yön ağ gecikmesi (RTT/2) |
| `buffer` | Güvenlik tamponu (varsayılan: 5ms) |

**Motor fazları:** `idle` → `token_check` → `calibrating` → `waiting` → `registering` → `done`

## 🔑 OBS API Yanıt Kodları

| Kod | Anlamı |
|-----|--------|
| `statusCode: 0` | ✅ Başarılı |
| `VAL02` | ⏳ Kayıt dönemi henüz açılmadı |
| `VAL03` | ℹ️ Ders zaten alınmış |
| `VAL06` | 🔴 Kontenjan dolu |
| `VAL09` | ⚠️ Ders çakışması |
| `VAL16` | 🔄 Debounce (3sn içinde tekrar istek) |
| `VAL22` | ⬆️ Yükseltmeye alınan ders çakışması |

## ☁️ Deployment

### Backend (Google Cloud Run)

```bash
gcloud run deploy itu-otostop-api \
  --source backend/ \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi --cpu 2 \
  --timeout 3600 \
  --min-instances 1 --max-instances 2 \
  --no-cpu-throttling --cpu-boost \
  --session-affinity \
  --set-env-vars "ENV=production,CORS_ORIGINS=https://itu-otostop.vercel.app"
```

### Frontend (Vercel)

Frontend, `main` branch'e push edildiğinde Vercel üzerinden otomatik deploy edilir.

## 📄 Lisans

Bu proje [Apache License 2.0](LICENSE) altında lisanslanmıştır.
