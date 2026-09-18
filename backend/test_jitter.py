# -*- coding: utf-8 -*-
"""RTT dağınıklık ölçütü tek bir aykırı örnekle kandırılamamalı.

CANLI OLAYDAN ÇIKTI (17 Eylül 14:00): üç konteynerin RTT örnekleminde 10
ölçümden biri 76-87ms geldi (diğerleri 38-45ms). Popülasyon standart sapması
farkların KARESİNİ aldığı için o tek örnek σ'yı 0.3ms'den 14-16ms'ye çıkardı.
Buffer 11ms yerine 30-33ms hesaplandı; buffer tek yön RTT'yi (20ms) aşınca
"en erken hedef+1ms'de gönder" alt sınırı devreden çıktı ve tetik 10-15ms
GECİKTİ. min hepsinde 38-40ms'ydi — ağ kusursuz çalışıyordu.

Ölçüt medyan tabanlı (MAD) olmalı: sıralamaya bakar, kare almaz, tek aykırı
örnek kılını kıpırdatmaz. Ama GERÇEK dağınıklığa da körleşmemeli.
"""

import engine


# 17 Eylül 14:00, sfm6b'nin gerçek örneklemi (ms)
GERCEK_AYKIRI = [39, 40, 41, 42, 43, 43, 44, 45, 50, 87]
# Aynı slottaki sağlıklı örneklem (7c2dx)
GERCEK_SAGLIKLI = [39, 39, 39, 39, 40, 40, 40, 40, 40, 40]


def _j(ms_listesi):
    return engine.robust_jitter([x / 1000 for x in ms_listesi]) * 1000


def test_single_outlier_does_not_inflate_jitter():
    """Asıl hata: 10 örnekten biri sapınca σ 14ms oluyordu."""
    assert _j(GERCEK_AYKIRI) < 5.0


def test_healthy_sample_has_near_zero_jitter():
    assert _j(GERCEK_SAGLIKLI) < 1.5


def test_genuinely_dispersed_sample_still_reports_high_jitter():
    """Ölçüt körleşmemeli — ağ GERÇEKTEN dağınıksa bunu görmeli.

    Bu test olmasa 'her zaman 0 döndür' de testi geçerdi.
    """
    assert _j([20, 40, 60, 80, 100, 20, 40, 60, 80, 100]) > 20.0


def test_outlier_free_buffer_restores_the_floor():
    """Uçtan uca: aykırı örnekli veriyle buffer tek yön RTT'nin ALTINDA kalmalı.

    Kalırsa alt sınır bağlar ve tetik hedef+1ms'de olur (dünkü +15ms değil).
    """
    m = engine.RegistrationEngine(token="t", ecrn_list=["12345"], kayit_saati="23:59:00")
    m._last_ntp_delay = 0.002
    cal = engine.CalibrationData(server_offset=0.0, rtt_one_way=0.0195)
    buffer = m._calculate_measurement_based_buffer(
        cal, engine.robust_jitter([x / 1000 for x in GERCEK_AYKIRI]))
    assert buffer < cal.rtt_one_way, f"buffer {buffer*1000:.1f}ms >= tek yön {cal.rtt_one_way*1000:.1f}ms"


def test_empty_sample_is_safe():
    assert engine.robust_jitter([]) >= 0.0
