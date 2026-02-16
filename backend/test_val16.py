"""
VAL16 Debounce Test Script
===========================
Bu script 3 kritik soruyu cevaplar:

1. VAL16 IP bazlı mı yoksa token/session bazlı mı?
2. Dummy CRN (00000) ile atılan istek debounce tetikler mi?
3. HEAD isteği debounce tetikler mi?

Kullanım:
  python test_val16.py --token1 "Bearer xxx" --token2 "Bearer yyy"
  
Token2 opsiyoneldir — sadece IP vs token bazlı testi için gerekli.
"""

import requests
import time
import argparse
import json

OBS_URL = "https://obs.itu.edu.tr/api/ders-kayit/v21"

def create_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://obs.itu.edu.tr",
        "Referer": "https://obs.itu.edu.tr/",
    })
    return s

def send_request(session: requests.Session, ecrn: list[str], label: str) -> dict:
    """İstek at ve response'u tamamen logla."""
    t0 = time.perf_counter()
    try:
        resp = session.post(OBS_URL, json={"ECRN": ecrn, "SCRN": []}, timeout=10)
        elapsed = (time.perf_counter() - t0) * 1000
        
        body = None
        try:
            body = resp.json()
        except:
            body = resp.text[:500]
        
        result = {
            "label": label,
            "status_code": resp.status_code,
            "elapsed_ms": round(elapsed),
            "body": body,
        }
        
        # VAL16 kontrol
        has_val16 = False
        has_val02 = False
        if isinstance(body, dict):
            for item in (body.get("ecrnResultList") or []):
                rc = item.get("resultCode", "")
                if rc == "VAL16":
                    has_val16 = True
                if rc == "VAL02":
                    has_val02 = True
        
        result["has_val16"] = has_val16
        result["has_val02"] = has_val02
        
        return result
    except Exception as e:
        return {"label": label, "error": str(e)}

def send_head(session: requests.Session, label: str) -> dict:
    """HEAD isteği at ve response'u logla."""
    t0 = time.perf_counter()
    try:
        resp = session.head(OBS_URL, timeout=10)
        elapsed = (time.perf_counter() - t0) * 1000
        return {
            "label": label,
            "method": "HEAD",
            "status_code": resp.status_code,
            "elapsed_ms": round(elapsed),
        }
    except Exception as e:
        return {"label": label, "method": "HEAD", "error": str(e)}

def print_result(result: dict):
    print(f"\n{'='*60}")
    print(f"  {result['label']}")
    print(f"{'='*60}")
    if "error" in result:
        print(f"  ❌ HATA: {result['error']}")
        return
    print(f"  HTTP {result['status_code']} | {result.get('elapsed_ms', '?')}ms | Method: {result.get('method', 'POST')}")
    if "has_val16" in result:
        print(f"  VAL16: {'⚠️ EVET' if result['has_val16'] else '✅ Yok'}")
        print(f"  VAL02: {'⏳ Evet' if result['has_val02'] else '✅ Yok'}")
    if "body" in result:
        print(f"  Body: {json.dumps(result['body'], ensure_ascii=False, indent=2)[:500]}")

def main():
    parser = argparse.ArgumentParser(description="VAL16 Debounce Test")
    parser.add_argument("--token1", required=True, help="Birinci Bearer token")
    parser.add_argument("--token2", default=None, help="İkinci Bearer token (IP vs token testi için)")
    args = parser.parse_args()
    
    s1 = create_session(args.token1)
    
    # ══════════════════════════════════════════════════════════
    # TEST 1: Dummy CRN debounce tetikler mi?
    # ══════════════════════════════════════════════════════════
    print("\n" + "█"*60)
    print("  TEST 1: Dummy CRN (00000) debounce tetikler mi?")
    print("█"*60)
    print("  İlk istek: dummy CRN 00000")
    print("  İkinci istek: 1sn sonra dummy CRN 00000")
    
    r1 = send_request(s1, ["00000"], "T1-A: İlk dummy istek")
    print_result(r1)
    
    time.sleep(1)  # 1sn bekle (< 3sn debounce)
    
    r2 = send_request(s1, ["00000"], "T1-B: 1sn sonra ikinci dummy istek")
    print_result(r2)
    
    if r2.get("has_val16"):
        print("\n⚠️ SONUÇ: Dummy CRN (00000) debounce TETİKLİYOR!")
        print("   → Keepalive ve probe POST'ları gerçek isteği debounce'a sokabilir!")
    else:
        print("\n✅ SONUÇ: Dummy CRN debounce tetiklemiyor")
    
    # 5sn bekle (debounce süresi dolsun)
    print("\n⏳ 5sn bekleniyor (debounce reset)...")
    time.sleep(5)
    
    # ══════════════════════════════════════════════════════════
    # TEST 2: HEAD isteği debounce tetikler mi?
    # ══════════════════════════════════════════════════════════
    print("\n" + "█"*60)
    print("  TEST 2: HEAD isteği debounce tetikler mi?")
    print("█"*60)
    
    r3 = send_head(s1, "T2-A: HEAD isteği")
    print_result(r3)
    
    time.sleep(0.5)  # 0.5sn sonra POST at
    
    r4 = send_request(s1, ["00000"], "T2-B: HEAD'den 0.5sn sonra POST")
    print_result(r4)
    
    if r4.get("has_val16"):
        print("\n⚠️ SONUÇ: HEAD isteği debounce TETİKLİYOR!")
    else:
        print("\n✅ SONUÇ: HEAD isteği debounce tetiklemiyor")
    
    # 5sn bekle
    print("\n⏳ 5sn bekleniyor (debounce reset)...")
    time.sleep(5)
    
    # ══════════════════════════════════════════════════════════
    # TEST 3: IP bazlı mı yoksa token bazlı mı?
    # ══════════════════════════════════════════════════════════
    if args.token2:
        print("\n" + "█"*60)
        print("  TEST 3: VAL16 IP bazlı mı yoksa token bazlı mı?")
        print("█"*60)
        print("  Token1 ile istek at → hemen Token2 ile istek at")
        
        s2 = create_session(args.token2)
        
        r5 = send_request(s1, ["00000"], "T3-A: Token1 ile istek")
        print_result(r5)
        
        time.sleep(0.5)  # 0.5sn sonra farklı tokenla
        
        r6 = send_request(s2, ["00000"], "T3-B: Token2 ile 0.5sn sonra istek")
        print_result(r6)
        
        if r6.get("has_val16"):
            print("\n🚨 SONUÇ: VAL16 IP BAZLI! Aynı IP'den farklı tokenlar da debounce yiyor!")
            print("   → Multi-user ÇALIŞMAZ! Her kullanıcı ayrı IP'ye ihtiyaç duyar!")
        else:
            print("\n✅ SONUÇ: VAL16 TOKEN BAZLI. Farklı tokenlar birbirini etkilemiyor.")
            print("   → Multi-user güvenle çalışır ✅")
    else:
        print("\n⚠️ TEST 3 atlandı: IP vs token testi için --token2 gerekli")
    
    # ══════════════════════════════════════════════════════════
    # TEST 4: Tam engine senaryosu simülasyonu
    # ══════════════════════════════════════════════════════════
    print("\n⏳ 5sn bekleniyor (debounce reset)...")
    time.sleep(5)
    
    print("\n" + "█"*60)
    print("  TEST 4: Engine senaryosu (keepalive + probe + kayıt)")
    print("█"*60)
    print("  Sıra: POST(5.5s) → POST(3.5s) → 3xPOST(2.5s) → KAYIT(0s)")
    print("  (Zamanlar kısaltılmış)")
    
    # 5.5sn kala keepalive
    r7 = send_request(s1, ["00000"], "T4-A: Keepalive POST (5.5sn kala)")
    print_result(r7)
    time.sleep(2)  # 2sn bekle (normalde 2sn)
    
    # 3.5sn kala keepalive
    r8 = send_request(s1, ["00000"], "T4-B: Keepalive POST (3.5sn kala)")
    print_result(r8)
    time.sleep(1)  # 1sn bekle (normalde 1sn)
    
    # 2.5sn kala probe (3x)
    for i in range(3):
        r9 = send_request(s1, ["00000"], f"T4-C{i+1}: Probe POST (2.5sn kala, #{i+1})")
        print_result(r9)
    
    time.sleep(2.5)  # Son probe'dan 2.5sn sonra (gerçek kayıt anı)
    
    # GERÇEK kayıt isteği
    r10 = send_request(s1, ["00000"], "T4-D: GERÇEK KAYIT İSTEĞİ (0sn)")
    print_result(r10)
    
    if r10.get("has_val16"):
        print("\n🚨 SONUÇ: Engine senaryosunda GERÇEK İSTEK VAL16 YEDİ!")
        print("   → Keepalive/probe POST'ları gerçek kaydı sabote ediyor!")
        print("   → ACİL: Keepalive'ı HEAD'e çevir, probe aralığını >3sn yap!")
    else:
        print("\n✅ SONUÇ: Engine senaryosunda gerçek istek VAL16 yemedi")
    
    print("\n" + "="*60)
    print("  TESTLER TAMAMLANDI")
    print("="*60)

if __name__ == "__main__":
    main()
