# -*- coding: utf-8 -*-
"""Şema tabanını yükseltmek var olan istemcileri KIRMAMALI.

CANLI OLAY (20 Eylül 05:44): kullanıcı "Ayarlar sunucuya kaydedilemiyor —
bağlantını kontrol et" hatası aldı ve hiçbir ayarı kaydedilemedi. Bağlantısı
sağlamdı; sorun bendeydi.

Debounce düzeltmesinde `retry_aralik` şema tabanını 3.0 → 3.5 çektim. Ama
frontend'in varsayılanı 3.0 ve kullanıcıların kayıtlı config'lerinde de 3.0
var. Backend her kaydı 422 ile reddetti.

Daha önce GEÇERLİ olan bir değeri sonradan geçersiz kılmak, istemciyi kırar.
Doğrusu: kabul et, güvenli tabana YÜKSELT. Girdide hoşgörülü, davranışta katı.
"""

import pytest
import models


def test_old_client_default_is_still_accepted():
    """ASIL HATA: frontend 3.0 gönderiyor, backend 422 dönüyordu."""
    c = models.ConfigRequest(token="t", ecrn_list=["12345"],
                             kayit_saati="14:08:00", retry_aralik=3.0)
    assert c.retry_aralik >= 3.5, "guvenli tabana yukseltilmedi"


def test_value_is_raised_to_the_safe_floor_not_rejected():
    for gelen in (3.0, 3.1, 3.49):
        c = models.ConfigRequest(token="t", ecrn_list=["12345"],
                                 kayit_saati="14:08:00", retry_aralik=gelen)
        assert c.retry_aralik == 3.5, f"{gelen} -> {c.retry_aralik}"


def test_larger_values_pass_through_untouched():
    c = models.ConfigRequest(token="t", ecrn_list=["12345"],
                             kayit_saati="14:08:00", retry_aralik=6.0)
    assert c.retry_aralik == 6.0


def test_absurd_values_are_still_refused():
    """Hoşgörü sınırsız değil: debounce'un çok altı anlamsız."""
    with pytest.raises(Exception):
        models.ConfigRequest(token="t", ecrn_list=["12345"],
                             kayit_saati="14:08:00", retry_aralik=0.1)
    with pytest.raises(Exception):
        models.ConfigRequest(token="t", ecrn_list=["12345"],
                             kayit_saati="14:08:00", retry_aralik=99.0)


def test_default_is_the_safe_value():
    c = models.ConfigRequest(token="t", ecrn_list=["12345"], kayit_saati="14:08:00")
    assert c.retry_aralik == 3.5
