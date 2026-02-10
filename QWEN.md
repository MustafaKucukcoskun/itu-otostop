# 🎓 İTÜ OBS Ders Kayıt Otomasyonu (Otostop)

## Proje Genel Bakış

İTÜ Öğrenci Bilgi Sistemi (OBS) üzerinden ders kayıt işlemini otomatikleştiren full-stack bir uygulamadır. Milisaniye düzeyinde zamanlama hassasiyeti ile kayıt saati geldiğinde derslere anında kayıt olmanızı sağlar. Proje, Next.js 16 ve FastAPI tabanlı modern bir mimariye sahiptir.

### Ana Özellikler
- **🎯 Hassas Zamanlama** — Sunucu saati HTTP `Date` header geçişi ile ±3ms doğrulukta ölçülür
- **⚡ Sıfır Gecikme** — TCP+TLS bağlantı ısıtma + PreparedRequest ile ilk istek ~6ms
- **📡 Gerçek Zamanlı UI** — WebSocket üzerinden canlı log akışı, geri sayım ve CRN durum takibi
- **🔄 Akıllı Retry** — 3 saniyelik sunucu debounce'una uygun VAL02/VAL16 retry stratejisi
- **➕ Ders Ekleme (ECRN)** — Birden fazla CRN'yi tek istekte kayıt
- **➖ Ders Bırakma (SCRN)** — Mevcut dersleri bırakıp yerine yenisini alma
- **🌙 Karanlık/Aydınlık Tema** — next-themes ile otomatik tema desteği
- **📊 Kalibrasyon Paneli** — Sunucu offset, RTT ve NTP karşılaştırması

## Proje Mimarisi

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

## Geliştirme Ortamı Kurulumu

### Gereksinimler
- Python 3.11+
- Node.js 18+ veya [Bun](https://bun.sh) (önerilen)
- İTÜ OBS hesabı + geçerli JWT token

### Backend Kurulumu
```bash
cd backend
pip install -r requirements.txt
python main.py
# → http://localhost:8000
```

### Frontend Kurulumu
```bash
cd frontend
bun install          # veya: npm install
bun run dev          # veya: npm run dev
# → http://localhost:3000
```

## Ana Dosya ve Dizinler

### Backend (/backend)
- `main.py` — REST endpoints + WebSocket `/ws` + global `AppState` singleton
- `engine.py` — Registration engine: calibration, busy-wait countdown, retry loop. Runs in a daemon thread, communicates via event queue → WebSocket broadcast
- `models.py` — Pydantic v2 models (ConfigRequest, RegistrationState, CalibrationResult, WSEvent, CRNStatus enum)
- `obs_course_service.py` — OBS public API proxy with LRU cache + TTL. Parses HTML course tables (BeautifulSoup). Searches popular departments first for fast CRN lookups

### Frontend (/frontend)
- `src/components/dashboard.tsx` — Main orchestrator (~900 lines). All state lives here (no Redux/Zustand). Auto-saves config to backend (500ms debounce) + Supabase cloud
- `src/hooks/use-websocket.ts` — WebSocket hook with auto-reconnect, ping/pong latency, event dispatching (log, state, countdown, crn_update, calibration, done)
- `src/lib/api.ts` — Typed fetch wrapper for all backend endpoints
- `src/app/page.tsx` — Ana sayfa bileşeni

## Ana Geliştirme Desenleri

### Yeni Endpoint Ekleme
- Backend'de `backend/main.py` dosyasını düzenle
- Frontend'de `frontend/src/lib/api.ts` dosyasına yazılan fonksiyonu ekle

### WebSocket Event Ekleme
- Backend'de `backend/engine.py` dosyasında emit et
- Frontend'de `frontend/src/hooks/use-websocket.ts` dosyasında handle et

### Zamanlama Formülü
```
tetik = hedef_epoch + server_offset - rtt_tek_yon + buffer
```

Bu formül, isteğin sunucuya tam hedef saatte (ör: 14:00:00.000) ulaşmasını sağlar.

### Kritik Bilgi Alanları
- OBS sunucu saati yaklaşık 2 saniye NTP'nin gerisindedir. NTP kullanmak VAL02 hatasına neden olur.
- 3 saniye debounce süresi vardır — Sunucu aynı oturumdan <3s aralıkla gelen istekleri yok sayar (VAL16).
- OBS yanıt kodları: statusCode 0=başarılı, VAL02=dönem kapalı, VAL03=zaten kayıtlı, VAL06=kontenjan dolu, VAL09=çakışma, VAL16=debounce, VAL22=yükseltme çakışması.

## Geliştirme Kuralları

### Kodlama Stili
- Backend Python kodları için Türkçe değişken isimleri kullanılır (örneğin: `sunucu_offset_olc`, `kayit_yap`, `tetik`)
- Frontend TypeScript kodları için İngilizce değişken isimleri kullanılır
- Log mesajları Türkçe olmalıdır

### Güvenlik
- Token bilgileri asla diske veya buluta kaydedilmemelidir
- Sadece bellekte oturum boyunca tutulmalıdır
- Bulut yapılandırması token alanını hariç tutmalıdır

### Test Etme
Test paketi mevcut değildir. Gerçek kayıt yapmadan zamanlama testi için dry-run modu (`dry_run: true` ayarı) kullanılmalıdır.

## Ortam Değişkenleri

Frontend için `NEXT_PUBLIC_API_URL` (varsayılan: `http://localhost:8000`), Clerk anahtarları (`NEXT_PUBLIC_CLERK_*`) ve Supabase anahtarları `.env.local` dosyasında tanımlanmalıdır.

## Kullanım

1. Tarayıcıda `http://localhost:3000` adresini açın
2. OBS web arayüzünden JWT token'ı kopyalayıp yapıştırın
3. Eklemek istediğiniz CRN'leri **Eklenecek Dersler** bölümüne ekleyin
4. Bırakmak istediğiniz CRN'leri **Bırakılacak Dersler** bölümüne ekleyin
5. Kayıt saatini ayarlayın (varsayılan: 14:00:00)
6. **"Kayıt Başlat"** butonuna basın (kayıt saatinden 2-5 dakika önce)
7. Sistem otomatik kalibre olacak ve tam saatte isteği gönderecektir

## Lisans

Bu proje Apache License 2.0 altında lisanslanmıştır. Türev çalışmalarda değişikliklerin belirtilmesi zorunludur.