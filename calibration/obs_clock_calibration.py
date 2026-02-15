"""
OBS Sunucu Saat Kalibrasyonu
─────────────────────────────
OBS sunucusunun Date header geçişlerini analiz ederek
sunucu saatini dünya saatine (NTP) göre kalibre eder.

Yöntem:
1. OBS'ye hızlı art arda istek at
2. Date header'ın saniye değişim anını yakala
3. Bu anı NTP saatiyle karşılaştır
4. Çok sayıda ölçümün ortalamasını al → hassas offset

Hedef: ±15ms hassasiyet
"""

import time
import statistics
import socket
import struct
import requests
import sys
from datetime import datetime

OBS_URL = "https://obs.itu.edu.tr"

# ── NTP ──────────────────────────────────────────────

def ntp_offset(server="time.google.com", timeout=2):
    """NTP sunucusundan offset (saniye) ve delay ölç."""
    NTP_EPOCH = 2208988800  # 1900 → 1970

    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(timeout)

    # NTP paketi oluştur
    data = b'\x1b' + 47 * b'\0'
    t1 = time.time()

    try:
        client.sendto(data, (server, 123))
        data, _ = client.recvfrom(1024)
    finally:
        client.close()

    t4 = time.time()

    # NTP yanıtından sunucu zamanlarını çıkar
    t2 = struct.unpack('!12I', data)[8] + struct.unpack('!12I', data)[9] / (2**32) - NTP_EPOCH
    t3 = struct.unpack('!12I', data)[10] + struct.unpack('!12I', data)[11] / (2**32) - NTP_EPOCH

    offset = ((t2 - t1) + (t3 - t4)) / 2
    delay = (t4 - t1) - (t3 - t2)

    return offset, delay


def get_ntp_time():
    """En iyi NTP ölçümünü al (3 deneme, en düşük delay)."""
    best_offset = None
    best_delay = float('inf')

    for server in ["time.google.com", "time.windows.com", "pool.ntp.org"]:
        try:
            for _ in range(3):
                offset, delay = ntp_offset(server)
                if delay < best_delay:
                    best_delay = delay
                    best_offset = offset
        except Exception:
            continue

    if best_offset is None:
        raise Exception("NTP sunucularına ulaşılamadı!")

    return best_offset, best_delay


# ── Date Header Geçiş Yakalama ──────────────────────

def detect_date_transition(session, ntp_off):
    """
    OBS'ye hızlı istekler atarak Date header'ın
    saniye değişim anını yakala.

    Döndürür: obs_offset_ms (OBS saati - NTP saati, ms cinsinden)
    """
    prev_date = None
    transition_time = None

    # Hızlı istekler at, Date geçişini bekle (max 3 saniye)
    start = time.time()
    request_count = 0

    while time.time() - start < 3.0:
        t_before = time.time()
        try:
            resp = session.head(OBS_URL, timeout=2)
        except Exception:
            continue
        t_after = time.time()

        request_count += 1
        date_str = resp.headers.get("Date", "")

        if not date_str:
            continue

        if prev_date and date_str != prev_date:
            # GEÇİŞ YAKALANDI!
            # İsteğin ortasında geçiş oldu
            rtt = t_after - t_before
            # Geçiş anı tahmini: istek gönderiminden RTT/2 sonra
            transition_local = t_before + rtt / 2

            # NTP düzeltmesi uygula
            transition_ntp = transition_local + ntp_off

            # Bu an tam saniye sınırı olmalı (.000)
            # OBS saatindeki saniye sınırı ile gerçek saniye sınırı farkı
            fractional = transition_ntp % 1.0  # 0.000 - 0.999 arası
            if fractional > 0.5:
                obs_offset_ms = (fractional - 1.0) * 1000  # Negatif = OBS geri
            else:
                obs_offset_ms = fractional * 1000  # Pozitif = OBS ileri

            return obs_offset_ms, rtt * 1000, request_count

        prev_date = date_str

    return None, None, request_count


# ── Ana Kalibrasyon ─────────────────────────────────

def main():
    print("=" * 60)
    print("   OBS Sunucu Saat Kalibrasyonu")
    print("   Hedef: ±15ms hassasiyet")
    print("=" * 60)
    print()

    # 1. NTP kalibrasyonu
    print("1️⃣  NTP kalibrasyonu yapılıyor...")
    try:
        ntp_off, ntp_delay = get_ntp_time()
        print(f"   NTP offset: {ntp_off*1000:+.1f}ms (delay: {ntp_delay*1000:.0f}ms)")
        print(f"   Hassasiyet: ±{ntp_delay*500:.0f}ms")
    except Exception as e:
        print(f"   ❌ NTP hatası: {e}")
        return

    # 2. OBS bağlantı testi
    print()
    print("2️⃣  OBS bağlantı testi...")
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })

    try:
        resp = session.head(OBS_URL, timeout=5)
        date_hdr = resp.headers.get("Date", "Yok")
        print(f"   HTTP {resp.status_code} | Date: {date_hdr}")
        if not resp.headers.get("Date"):
            print("   ❌ Date header bulunamadı! Kalibrasyon yapılamaz.")
            return
    except Exception as e:
        print(f"   ❌ Bağlantı hatası: {e}")
        return

    # 3. Date geçiş ölçümleri
    target_samples = 5000  # 5000 geçiş ölçümü → ±4ms hassasiyet hedefi
    print()
    print(f"3️⃣  {target_samples} Date header geçişi ölçülüyor...")
    print(f"   (Her biri ~1-2 saniye, toplam ~{target_samples * 1.5:.0f} saniye)")
    print()

    offsets = []
    rtts = []

    for i in range(target_samples):
        obs_off, rtt, req_count = detect_date_transition(session, ntp_off)

        if obs_off is not None:
            offsets.append(obs_off)
            rtts.append(rtt)
            if len(offsets) % 50 == 0 or len(offsets) <= 5:
                cur_mean = statistics.mean(offsets)
                cur_std = statistics.stdev(offsets) if len(offsets) > 1 else 0
                cur_se = 1.96 * cur_std / (len(offsets) ** 0.5) if len(offsets) > 1 else 999
                print(f"   [{len(offsets):3d} ölçüm] "
                      f"ortalama: {cur_mean:+7.1f}ms  "
                      f"hassasiyet: ±{cur_se:.0f}ms  "
                      f"(son: {obs_off:+.0f}ms, RTT: {rtt:.0f}ms)")
        else:
            if i % 100 == 0:
                print(f"   [{i+1:3d}/{target_samples}] ⚠️ Geçiş yakalanamadı")

        # Kısa bekleme (sonraki geçişi yakalamak için)
        time.sleep(0.1)

    session.close()

    # 4. İstatistiksel analiz
    if len(offsets) < 5:
        print(f"\n❌ Yetersiz ölçüm ({len(offsets)}). En az 5 gerekli.")
        return

    print()
    print("=" * 60)
    print("   📊 SONUÇLAR")
    print("=" * 60)

    mean_offset = statistics.mean(offsets)
    median_offset = statistics.median(offsets)
    stdev = statistics.stdev(offsets)
    stderr = stdev / (len(offsets) ** 0.5)
    confidence_95 = 1.96 * stderr

    mean_rtt = statistics.mean(rtts)

    # Outlier tespiti (±2σ dışındakileri filtrele)
    filtered = [o for o in offsets if abs(o - mean_offset) < 2 * stdev]
    if len(filtered) >= 5:
        clean_mean = statistics.mean(filtered)
        clean_stdev = statistics.stdev(filtered)
        clean_stderr = clean_stdev / (len(filtered) ** 0.5)
        clean_95 = 1.96 * clean_stderr
    else:
        clean_mean = mean_offset
        clean_95 = confidence_95

    direction = "İLERİDE" if clean_mean > 0 else "GERİDE"

    print(f"""
   Toplam ölçüm:         {len(offsets)}
   Outlier sonrası:       {len(filtered)}
   
   Ham ortalama:          {mean_offset:+.1f}ms
   Ham medyan:            {median_offset:+.1f}ms
   Standart sapma:        {stdev:.1f}ms
   
   ─── TEMİZ SONUÇ ───
   OBS saat offseti:      {clean_mean:+.1f}ms {direction}
   %95 güven aralığı:     ±{clean_95:.1f}ms
   Hassasiyet:            ±{clean_95:.0f}ms
   
   ─── YARDIMCI ───
   Ortalama RTT:          {mean_rtt:.0f}ms
   NTP offset:            {ntp_off*1000:+.1f}ms
   
   ─── KARAR ───""")

    if clean_95 <= 15:
        print(f"   ✅ HEDEF TUTTURULDU! Hassasiyet ±{clean_95:.0f}ms ≤ ±15ms")
        print(f"   → Hardcoded değer: OBS_CLOCK_OFFSET = {clean_mean:+.1f}  # ms")
    elif clean_95 <= 30:
        print(f"   ⚠️ İYİ ama hedefin üstünde: ±{clean_95:.0f}ms")
        print(f"   → Daha fazla ölçüm yaparak iyileştirilebilir")
        print(f"   → Hardcoded değer (dikkatli kullan): OBS_CLOCK_OFFSET = {clean_mean:+.1f}  # ms")
    else:
        print(f"   ❌ Hassasiyet yetersiz: ±{clean_95:.0f}ms")
        print(f"   → OBS sunucusu stabil değil veya ağ çok değişken")

    print()
    print(f"   Kullanım: engine.py tetik formülüne {clean_mean:+.1f}ms ekle")
    print(f"   → İstek OBS açılışından {abs(clean_mean) + clean_95:.0f}ms sonra ulaşır (en kötü)")
    print(f"   → İstek OBS açılışından {max(0, abs(clean_mean) - clean_95):.0f}ms sonra ulaşır (en iyi)")


if __name__ == "__main__":
    main()
