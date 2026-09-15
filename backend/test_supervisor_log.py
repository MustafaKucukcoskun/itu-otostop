"""Denetleyici hatalarının GÖRÜNÜR olması.

`_isolation_supervisor` tüm döngüyü `except Exception: pass` ile sarıyordu.
Devir mantığında bir hata olsa — konteynerler asla çekilmez ya da sözü geri
alınmaz — ve biz bunu ASLA öğrenemezdik. En kritik döngüde kör nokta.

Loglamak da körü körüne yapılamaz: hata her 2 saniyede bir tekrarlarsa log
akışını boğar ve kayıt günü teşhisi imkânsızlaşır. Bu yüzden ilk görülüşte
ve sonra seyrek loglanır.
"""

import main


def test_first_error_is_logged():
    sayac = {"n": 0}
    main._supervisor_error(RuntimeError("patlak"), sayac, yaz=lambda m: sayac.__setitem__("son", m))
    assert sayac["n"] == 1
    assert "patlak" in sayac["son"]


def test_repeated_errors_are_throttled():
    """Aynı hata her turda loglanmamalı — 2 saniyede bir log akışı boğar."""
    sayac = {"n": 0}
    yazilan = []
    for _ in range(40):
        main._supervisor_error(RuntimeError("ayni"), sayac, yaz=yazilan.append)
    assert 1 <= len(yazilan) <= 3, len(yazilan)


def test_a_new_error_is_logged_immediately():
    """Farklı bir hata beklemeden görünmeli — yeni bir arıza gizlenmemeli."""
    sayac = {"n": 0}
    yazilan = []
    for _ in range(5):
        main._supervisor_error(RuntimeError("birinci"), sayac, yaz=yazilan.append)
    n = len(yazilan)
    main._supervisor_error(ValueError("ikinci"), sayac, yaz=yazilan.append)
    assert len(yazilan) == n + 1
    assert "ikinci" in yazilan[-1]
