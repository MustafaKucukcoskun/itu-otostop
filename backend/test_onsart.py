# -*- coding: utf-8 -*-
"""VAL11'in ham JSON'u öğrenciye bir şey anlatmıyor.

18 Eylül 14:00 (42vq5), Fix B sayesinde OBS'in kendi açıklaması göründü:

    VAL11 — {"uyulmayanOnsartlar": "\\"  ({'DersKodu':'MAT 104', 'Min': 'DD'}
             | {'DersKodu':'MAT 104E', 'Min': 'DD'})\\""}

Alan adı `uyulmayanOnsartlar` — yani VAL11 = ÖNKOŞUL SAĞLANMADI. Bu artık
tahmin değil, OBS'in kendi sözü. Ama öğrenci ekranda bu JSON'u görüyor.

Dönüşüm YORUM değil, birebir çeviri: her `{...}` birimi "DERS (en az NOT)"
olur, `|` → "veya", `&` → "ve", parantezler korunur. Yapıyı kendimiz
yorumlasaydık (örn. hepsini "veya" sayıp düzleştirseydik) yanlış bilgi
vermiş olurduk — eksik bilgi yanlış bilgiden iyidir.
"""

import engine

GERCEK_1 = "\"  ({'DersKodu':'MAT 104', 'Min': 'DD'} | {'DersKodu':'MAT 104E', 'Min': 'DD'})\""
GERCEK_2 = ("\"  (({'DersKodu':'MAT 103', 'Min': 'DD'} | {'DersKodu':'MAT 103E', 'Min': 'DD'})"
            " | ({'DersKodu':'MAT 101', 'Min': 'DD'} | {'DersKodu':'MAT 101E', 'Min': 'DD'}))\"")


def test_simple_or_becomes_readable_turkish():
    assert engine.onsart_metni(GERCEK_1) == "MAT 104 (en az DD) veya MAT 104E (en az DD)"


def test_nested_structure_is_preserved_not_flattened():
    """İç gruplar korunmalı — düzleştirmek mantığı bozar."""
    c = engine.onsart_metni(GERCEK_2)
    assert c == ("(MAT 103 (en az DD) veya MAT 103E (en az DD))"
                 " veya (MAT 101 (en az DD) veya MAT 101E (en az DD))")


def test_json_braces_and_keys_disappear():
    for parca in ("DersKodu", "Min", "{", "}", "|"):
        assert parca not in engine.onsart_metni(GERCEK_1)


def test_and_operator_is_translated_too():
    assert engine.onsart_metni("{'DersKodu':'FIZ 101', 'Min': 'CC'} & {'DersKodu':'MAT 101', 'Min': 'DD'}") \
        == "FIZ 101 (en az CC) ve MAT 101 (en az DD)"


def test_unrecognised_text_is_returned_as_is_not_invented():
    """Tanımadığımız bir şekil gelirse uydurma — olduğu gibi göster."""
    assert engine.onsart_metni("bilinmeyen bir sey") == "bilinmeyen bir sey"


def test_empty_input_is_safe():
    assert engine.onsart_metni("") == ""
    assert engine.onsart_metni(None) == ""


def test_val11_is_now_a_known_code():
    """OBS alan adını söyledi: uyulmayanOnsartlar."""
    assert "VAL11" in engine.HATA_KODLARI
    assert "nkoşul" in engine.HATA_KODLARI["VAL11"]


def test_val11_message_carries_the_requirement(monkeypatch):
    """Uçtan uca: kullanıcı hangi dersi hangi notla alması gerektiğini görmeli."""
    mesaj = engine.obs_aciklama({"uyulmayanOnsartlar": GERCEK_1})
    assert "MAT 104" in mesaj and "DD" in mesaj
    assert "DersKodu" not in mesaj


# ══════════════════════════════════════════════════════════════
# Bilinen kod, OBS'in ayrıntısını YUTMAMALI
# ══════════════════════════════════════════════════════════════
#
# VAL11'i HATA_KODLARI'na eklemek tek başına bir REGRESYON yaratıyor:
# kod artık "bilinen" sayıldığı için resultData okunmayan dala düşüyor ve
# kullanıcı yine "Önkoşul sağlanmadı" görüp hangi dersi hangi notla alması
# gerektiğini öğrenemiyor. Etiket koddan, ayrıntı OBS'ten gelmeli.


class _SahteYanit200:
    status_code = 200

    def __init__(self, sonuclar):
        self._s = sonuclar

    def json(self):
        return {"ecrnResultList": self._s}


def _kos_tek_deneme(monkeypatch, sonuclar):
    m = engine.RegistrationEngine(token="t", ecrn_list=["14771"],
                                  kayit_saati="23:59:00", max_deneme=1)
    monkeypatch.setattr(m, "_prepare_fire", lambda: None)
    monkeypatch.setattr(m, "_request_for", lambda c: object())
    monkeypatch.setattr(engine.time, "sleep", lambda s: None)

    class S:
        def send(self, *a, **k):
            return _SahteYanit200(sonuclar)
    monkeypatch.setattr(m, "session", S())
    m._kayit_yap()
    return m._crn_results["14771"]["message"]


def test_val11_result_keeps_the_course_requirement(monkeypatch):
    mesaj = _kos_tek_deneme(monkeypatch, [{
        "crn": "14771", "statusCode": 1, "resultCode": "VAL11",
        "resultData": {"uyulmayanOnsartlar": GERCEK_1},
    }])
    assert "MAT 104" in mesaj, f"ayrıntı kayboldu: {mesaj!r}"
    assert "DD" in mesaj
    assert "nkoşul" in mesaj


def test_unknown_code_still_shows_whatever_obs_sent(monkeypatch):
    mesaj = _kos_tek_deneme(monkeypatch, [{
        "crn": "14771", "statusCode": 1, "resultCode": "VAL21",
        "resultData": {"mesaj": "Aktif ders seçim zamanınız değil"},
    }])
    assert "VAL21" in mesaj and "Aktif ders" in mesaj


def test_known_code_without_data_is_not_polluted(monkeypatch):
    mesaj = _kos_tek_deneme(monkeypatch, [{
        "crn": "14771", "statusCode": 1, "resultCode": "VAL11",
        "resultData": None,
    }])
    assert mesaj == "Önkoşul sağlanmadı"
