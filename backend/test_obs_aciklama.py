# -*- coding: utf-8 -*-
"""Bilinmeyen bir OBS hata kodunda, OBS'in kendi açıklaması ATILMAMALI.

CANLI OLAY (17 Eylül 14:00): bir kullanıcının 10 dersinin HEPSİ `VAL21`
aldı ve 0/10 ile bitti. O kod `HATA_KODLARI`'nda yok, dolayısıyla kullanıcı
ekranda sadece "VAL21" yazısını gördü — neden hiç ders alamadığını
öğrenemedi. Aynı istekte OBS `resultData` alanını gönderiyor ve biz onu
okumadan atıyorduk.

Alanın şeklini BİLMİYORUZ (VAL22'de dict geliyor, ötekilerde ne geldiği
meçhul), o yüzden hiçbir şekil varsayılmıyor: ne bulursak okunabilir hale
getirip gösteriyoruz. Amaç, bir sonraki kayıtta kodun ne olduğunu
tahminle değil OBS'in cümlesiyle öğrenmek.
"""

import engine


def test_dict_with_a_message_field_is_read():
    assert engine.obs_aciklama(
        {"message": "Aktif bir ders seçim zamanı içinde değilsiniz"}
    ) == "Aktif bir ders seçim zamanı içinde değilsiniz"


def test_turkish_key_names_are_read_too():
    assert engine.obs_aciklama({"aciklama": "Danışman onayı yok"}) == "Danışman onayı yok"


def test_unknown_shape_is_still_shown_not_swallowed():
    """Şekli tanımadığımızda bile içeriği görmeliyiz — öğrenmenin tek yolu bu."""
    cikti = engine.obs_aciklama({"kayitSaati": "10:00", "kod": 21})
    assert "kayitSaati" in cikti and "10:00" in cikti


def test_plain_string_passes_through():
    assert engine.obs_aciklama("ders kaydı kapalı") == "ders kaydı kapalı"


def test_missing_data_yields_empty_string_not_crash():
    assert engine.obs_aciklama(None) == ""
    assert engine.obs_aciklama({}) == ""


def test_output_is_bounded():
    """Tetik yolunda olmasa da log satırı sınırsız büyümemeli."""
    assert len(engine.obs_aciklama({"m": "x" * 5000})) <= 200


def test_turkish_characters_survive():
    """ensure_ascii kaçışı olursa kullanıcı 'de\u011fil' görür."""
    assert "değilsiniz" in engine.obs_aciklama({"bilinmeyen": "değilsiniz"})
