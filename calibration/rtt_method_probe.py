# -*- coding: utf-8 -*-
"""HEAD, POST'un yerini tutar mı? — Frankfurt'tan ölçüm.

NEDEN
─────
`engine._rtt_olc()` ve `_rtt_stats()` ağ gecikmesini ölçmek için GERÇEK kayıt
ucuna (`/api/ders-kayit/v21`) `ECRN:["00000"]` ile POST atıyor. Kayıt başına
~37 sahte kayıt isteği ediyor; 40 kullanıcıda ~1500.

İki ayrı sorun:
  1. Nezaket/risk: üniversitenin kayıt ucuna bu hacimde sahte istek, aracın
     engellenmesine yol açabilir.
  2. Kavramsal: POST'un gidiş-dönüşü OBS'in UYGULAMA işleme süresini de
     içerir; oysa formüldeki `rtt_one_way` saf AĞ transit süresi olmalı.

Üretim loglarından (15-19 Eylül, n=16) POST min 38ms, HEAD min 37ms çıktı —
yani fark ~1ms. Ama n=16 ince ve HEAD ölçümü koşu başına tek örnek. Bu araç
ikisini AYNI koşulda, dönüşümlü ve geniş örneklemle kıyaslar.

YÖNTEM
──────
Dönüşümlü ölçüm (HEAD, POST, HEAD, POST...) — zamanla değişen ağ koşulları
ikisini de aynı şekilde etkilesin diye. Karşılaştırmada MİNİMUM esas alınır:
en düşük RTT, işleme süresi ~0 olan örnektir ve saf transite en yakın olanıdır.
Medyan ve p90 da raporlanır.

POST'a geçerli token KONULMAZ: 401 dönecek. Bu kasıtlı — amaç ağ yolunu
ölçmek, gerçek kayıt denemesi yapmak değil. Gerçek token'lı POST'un üretimdeki
min değeri loglardan biliniyor (38ms) ve buradaki 401-POST ile kıyaslanabilir.
"""

import os
import statistics
import time

import requests

OBS_URL = os.getenv("OBS_URL", "https://obs.itu.edu.tr/api/ders-kayit/v21")
OBS_BASE = os.getenv("OBS_BASE", "https://obs.itu.edu.tr")
TUR = int(os.getenv("TUR", "120"))
BEKLE = float(os.getenv("BEKLE", "0.15"))


def olc(fn):
    t0 = time.perf_counter()
    try:
        r = fn()
    except Exception:
        return None, None
    return (time.perf_counter() - t0) * 1000, r.status_code


def ozet(ad, v, kodlar):
    if not v:
        print(f"  {ad:<26} olculemedi")
        return None
    v = sorted(v)
    n = len(v)
    print(f"  {ad:<26} n={n:>3}  min={v[0]:6.1f}  p25={v[n//4]:6.1f}  "
          f"medyan={statistics.median(v):6.1f}  p90={v[int(n*0.9)]:6.1f}  "
          f"max={v[-1]:6.1f}  HTTP {sorted(kodlar)}")
    return v[0]


def main():
    s = requests.Session()
    s.headers.update({
        "Accept": "*/*",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "itu-otostop-rtt-probe/1.0",
    })

    # Bağlantıyı ısıt: TLS el sıkışması ilk ölçümleri şişirir.
    for _ in range(5):
        try:
            s.head(OBS_BASE, timeout=5, allow_redirects=False)
        except Exception:
            pass

    yollar = {
        "HEAD  kayit ucu": (lambda: s.head(OBS_URL, timeout=10), [], set()),
        "POST  kayit ucu": (lambda: s.post(OBS_URL, json={"ECRN": ["00000"], "SCRN": []},
                                           timeout=10), [], set()),
        "HEAD  ana sayfa": (lambda: s.head(OBS_BASE, timeout=10, allow_redirects=False), [], set()),
    }

    print(f"Donusumlu olcum: {TUR} tur x {len(yollar)} yol\n")
    for i in range(TUR):
        for ad, (fn, sure, kodlar) in yollar.items():
            ms, kod = olc(fn)
            if ms is not None:
                sure.append(ms)
                kodlar.add(kod)
            time.sleep(BEKLE / len(yollar))
        if (i + 1) % 40 == 0:
            print(f"  ... {i+1}/{TUR} tur")

    print("\n" + "=" * 78)
    minler = {}
    for ad, (_, sure, kodlar) in yollar.items():
        minler[ad] = ozet(ad, sure, kodlar)
    print("=" * 78)

    h = minler.get("HEAD  kayit ucu")
    p = minler.get("POST  kayit ucu")
    if h and p:
        print(f"\n  POST min - HEAD min = {p - h:+.1f} ms")
        print(f"  -> tek yon tahminine etkisi: {(p - h) / 2:+.1f} ms")
        print(f"  Uretimde (gercek token'li POST) min = 38.0 ms")
        print(f"  Buradaki 401-POST min             = {p:.1f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
