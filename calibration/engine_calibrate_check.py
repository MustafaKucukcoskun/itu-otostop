"""
Engine'in GERÇEK production kalibrasyonunu çalıştırır (NTP + Date header + cross-validation).
quick_calibrate sadece kesirli offset ölçüyordu; bu, engine'in kullandığı TAM offset'i verir.

Çalıştırma (calibration/ içinden, backend venv ile):
    python engine_calibrate_check.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from engine import RegistrationEngine  # noqa: E402

eng = RegistrationEngine(token="dummy.jwt.token", ecrn_list=["00000"])

# _log'u stdout'a yönlendir (normalde event queue'ya gider)
eng._log = lambda msg, level="info": print(f"  [{level}] {msg}")

print("=== Engine.calibrate() — gerçek production kalibrasyonu ===\n")
cal = eng.calibrate()

print("\n=== SONUÇ ===")
print(f"  server_offset (yerel - OBS): {cal.server_offset * 1000:+.0f} ms")
print(f"  ntp_offset    (NTP - yerel): {cal.ntp_offset * 1000:+.0f} ms")
print(f"  rtt_one_way:                 {cal.rtt_one_way * 1000:.0f} ms")

date_off = eng._measure_date_offset()
if date_off is not None:
    print(f"  date_offset (TAM, yerel+rtt/2 - OBS): {date_off * 1000:+.0f} ms")
    print(f"\n  YORUM: |date_offset| ~0 → OBS NTP-senkron")
    print(f"         date_offset ~+2000ms → OBS ~2sn GERİDE (CLAUDE.md notu hâlâ geçerli)")
else:
    print("  date_offset: ölçülemedi")
