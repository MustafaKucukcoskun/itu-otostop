# -*- coding: utf-8 -*-
"""Geç kalan kullanıcı denemeden reddedilmemeli.

CANLI OLAY — iki gerçek kullanıcı, iki ayrı gün, aynı duvar:

  17 Eylül 14:03:53  (hedeften 233sn sonra)  → HTTP 400
  18 Eylül 14:02:27  (hedeften 147sn sonra)  → HTTP 400

İkisinin de kurulumu geçerliydi: hemen öncesinde /api/config 200 dönmüş.
17 Eylül'deki kullanıcı zaten 13:57'de başarıyla kayıt yapmıştı ve kaçırdığı
bir ders için tekrar denemek istedi; 18 Eylül'deki kullanıcı sadece iki
dakika geç kalmıştı.

Oysa kayıt penceresi saatlerce açık kalıyor — boş kontenjanı olan bir ders
hâlâ alınabilirdi. Sınırın varlık sebebi "akşamdan kurup ertesi güne
bırakmak" vakası; o vakada hedef SAATLERCE geride olur. 120 saniye bu ayrımı
yapmak için fazla dar, kodun kendi yorumu bile "birkaç dakikalık gecikme
denemeye değer" diyordu.
"""

import main


def test_two_minutes_late_is_allowed():
    """18 Eylül'deki kullanıcının tam durumu."""
    assert main.GECMIS_HEDEF_TOLERANSI > 147


def test_four_minutes_late_is_allowed():
    """17 Eylül'deki kullanıcının tam durumu."""
    assert main.GECMIS_HEDEF_TOLERANSI > 233


def test_half_an_hour_late_is_still_worth_trying():
    """Pencere saatlerce açık; yarım saat geç kalan da denemeli."""
    assert main.GECMIS_HEDEF_TOLERANSI >= 1800


def test_the_night_before_setup_is_still_refused():
    """Sınırın varlık sebebi bu: akşamdan kurulan kayıt saatlerce geride olur.

    Tolerans bunu da geçirirse motor kapalı pencereye altmış kez ateşler ve
    kullanıcı 'başlatıldı' yazısını gördükten sonra hiçbir şey olmaz.
    """
    assert main.GECMIS_HEDEF_TOLERANSI < 6 * 3600
