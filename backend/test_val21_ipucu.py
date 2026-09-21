# -*- coding: utf-8 -*-
"""Tanımadığımız kod, kullanıcıyı çıplak bırakmamalı — ama uydurmamalı da.

VAL21 hakkında bildiklerimiz (17 Eylül 14:00, x68zw):
  - 10 CRN'in HEPSİ aynı kodu aldı, cevap 49ms'de geldi (dokuz koşunun en
    hızlısı) — yani OBS kontenjan mantığına hiç girmeden kapıda kesmiş
  - o CRN'lerden ikisini AYNI SANİYEDE başka kullanıcılar aldı
  - biri 75 kontenjan / 23 kayıt, yani bol yer vardı
  - resmî takvim: 17 Eylül 14:00 slotu 3. SINIFA aitti

Hepsi "bu öğrencinin kayıt saati değildi" açıklamasına uyuyor. Ama bu bir
HİPOTEZ: OBS'in kendi metnini hiç görmedik. O yüzden ipucu KESİN DİLLE
verilmiyor ve OBS bir açıklama gönderdiyse ipucu değil O gösteriliyor —
OBS'in sözü bizim tahminimizi her zaman yener.
"""

import engine


def test_val21_gets_an_actionable_hint():
    m = engine.IPUCLARI.get("VAL21", "")
    assert m, "VAL21 hala tanimsiz"
    assert "kayıt saat" in m.lower() or "kayit saat" in m.lower()


def test_hint_is_hedged_not_asserted():
    """Kesin konuşmuyoruz: OBS'in metnini görmedik."""
    m = engine.IPUCLARI["VAL21"].lower()
    assert any(k in m for k in ("muhtemelen", "olabilir", "genelde")), m


def test_obs_explanation_wins_over_our_hint(monkeypatch):
    """OBS bir şey söylediyse bizim tahminimiz değil O gösterilir."""
    class Y:
        status_code = 200
        def json(self):
            return {"ecrnResultList": [{
                "crn": "12345", "statusCode": 1, "resultCode": "VAL21",
                "resultData": {"mesaj": "Aktif ders secim zamaniniz degil"},
            }]}
    m = engine.RegistrationEngine(token="t", ecrn_list=["12345"],
                                  kayit_saati="23:59:00", max_deneme=1)
    monkeypatch.setattr(m, "_prepare_fire", lambda: None)
    monkeypatch.setattr(m, "_request_for", lambda c: object())
    monkeypatch.setattr(engine.time, "sleep", lambda s: None)
    monkeypatch.setattr(m, "session", type("S", (), {"send": lambda s,*a,**k: Y()})())
    m._kayit_yap()
    mesaj = m._crn_results["12345"]["message"]
    assert "Aktif ders secim zamaniniz degil" in mesaj
    assert "Muhtemelen" not in mesaj, f"tahminimiz OBS'in sozuyle yan yana durdu: {mesaj}"


def test_val08_stays_undecoded():
    """VAL08 hakkinda kanitimiz yok — uydurmuyoruz."""
    assert "VAL08" not in engine.HATA_KODLARI and "VAL08" not in engine.IPUCLARI
