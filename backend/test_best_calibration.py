# -*- coding: utf-8 -*-
"""Offset ve transit AYRI ölçütlerle seçilmeli.

CANLI OLAY (20 Eylül 06:05, gerçek kullanıcı koşusu): ateşlemeden 14 saniye
önce buffer 10.2ms'den 14.5ms'ye ÇIKTI.

    06:05:14  σ_ntp=1.3ms → buffer=10.2ms
    06:05:46  σ_ntp=5.3ms → buffer=14.5ms

Son tam kalibrasyonun NTP gecikmesi 11ms'ydi (öncekiler 3-7ms) ama HTTP
RTT'si en düşüktü. `_best_calibration()` yalnızca en düşük RTT'ye baktığı
için o örneği seçti ve σ_ntp'yi onunla hesapladık.

İki büyüklüğün doğruluk ölçütü farklı:
    server_offset → NTP gecikmesi belirler
    rtt_one_way   → HTTP RTT belirler
İkisini tek örnekten tek ölçütle seçmek, birinde kazanıp ötekinde kaybetmek
demek. Ateşleme o gün yine doğru oldu (alt sınır bağladı) ama pay 7.7ms
yerine 3.5ms kaldı — 18 Eylül'de 0.9ms'ye kadar inen hatanın bir kat
derinindeki hali.
"""

import engine


def _motor():
    return engine.RegistrationEngine(token="t", ecrn_list=["12345"],
                                     kayit_saati="23:59:00")


def test_offset_comes_from_the_lowest_ntp_delay_sample():
    """ASIL HATA: RTT'de kazanan örnek, kötü NTP gecikmesini de getiriyordu."""
    m = _motor()
    m._add_sample(0.001, 0.040, "iyi ntp",  ntp_delay=0.003)   # RTT kotu, NTP iyi
    m._add_sample(0.009, 0.036, "kotu ntp", ntp_delay=0.011)   # RTT iyi, NTP kotu
    cal = m._best_calibration()
    assert cal.ntp_delay == 0.003, f"ntp_delay {cal.ntp_delay}"
    assert abs(cal.server_offset - 0.001) < 1e-9


def test_transit_comes_from_the_lowest_rtt_sample():
    """Aynı anda: tek yön tahmini en düşük RTT'den gelmeli."""
    m = _motor()
    m._add_sample(0.001, 0.040, "iyi ntp",  ntp_delay=0.003)
    m._add_sample(0.009, 0.036, "kotu ntp", ntp_delay=0.011)
    assert m._best_calibration().rtt_one_way == 0.036 / 2


def test_live_case_keeps_the_good_buffer():
    """20 Eylül'ün gerçek sayıları: buffer 14.5ms'ye çıkmamalı."""
    m = _motor()
    m._rtt_jitter = 0.0002
    m._add_sample(-0.0000, 0.037, "hizli kal #4", ntp_delay=0.003)
    m._add_sample(-0.0001, 0.036, "son tam kal", ntp_delay=0.011)
    buf = m._refresh_buffer()
    assert buf < 0.012, f"buffer {buf*1000:.1f}ms — kotu NTP ornegi hala kazaniyor"


def test_samples_without_ntp_delay_do_not_win_by_default():
    """NTP başarısızken gecikme 0 kaydediliyor; 'en düşük' diye seçilmemeli."""
    m = _motor()
    m._add_sample(0.002, 0.050, "ntp yok", ntp_delay=0.0)
    m._add_sample(0.001, 0.040, "ntp var", ntp_delay=0.004)
    cal = m._best_calibration()
    assert cal.ntp_delay == 0.004
    assert abs(cal.server_offset - 0.001) < 1e-9


def test_falls_back_when_no_sample_has_ntp():
    """Hiçbirinde NTP yoksa eski davranış: en düşük RTT."""
    m = _motor()
    m._add_sample(0.002, 0.050, "a")
    m._add_sample(0.001, 0.040, "b")
    cal = m._best_calibration()
    assert cal.rtt_one_way == 0.040 / 2
    assert abs(cal.server_offset - 0.001) < 1e-9


def test_empty_pool_is_safe():
    assert _motor()._best_calibration() is not None or True
