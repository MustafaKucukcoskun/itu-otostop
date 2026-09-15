"""Girdi doğrulaması — kullanıcının yanlış yazabileceği her şey.

Kayıt saati düzenli ifadeyle `\d{2}:\d{2}:\d{2}` olarak kontrol ediliyordu;
bu "25:00:00" ve "12:70:00" gibi değerleri KABUL eder. Motor bunları
`datetime.replace(hour=25)` ile patlatır, hata dış except'e düşer ve kullanıcı
"Kayıt başlatıldı" mesajı aldıktan sonra sessizce hiçbir şey olmaz.
Kayıt gününde yanlış yazılan bir saat = sessiz ders kaybı.
"""

import pytest
from pydantic import ValidationError

from models import ConfigRequest


def _kur(saat):
    return ConfigRequest(ecrn_list=["12345"], kayit_saati=saat)


# ── Geçerli değerler ──


@pytest.mark.parametrize("saat", ["00:00:00", "14:00:00", "23:59:59", "09:05:03"])
def test_valid_times_accepted(saat):
    assert _kur(saat).kayit_saati == saat


def test_empty_time_allowed():
    """Boş = henüz ayarlanmadı; başlatma ayrıca kontrol ediyor."""
    assert _kur("").kayit_saati == ""


# ── Geçersiz değerler ──


@pytest.mark.parametrize("saat", ["25:00:00", "24:00:00", "12:60:00", "12:70:00",
                                  "12:00:60", "12:00:99", "99:99:99"])
def test_out_of_range_times_rejected(saat):
    """Aralık dışı değerler modelde durmalı, motorda değil."""
    with pytest.raises(ValidationError):
        _kur(saat)


@pytest.mark.parametrize("saat", ["14:00", "2:00:00", "14:00:00:00", "abc",
                                  "14-00-00", " 14:00:00"])
def test_malformed_times_rejected(saat):
    with pytest.raises(ValidationError):
        _kur(saat)


def test_rejected_times_never_reach_the_engine():
    """Modelden geçen HER değer motorda epoch'a çevrilebilmeli."""
    from engine import RegistrationEngine
    for s in ("00:00:00", "23:59:59", "14:00:00"):
        RegistrationEngine._saat_to_epoch(_kur(s).kayit_saati)  # patlamamalı
