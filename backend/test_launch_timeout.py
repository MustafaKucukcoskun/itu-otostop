# -*- coding: utf-8 -*-
"""Konteynerin zaman sınırı, gerçekte ne kadar bekleyeceğini kapsamalı.

İKİ AYRI YERDE SABİT 1800:
  main.py       : _launcher.launch(sid, ticket, 1800)
  job_launcher  : def launch(..., task_timeout: int = 1800)
ve bu sayı açılış isteğinin gövdesinde `"timeout": "1800s"` olarak gidip
Job'ın kendi ayarını EZİYOR. 18 Eylül'de `gcloud run jobs update
--task-timeout=2700s` yaptım ve hiçbir işe yaramadı.

Sonuç ölçüldü: 15-17 Eylül'de üç konteyner 1799, 1803, 1811 saniye çalıştı —
ikisi sınırı aştı ve "Terminating task because it has reached the maximum
timeout of 1800 seconds" logladı. 447p4 hedefte ateşledi, OBS 3296ms sonra
cevap verdi ve konteyner öldürülmesine 0.3 saniye kala sonucu aldı.

Sabit bir sayı doğru olamaz: konteyner hedefe kadar BEKLİYOR ve kullanıcı ne
kadar erken başlattıysa bekleme o kadar uzun. Sınır, kalan bekleme SÜRESİ
artı hedef sonrası tekrar bütçesi olmalı.
"""

import job_launcher


def _cfg():
    return job_launcher.JobLauncherConfig(
        project="p", region="r", job_name="j", control_url="https://c")


def _timeout_of(body):
    return int(body["overrides"]["timeout"].rstrip("s"))


def test_timeout_covers_a_long_wait():
    """Bir saat önce başlatan kullanıcı: 1800sn sınır hedefe varmadan biter."""
    _, body = job_launcher.build_run_request(_cfg(), "s", "t", 3600 + 900)
    assert _timeout_of(body) > 3600


def test_timeout_is_not_a_fixed_number():
    """Aynı çağrı farklı beklemelerde farklı sınır üretmeli."""
    _, kisa = job_launcher.build_run_request(_cfg(), "s", "t", 180 + 900)
    _, uzun = job_launcher.build_run_request(_cfg(), "s", "t", 3600 + 900)
    assert _timeout_of(kisa) != _timeout_of(uzun)


def test_runway_covers_the_full_retry_budget():
    """Hedeften SONRA 60 deneme x 3.5sn + yavaş OBS + kapanış yapılıyor."""
    assert job_launcher.CONTAINER_RUNWAY >= 60 * 3.5


def test_computed_timeout_adds_runway_to_the_wait():
    """Kalan bekleme + koşu payı."""
    assert job_launcher.hesapla_timeout(kalan_sn=3600) == 3600 + job_launcher.CONTAINER_RUNWAY


def test_a_late_start_still_gets_the_full_runway():
    """Hedef geçmiş olsa bile tekrar bütçesi kısılmamalı."""
    assert job_launcher.hesapla_timeout(kalan_sn=-120) == job_launcher.CONTAINER_RUNWAY


def test_timeout_is_a_whole_number_of_seconds():
    _, body = job_launcher.build_run_request(_cfg(), "s", "t",
                                             job_launcher.hesapla_timeout(1234.7))
    assert body["overrides"]["timeout"].endswith("s")
    assert float(_timeout_of(body)) == _timeout_of(body)
