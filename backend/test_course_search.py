"""Ders adına göre arama — metin eşleştirme birim testleri.

Ağa çıkmaz: yalnızca saf eşleştirme mantığını test eder.
"""

from obs_course_service import fold_tr, matches_query


# ── Türkçe katlama ──


def test_fold_lowercases_turkish_dotted_i():
    """Python'ın .lower()'ı İ'yi yanlış katlar; Türkçe'de İ → i olmalı."""
    assert fold_tr("İSTATİSTİK") == "istatistik"


def test_fold_lowercases_turkish_dotless_i():
    """I → ı, sonra aksan temizliğiyle i'ye iner."""
    assert fold_tr("IŞIK") == "isik"


def test_fold_strips_diacritics():
    """Kullanıcı Türkçe karakter yazmadan da bulabilmeli."""
    assert fold_tr("Akışkanlar Mekaniği") == "akiskanlar mekanigi"
    assert fold_tr("Çevre Mühendisliği") == "cevre muhendisligi"
    assert fold_tr("Öğrenme") == "ogrenme"


def test_fold_is_idempotent():
    once = fold_tr("Şehir ve Bölge Planlama")
    assert fold_tr(once) == once


# ── Sorgu eşleştirme ──


def test_matches_plain_substring():
    assert matches_query("mekani", "Akışkanlar Mekaniği", "AKM 204") is True


def test_matches_without_turkish_characters():
    """En önemli senaryo: klavyeden Türkçe karakter yazmayan kullanıcı."""
    assert matches_query("akiskanlar", "Akışkanlar Mekaniği", "AKM 204") is True
    assert matches_query("muhendis", "Çevre Mühendisliği", "CEV 101") is True


def test_stemming_is_not_supported():
    """BİLİNEN SINIR: Türkçe ek almada ünsüz yumuşaması (k → ğ) çözülmüyor.

    "mekanik" yazan kullanıcı "Mekaniği"yi bulamaz. Gövdeleme gerektirir.
    Ucuz çözüm (ğ ile k'yi eşitlemek) "kaz" aramasını "gaz" ile eşleştirir —
    yanlış sonuç üretmektense eksik sonuç vermek tercih edildi.
    Arayüz bu yüzden kullanıcıyı kısa kök yazmaya yönlendirmeli.
    """
    assert matches_query("mekanik", "Akışkanlar Mekaniği", "AKM 204") is False


def test_matches_course_code_too():
    assert matches_query("akm 204", "Akışkanlar Mekaniği", "AKM 204") is True


def test_matches_all_words_not_just_one():
    """Çok kelimeli sorguda kelimelerin HEPSİ geçmeli — yoksa alakasız sonuç yağar."""
    assert matches_query("akiskanlar mekanigi", "Akışkanlar Mekaniği", "AKM 204") is True
    assert matches_query("akiskanlar termodinamik", "Akışkanlar Mekaniği", "AKM 204") is False


def test_does_not_match_unrelated():
    assert matches_query("kimya", "Akışkanlar Mekaniği", "AKM 204") is False


def test_empty_query_does_not_match():
    assert matches_query("", "Akışkanlar Mekaniği", "AKM 204") is False
    assert matches_query("   ", "Akışkanlar Mekaniği", "AKM 204") is False
