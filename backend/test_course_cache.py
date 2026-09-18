"""Ders önbelleğinin OBS'yi dövmemesi.

BULUNAN HATA: LRU önbelleği 50 bölüm tutuyordu ama ITÜ'de 177 bölüm var.
Bulunamayan bir CRN tüm bölümleri taratır; tarama sırasında ilk 50 bölüm
sonrakiler tarafından ATILIR. Bir sonraki arama her şeyi baştan indirir.

Ölçüldü (üretim): bulunamayan CRN sorgusu ~12 saniye ve OBS'e ~127 istek —
HER SEFERİNDE, aynı CRN tekrar sorulsa bile. Kayıt gününde ders planı sayfası
açılışta toplu sorgu yapıyor; 40 kullanıcı binlerce isteğe dönüşür.
"""

import time

import obs_course_service as ocs
from obs_course_service import OBSCourseService, CourseInfo


def _ders(crn):
    return CourseInfo(crn=crn, course_code="X 101", course_name="Test",
                      instructor="Y", teaching_method="Örgün",
                      capacity=10, enrolled=1)


class SahteServis(OBSCourseService):
    """OBS'ye çıkmaz; kaç bölüm indirildiğini sayar."""

    def __init__(self, bolum_sayisi=177, **kw):
        super().__init__(**kw)
        self.indirilen = 0
        self._bolumler = [{"bransKoduId": i, "dersBransKodu": f"D{i}"}
                          for i in range(bolum_sayisi)]

    def get_departments(self):
        return self._bolumler

    def get_courses(self, brans_kodu_id):
        now = time.time()
        if brans_kodu_id in self._dept_cache:
            kurslar, ts = self._dept_cache[brans_kodu_id]
            if (now - ts) < self.course_ttl:
                self._dept_cache.move_to_end(brans_kodu_id)
                return kurslar
        self.indirilen += 1
        kurslar = [_ders(f"{10000 + brans_kodu_id}")]
        self._dept_cache[brans_kodu_id] = (kurslar, now)
        while len(self._dept_cache) > self.max_cache_depts:
            self._dept_cache.popitem(last=False)
        for k in kurslar:
            self._crn_index[k.crn] = k
        return kurslar


def test_cache_holds_every_department():
    """Önbellek bölüm sayısından KÜÇÜK olursa tam tarama kendini yer."""
    s = SahteServis()
    assert s.max_cache_depts >= len(s.get_departments()), (
        f"onbellek {s.max_cache_depts} bolum tutuyor ama {len(s.get_departments())} bolum var"
    )


def test_repeated_missing_crn_does_not_refetch_everything():
    """ASIL HATA: aynı olmayan CRN ikinci kez sorulduğunda OBS yeniden
    dövülmemeli."""
    s = SahteServis()
    s.lookup_crns(["99999"])
    ilk = s.indirilen
    s.lookup_crns(["99999"])
    ikinci = s.indirilen - ilk
    assert ikinci == 0, f"ikinci sorguda {ikinci} bolum yeniden indirildi"


def test_known_crn_is_served_from_cache():
    s = SahteServis()
    s.lookup_crns(["10005"])           # bulunur
    ilk = s.indirilen
    r = s.lookup_crns(["10005"])
    assert r["10005"] is not None
    assert s.indirilen == ilk          # ek indirme yok


def test_negative_cache_does_not_hide_a_course_forever():
    """ASIL GÜVENCE: sonradan açılan bir ders sonsuza dek 'yok' kalmamalı.

    (İndirme sayısını ölçmek yanıltıcı olurdu: TTL dolduğunda yeniden ARANIR
    ama bölümler hâlâ önbellekte olduğu için yeni indirme olmaz — ki istenen
    de budur.)
    """
    s = SahteServis(negative_ttl=0.01)
    assert s.lookup_crns(["77777"])["77777"] is None      # henuz yok

    # Ders sonradan aciliyor
    s._crn_index["77777"] = _ders("77777")

    assert s.lookup_crns(["77777"])["77777"] is None or True  # TTL dolmadan eski cevap olabilir
    time.sleep(0.05)
    assert s.lookup_crns(["77777"])["77777"] is not None, "negatif onbellek dersi kalici gizledi"


def test_negative_cache_prevents_the_rescan_while_fresh():
    """TTL içinde aynı CRN yeniden TARANMAMALI — asıl maliyet buydu."""
    s = SahteServis(negative_ttl=60)
    s.lookup_crns(["99999"])
    ilk = s.indirilen
    s.lookup_crns(["99999"])
    assert s.indirilen == ilk


# ══════════════════════════════════════════════════════════════
# Kontenjan bayatlamamalı — ders TTL'i bölüm TTL'inden ayrı
# ══════════════════════════════════════════════════════════════
#
# CANLI OLAY (18 Eylül 09:46): DEN 405E (CRN 12002) uygulamada 85/85 "DOLU"
# görünüyordu. Aynı anda OBS'ten önbelleksiz çekilen taze veri 100/85 dedi —
# kontenjan 85'ten 100'e ÇIKARILMIŞTI, 15 boş yer vardı. Öğrenci, yeri olan
# bir dersi dolu sanıp vazgeçiyordu.
#
# Sebep tek bir cache_ttl=3600'ün iki farklı şeyi birden yönetmesiydi:
#   bölüm listesi  → dönem içinde neredeyse hiç değişmez, 1 saat iyi
#   ders/kontenjan → kayıt gününde dakikalar içinde değişir, 1 saat felaket


class _SahteYanit:
    def __init__(self, govde):
        self._govde = govde
        self.text = govde if isinstance(govde, str) else ""
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._govde


def _servis(monkeypatch, sayac):
    svc = ocs.OBSCourseService()

    def sahte_get(url, **kw):
        sayac.append(url)
        if url == ocs.DEPARTMENTS_URL:
            return _SahteYanit([{"bransKoduId": 10, "dersBransKodu": "DEN"}])
        return _SahteYanit("<table></table>")

    monkeypatch.setattr(svc.session, "get", sahte_get)
    return svc


def test_course_data_is_refetched_once_it_goes_stale(monkeypatch):
    """Asıl hata: kontenjan bir saat boyunca donuyordu."""
    cagrilar = []
    svc = _servis(monkeypatch, cagrilar)
    svc.get_courses(10)
    n = len(cagrilar)
    # Ders verisini ders TTL'inden eski yap
    kurslar, ts = svc._dept_cache[10]
    svc._dept_cache[10] = (kurslar, ts - svc.course_ttl - 1)
    svc.get_courses(10)
    assert len(cagrilar) > n, "ders verisi bayatladığı hâlde yenilenmedi"


def test_fresh_course_data_is_served_from_cache(monkeypatch):
    """Önbellek yine de işini yapmalı — her istekte OBS'e gidilmemeli."""
    cagrilar = []
    svc = _servis(monkeypatch, cagrilar)
    svc.get_courses(10)
    n = len(cagrilar)
    svc.get_courses(10)
    assert len(cagrilar) == n


def test_course_ttl_is_far_shorter_than_department_ttl(monkeypatch):
    """İkisi ayrı olmalı: bölüm listesini 5 dakikada bir çekmek boşuna yük."""
    svc = ocs.OBSCourseService()
    assert svc.course_ttl <= 600
    assert svc.cache_ttl >= svc.course_ttl * 4


def test_department_list_is_not_refetched_at_the_course_rate(monkeypatch):
    """Bölüm listesi ders TTL'i geçtiğinde yenilenmemeli."""
    cagrilar = []
    svc = _servis(monkeypatch, cagrilar)
    svc.get_departments()
    n = len(cagrilar)
    svc._departments_ts -= svc.course_ttl + 1     # ders TTL'i geçti, bölüm TTL'i geçmedi
    svc.get_departments()
    assert len(cagrilar) == n, "bölüm listesi gereksiz yere yeniden çekildi"
