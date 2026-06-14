"""
Engine'in GERÇEK production kalibrasyonunu çalıştırır (NTP + robust Date + OBS↔NTP skew).
Engine'in tetik için kullandığı TAM offset'i + OBS skew telafisini gösterir.

Çalıştırma (calibration/ içinden, backend venv ile):
    python engine_calibrate_check.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from engine import RegistrationEngine  # noqa: E402

VERBOSE = "-v" in sys.argv


def run_once(label: str):
    eng = RegistrationEngine(token="dummy.jwt.token", ecrn_list=["00000"])
    if VERBOSE:
        eng._log = lambda msg, level="info": print(f"  [{level}] {msg}")
    else:
        eng._log = lambda msg, level="info": None

    cal = eng.calibrate()
    skew = eng._obs_clock_offset  # OBS↔NTP skew telafisi (- = OBS geride, geç at)
    print(
        f"  {label}: server_offset(NTP)={cal.server_offset*1000:+6.0f}ms | "
        f"ntp_offset={cal.ntp_offset*1000:+6.0f}ms | "
        f"OBS↔NTP skew={skew*1000:+5.0f}ms ({'OBS GERİDE' if skew < 0 else 'OBS İLERİDE'}) | "
        f"rtt_1yön={cal.rtt_one_way*1000:.0f}ms"
    )
    return skew


print("=== Engine.calibrate() — robust kalibrasyon + OBS↔NTP skew (2 kez) ===\n")
s1 = run_once("#1")
s2 = run_once("#2")

print("\n=== YORUM ===")
print("  OBS↔NTP skew, engine'in tetiği telafi ettiği OBS saat kayması.")
print("  - skew ~0      → OBS NTP-senkron, telafi gereksiz")
print("  - skew negatif → OBS NTP'den GERİDE; engine bu kadar GEÇ atar (erken atış = VAL02 önlenir)")
print(f"  İki ölçüm tutarlıysa (|fark|={abs(s1-s2)*1000:.0f}ms) skew güvenilir; değilse Date gürültülü.")
