# 🎓 İTÜ OBS Ders Kayıt Otomasyonu

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

İTÜ Öğrenci Bilgi Sistemi (OBS) üzerinden ders kayıt işlemini otomatikleştiren full-stack uygulama. Milisaniye düzeyinde zamanlama hassasiyeti ile kayıt saati geldiğinde derslere anında kayıt olmanızı sağlar.

## ✨ Özellikler

- **🎯 Hassas Zamanlama** — Sunucu saati HTTP `Date` header geçişi ile ±3ms doğrulukta ölçülür
- **⚡ Sıfır Gecikme** — TCP+TLS bağlantı ısıtma + PreparedRequest ile ilk istek ~6ms
- **📡 Gerçek Zamanlı UI** — WebSocket üzerinden canlı log akışı, geri sayım ve CRN durum takibi
- **🔄 Akıllı Retry** — 3 saniyelik sunucu debounce'una uygun VAL02/VAL16 retry stratejisi
- **➕ Ders Ekleme (ECRN)** — Birden fazla CRN'yi tek istekte kayıt
- **➖ Ders Bırakma (SCRN)** — Mevcut dersleri bırakıp yerine yenisini alma
- **🌙 Karanlık/Aydınlık Tema** — next-themes ile otomatik tema desteği
- **📊 Kalibrasyon Paneli** — Sunucu offset, RTT ve NTP karşılaştırması

## 🏗️ Mimari

```
┌──────────────────┐     WebSocket      ┌──────────────────┐
│   Next.js 16     │◄──────────────────►│   FastAPI         │
│   React 19       │     REST API       │   Uvicorn         │
│   shadcn/ui      │◄──────────────────►│   Pydantic v2     │
│   Bun            │                    │   Requests        │
└──────────────────┘                    └────────┬─────────┘
     :3000                                       │
                                                 │ HTTPS POST
                                                 ▼
                                    ┌──────────────────────┐
                                    │  OBS API (v21)       │
                                    │  obs.itu.edu.tr      │
                                    └──────────────────────┘
```

## 📂 Proje Yapısı

```
├── backend/                 # FastAPI backend
│   ├── main.py              # REST + WebSocket endpoints
│   ├── engine.py            # Kayıt motoru (zamanlama, retry, kalibrasyon)
│   ├── models.py            # Pydantic veri modelleri
│   └── requirements.txt     # Python bağımlılıkları
├── frontend/                # Next.js frontend
│   ├── src/
│   │   ├── app/             # App Router (layout, page)
│   │   ├── components/      # React bileşenleri
│   │   │   ├── dashboard.tsx         # Ana orkestratör
│   │   │   ├── crn-manager.tsx       # CRN ekleme/bırakma yöneticisi
│   │   │   ├── token-input.tsx       # JWT token girişi
│   │   │   ├── calibration-card.tsx  # Kalibrasyon metrikleri
│   │   │   ├── countdown-timer.tsx   # Animasyonlu geri sayım
│   │   │   ├── live-logs.tsx         # Terminal tarzı log görüntüleyici
│   │   │   ├── settings-panel.tsx    # Kayıt ayarları
│   │   │   ├── connection-status.tsx # WebSocket durum göstergesi
│   │   │   └── theme-toggle.tsx      # Tema değiştirici
│   │   ├── hooks/
│   │   │   └── use-websocket.ts      # WebSocket hook
│   │   └── lib/
│   │       ├── api.ts                # Typed API client
│   │       └── utils.ts              # Yardımcı fonksiyonlar
│   └── package.json
└── claudeai2-optimal.py     # Standalone CLI versiyonu
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
# → http://localhost:8000
```

### 2. Frontend

```bash
cd frontend
bun install          # veya: npm install
bun run dev          # veya: npm run dev
# → http://localhost:3000
```

### 3. Kullanım

1. Tarayıcıda `http://localhost:3000` adresini açın
2. OBS web arayüzünden JWT token'ı kopyalayıp yapıştırın
3. Eklemek istediğiniz CRN'leri **Eklenecek Dersler** bölümüne ekleyin
4. Bırakmak istediğiniz CRN'leri **Bırakılacak Dersler** bölümüne ekleyin
5. Kayıt saatini ayarlayın (varsayılan: 14:00:00)
6. **"Kayıt Başlat"** butonuna basın (kayıt saatinden 2-5 dakika önce)
7. Sistem otomatik kalibre olacak ve tam saatte isteği gönderecektir

## ⏱️ Zamanlama Formülü

```
tetik = hedef_epoch + server_offset - rtt_tek_yon + buffer
```

Bu formül, isteğin sunucuya tam hedef saatte (ör: 14:00:00.000) ulaşmasını sağlar.

## 🔑 Token Alma

1. [obs.itu.edu.tr](https://obs.itu.edu.tr) adresine giriş yapın
2. Tarayıcı DevTools → Network sekmesini açın
3. Herhangi bir API isteğinin `Authorization: Bearer ...` header'ından token'ı kopyalayın
4. Token geçerlilik süresi: ~6 saat

## ⚠️ Önemli Notlar

- **Sunucu NTP'den ~2 saniye geride** — NTP kullanmak 2s erken tetikleme → VAL02 hatası verir
- **3 saniye debounce** — Sunucu aynı oturumdan <3s aralıkla gelen istekleri yok sayar (VAL16)
- **Token yenileme** — Her kayıt oturumundan önce taze token gerekir
- Bu araç sadece eğitim amaçlıdır

## 🛠️ Teknoloji Yığını

| Katman         | Teknoloji                                           |
| -------------- | --------------------------------------------------- |
| Frontend       | Next.js 16, React 19, TypeScript, Tailwind CSS v4   |
| UI             | shadcn/ui, Lucide Icons, motion (Framer Motion v12) |
| Backend        | FastAPI, Uvicorn, Pydantic v2, Requests             |
| Gerçek Zamanlı | WebSocket (FastAPI ↔ React)                         |
| Paket Yönetimi | Bun (frontend), pip (backend)                       |
| Tema           | next-themes (karanlık/aydınlık)                     |
| Bildirimler    | Sonner (toast)                                      |

## ❓ Sık Sorulan Sorular

- **GitHub Copilot Kota Kullanımı**: GitHub Copilot kullanırken hangi kota kullanıldığını merak ediyor musunuz? [Copilot Kota SSS](.github/COPILOT-QUOTA-FAQ.md) dökümanına göz atın.

## 📄 Lisans

Bu proje [Apache License 2.0](LICENSE) altında lisanslanmıştır. Türev çalışmalarda değişikliklerin belirtilmesi zorunludur.
