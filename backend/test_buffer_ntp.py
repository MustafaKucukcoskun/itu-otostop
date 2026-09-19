# -*- coding: utf-8 -*-
"""Belirsizlik, offseti aldığımız ölçümün belirsizliği olmalı.

CANLI OLAY (18 Eylül 14:00, 42vq5): başlangıç kalibrasyonunda NTP gecikmesi
16.2ms'ydi → σ_ntp=8.1ms → buffer 19.1ms. Tek yön RTT 20.0ms olduğu için
buffer sınırın yalnızca 0.9ms ALTINDA kaldı. σ_ntp 9ms olsaydı buffer RTT'yi
aşacak, `_apply_advanced_protection` alt sınırı devreden çıkacak ve tetik
10-15ms gecikecekti — yani 17 Eylül'deki hatanın aynısı, bu sefer NTP
kapısından.

Kök sebep: buffer motor başlarken BİR KEZ hesaplanıp donuyor. Kalibrasyon
havuzu sonradan çok daha iyi ölçümlerle doluyor, `_best_calibration()` da
offseti oradan seçiyor — ama belirsizlik ilk, kötü ölçümde kalıyor.
Offseti en iyi örnekten alıp belirsizliği başka bir örnekten almak tutarsız.

Çözüm: NTP gecikmesi örneğin kendisiyle saklanır ve buffer, offseti
aldığımız örneğin gecikmesinden hesaplanır.
"""

import engine


def _motor():
    return engine.RegistrationEngine(token="t", ecrn_list=["12345"],
                                     kayit_saati="23:59:00")


def test_sample_carries_its_own_ntp_delay():
    m = _motor()
    m._add_sample(0.001, 0.040, "test", ntp_delay=0.016)
    assert m._best_calibration().ntp_delay == 0.016


def test_best_sample_supplies_the_uncertainty_not_the_latest_call():
    """ASIL HATA: offset en iyi örnekten, belirsizlik son çağrıdan geliyordu."""
    m = _motor()
    m._add_sample(0.001, 0.038, "iyi", ntp_delay=0.002)     # en düşük RTT → seçilecek
    m._add_sample(0.001, 0.060, "kotu", ntp_delay=0.030)    # sonradan geldi, kötü
    m._last_ntp_delay = 0.030                               # son çağrı kötüydü
    assert m._best_calibration().ntp_delay == 0.002


def test_a_better_later_measurement_shrinks_the_buffer():
    """42vq5 senaryosu: kötü başlayan ölçüm sonradan düzelince buffer da düzelmeli."""
    m = _motor()
    m._add_sample(0.001, 0.040, "ilk", ntp_delay=0.0162)    # sigma_ntp 8.1ms
    kotu = m._calculate_measurement_based_buffer(m._best_calibration(), 0.0003)
    m._add_sample(0.001, 0.039, "sonraki", ntp_delay=0.002) # sigma_ntp 1.0ms
    iyi = m._calculate_measurement_based_buffer(m._best_calibration(), 0.0003)
    assert iyi < kotu, f"buffer iyilesmedi: {kotu*1000:.1f}ms -> {iyi*1000:.1f}ms"


def test_buffer_stays_below_the_one_way_rtt_in_the_live_case():
    """42vq5'in gerçek sayıları: buffer sınırı devre dışı bırakmamalı."""
    m = _motor()
    m._add_sample(0.005, 0.040, "ilk", ntp_delay=0.0162)
    m._add_sample(0.005, 0.039, "son kalibrasyon", ntp_delay=0.002)
    cal = m._best_calibration()
    buf = m._calculate_measurement_based_buffer(cal, 0.0002)
    assert buf < cal.rtt_one_way, f"buffer {buf*1000:.1f}ms >= tek yön {cal.rtt_one_way*1000:.1f}ms"


def test_missing_delay_falls_back_and_never_crashes():
    """Gecikme kaydedilmemişse eski davranışa düşülür, patlanmaz."""
    m = _motor()
    m._add_sample(0.001, 0.040, "eski yol")
    buf = m._calculate_measurement_based_buffer(m._best_calibration(), 0.0003)
    assert buf > 0


# ══════════════════════════════════════════════════════════════
# Buffer donmamalı: havuz iyileştikçe tazelenmeli
# ══════════════════════════════════════════════════════════════
#
# Örneğe gecikme yazmak tek başına yetmez — buffer motor başlarken bir kez
# hesaplanıp öylece kalıyordu. Tetik bekleme boyunca yeniden hesaplanıyor
# (periyodik kalibrasyon, son tam kalibrasyon) ama hep O DONMUŞ buffer'la.
# 42vq5'in kötü başlangıcı bu yüzden hedefe kadar taşındı.


def test_buffer_is_refreshed_from_the_current_best_sample():
    m = _motor()
    m._rtt_jitter = 0.0003
    m._add_sample(0.001, 0.040, "kotu baslangic", ntp_delay=0.0162)
    kotu = m._refresh_buffer()
    m._add_sample(0.001, 0.039, "sonraki kalibrasyon", ntp_delay=0.002)
    iyi = m._refresh_buffer()
    assert iyi < kotu
    assert m._measurement_buffer == iyi, "tazelenen degeri saklamadi"


def test_refresh_is_safe_with_an_empty_pool():
    m = _motor()
    assert m._refresh_buffer() > 0


def test_refresh_uses_the_stored_jitter_and_does_no_network_io(monkeypatch):
    """Tetik yolunda ağ ölçümü YAPILMAMALI — saklanan jitter kullanılır."""
    m = _motor()
    def patla(*a, **k):
        raise AssertionError("_refresh_buffer ag olcumu yapti")
    monkeypatch.setattr(m, "_rtt_stats", patla)
    m._rtt_jitter = 0.0005
    m._add_sample(0.001, 0.040, "x", ntp_delay=0.004)
    assert m._refresh_buffer() > 0
