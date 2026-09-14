"""İzole konteyner devri için sahiplik/zamanlama mantığı testleri.

Ağa çıkmaz, saat enjekte edilir: tamamen deterministik.

Buradaki tek kritik güvence şu — bir kayıt YA izole konteynerden YA ana
servisten ateşlenir, asla ikisinden birden. Çift ateşleme OBS tarafında
VAL16 (debounce) tetikler ve kullanıcı dersi kaybeder.
"""

import pytest

from isolation import IsolationBroker


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


@pytest.fixture
def broker():
    clock = FakeClock()
    b = IsolationBroker(lead=900.0, ready_deadline=120.0, clock=clock)
    b.clock = clock  # testin saati ilerletebilmesi için
    return b


# ── Bilet ──


def test_ticket_is_unique_per_registration(broker):
    t1 = broker.register("s1", target_epoch=5000.0)
    t2 = broker.register("s2", target_epoch=5000.0)
    assert t1 != t2


def test_ticket_is_long_enough_to_be_unguessable(broker):
    """Bilet, kullanıcının OBS token'ını çekmeye yarıyor — tahmin edilememeli."""
    assert len(broker.register("s1", target_epoch=5000.0)) >= 32


# ── Sahiplik (tek ateşleyici garantisi) ──


def test_job_claim_succeeds_once(broker):
    ticket = broker.register("s1", target_epoch=5000.0)
    assert broker.claim_remote("s1", ticket) is True


def test_second_remote_claim_rejected(broker):
    """Cloud Run görevi yeniden denerse ikinci konteyner ateşlememeli."""
    ticket = broker.register("s1", target_epoch=5000.0)
    broker.claim_remote("s1", ticket)
    assert broker.claim_remote("s1", ticket) is False


def test_local_claim_blocked_after_remote_claimed(broker):
    """İzole konteyner sahiplendiyse ana servis yedeğe geçmemeli."""
    ticket = broker.register("s1", target_epoch=5000.0)
    broker.claim_remote("s1", ticket)
    assert broker.claim_local("s1") is False


def test_remote_claim_blocked_after_local_claimed(broker):
    """Yedek devreye girdiyse geç kalkan konteyner ateşlememeli."""
    ticket = broker.register("s1", target_epoch=5000.0)
    broker.claim_local("s1")
    assert broker.claim_remote("s1", ticket) is False


def test_wrong_ticket_rejected(broker):
    broker.register("s1", target_epoch=5000.0)
    assert broker.claim_remote("s1", "yanlis-bilet") is False


def test_claim_for_unknown_session_rejected(broker):
    assert broker.claim_remote("yok", "bilet") is False
    assert broker.claim_local("yok") is False


# ── Başlatma zamanlaması ──


def test_not_due_before_lead_window(broker):
    """Hedefe 20 dk varken 15 dk'lık pencere açılmamış olmalı."""
    broker.register("s1", target_epoch=broker.clock() + 1200)
    assert broker.due_for_launch() == []


def test_due_inside_lead_window(broker):
    broker.register("s1", target_epoch=broker.clock() + 800)
    assert [s for s, _ in broker.due_for_launch()] == ["s1"]


def test_launched_entry_not_returned_again(broker):
    """Aynı kullanıcı için iki konteyner açılmasın."""
    broker.register("s1", target_epoch=broker.clock() + 800)
    broker.mark_launched("s1")
    assert broker.due_for_launch() == []


def test_past_target_is_due_immediately(broker):
    """Hedef geçmişse beklemeden devret."""
    broker.register("s1", target_epoch=broker.clock() - 10)
    assert [s for s, _ in broker.due_for_launch()] == ["s1"]


# ── Yedeğe düşme ──


def test_fallback_due_when_remote_never_claims(broker):
    """Konteyner kalkmazsa ana servis son anda devralır — kullanıcı ders kaybetmez."""
    broker.register("s1", target_epoch=broker.clock() + 800)
    broker.mark_launched("s1")
    broker.clock.advance(700)  # hedefe 100s kaldı, eşik 120s
    assert broker.fallback_due() == ["s1"]


def test_fallback_not_due_while_deadline_far(broker):
    broker.register("s1", target_epoch=broker.clock() + 800)
    broker.mark_launched("s1")
    broker.clock.advance(500)  # hedefe 300s kaldı
    assert broker.fallback_due() == []


def test_fallback_not_due_when_remote_claimed(broker):
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.mark_launched("s1")
    broker.claim_remote("s1", ticket)
    broker.clock.advance(700)
    assert broker.fallback_due() == []


def test_fallback_due_even_if_launch_never_happened(broker):
    """Başlatma isteği hiç gitmediyse de yedek devralmalı.

    Aksi halde (Run API hatası, geç kayıt) kullanıcı hiç ateşlenmez. Sahiplik
    yoksa ve süre doldusa, sebebi ne olursa olsun ana servis üstlenir.
    """
    broker.register("s1", target_epoch=broker.clock() + 800)
    broker.clock.advance(700)
    assert broker.fallback_due() == ["s1"]


def test_late_registration_falls_back_immediately(broker):
    """Kullanıcı T-60s'de başlatırsa konteyner yetişemez (~70s provisioning)."""
    broker.register("s1", target_epoch=broker.clock() + 60)
    assert broker.fallback_due() == ["s1"]


# ── Temizlik ──


def test_release_removes_entry(broker):
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.release("s1")
    assert broker.due_for_launch() == []
    assert broker.claim_remote("s1", ticket) is False


def test_reregister_invalidates_old_ticket(broker):
    """Kullanıcı iptal edip yeniden başlatırsa eski konteyner ateşleyememeli."""
    old = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.release("s1")
    broker.register("s1", target_epoch=broker.clock() + 800)
    assert broker.claim_remote("s1", old) is False


# ── Bilet doğrulama (sahiplik almadan) ──


def test_verify_ticket_accepts_valid(broker):
    """Konteyner yapılandırmayı çekerken kimliğini kanıtlar ama sahiplenmez."""
    ticket = broker.register("s1", target_epoch=5000.0)
    assert broker.verify_ticket("s1", ticket) is True
    assert broker.owner_of("s1") is None  # doğrulama sahiplik VERMEZ


def test_verify_ticket_rejects_invalid(broker):
    broker.register("s1", target_epoch=5000.0)
    assert broker.verify_ticket("s1", "yanlis") is False
    assert broker.verify_ticket("s1", "") is False


def test_verify_ticket_rejects_unknown_session(broker):
    assert broker.verify_ticket("yok", "bilet") is False


def test_verify_ticket_still_works_after_claim(broker):
    """Sahiplenmiş konteyner olay akışını göndermeye devam edebilmeli."""
    ticket = broker.register("s1", target_epoch=5000.0)
    broker.claim_remote("s1", ticket)
    assert broker.verify_ticket("s1", ticket) is True


# ══════════════════════════════════════════════════════════════════
# Devir güvenliği — konteyner sahiplendikten SONRAKİ tehlikeler
# ══════════════════════════════════════════════════════════════════

# ── Geç sahiplenme reddi ──
# Konteyner hedefe çok yakın sahiplenirse yerel motor çoktan ateşlemiş
# olabilir; ikisi aynı token'la art arda POST atarsa OBS her ikisini de
# VAL16 ile düşürür ve ders kaybedilir.


def test_claim_refused_too_close_to_target(broker):
    broker2 = IsolationBroker(clock=broker.clock, min_claim_margin=20.0)
    broker2.clock = broker.clock
    ticket = broker2.register("s1", target_epoch=broker2.clock() + 10)
    assert broker2.claim_remote("s1", ticket) is False


def test_claim_allowed_with_enough_margin(broker):
    broker2 = IsolationBroker(clock=broker.clock, min_claim_margin=20.0)
    broker2.clock = broker.clock
    ticket = broker2.register("s1", target_epoch=broker2.clock() + 25)
    assert broker2.claim_remote("s1", ticket) is True


# ── Nabız (konteynerin hayatta olduğunun kanıtı) ──


def test_heartbeat_requires_valid_ticket(broker):
    broker.register("s1", target_epoch=broker.clock() + 800)
    assert broker.heartbeat("s1", "yanlis") is None


def test_heartbeat_reports_status(broker):
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    st = broker.heartbeat("s1", ticket)
    assert st == {"cancelled": False, "revoked": False}


def test_remote_considered_dead_without_heartbeat(broker):
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.claim_remote("s1", ticket)
    broker.heartbeat("s1", ticket)
    broker.clock.advance(30)
    assert broker.remote_alive("s1", max_age=10.0) is False


def test_remote_considered_alive_with_fresh_heartbeat(broker):
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.claim_remote("s1", ticket)
    broker.clock.advance(30)
    broker.heartbeat("s1", ticket)
    assert broker.remote_alive("s1", max_age=10.0) is True


def test_claim_counts_as_proof_of_life_but_goes_stale(broker):
    """Sahiplenme anı bir hayat kanıtıdır, ama diğer nabızlar gibi eskir.

    ASIL GÜVENCE: T-180s'de sahiplenip susan konteyner, devir anında
    (T-8s) ölü sayılır — yani yerel motor çekilmez ve ders kurtulur.
    """
    ticket = broker.register("s1", target_epoch=broker.clock() + 180)
    broker.claim_remote("s1", ticket)
    assert broker.remote_alive("s1", max_age=10.0) is True  # az önce sahiplendi

    broker.clock.advance(172)  # hedefe 8s — devir anı, konteyner hiç ses vermedi
    assert broker.remote_alive("s1", max_age=10.0) is False


def test_dead_remote_never_heartbeats_again(broker):
    """Ölü konteyner nabız atamaz; bu yüzden eskime tespiti çalışır."""
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.claim_remote("s1", ticket)
    broker.clock.advance(11)
    assert broker.remote_alive("s1", max_age=10.0) is False


# ── Devir anı (yerel motor ancak burada çekilir) ──


def test_handover_not_due_while_target_far(broker):
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.claim_remote("s1", ticket)
    assert broker.handover_due() == []


def test_handover_due_near_target(broker):
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.claim_remote("s1", ticket)
    broker.clock.advance(795)  # hedefe 5s
    assert broker.handover_due() == ["s1"]


def test_handover_not_due_for_unclaimed(broker):
    """Sahipsiz kayıt zaten yerel motorda; devir diye bir şey yok."""
    broker.register("s1", target_epoch=broker.clock() + 800)
    broker.clock.advance(795)
    assert broker.handover_due() == []


def test_handover_reported_once(broker):
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.claim_remote("s1", ticket)
    broker.clock.advance(795)
    broker.mark_handover_decided("s1")
    assert broker.handover_due() == []


# ── Sahipliği geri alma (ölü konteyner) ──


def test_revoke_returns_ownership_so_local_can_fire(broker):
    """Konteyner öldüyse yerel motor devralabilmeli — asıl felaket
    ateşleyen KİMSENİN olmaması."""
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.claim_remote("s1", ticket)
    broker.revoke("s1")
    assert broker.owner_of("s1") is None
    assert broker.claim_local("s1") is True


def test_revoked_container_cannot_reclaim(broker):
    """Geri alınmış kayıt, sonradan canlanan konteynerce ateşlenemez."""
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.claim_remote("s1", ticket)
    broker.revoke("s1")
    assert broker.claim_remote("s1", ticket) is False


def test_revoked_flag_reaches_container_via_heartbeat(broker):
    """Konteyner nabızdan geri alındığını öğrenip kendini iptal etmeli."""
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.claim_remote("s1", ticket)
    broker.revoke("s1")
    assert broker.heartbeat("s1", ticket)["revoked"] is True


# ── İptal konteynere ulaşmalı ──


def test_cancel_flag_reaches_container(broker):
    """Kullanıcı iptal edince konteyner bunu nabızdan öğrenir ve durur."""
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.claim_remote("s1", ticket)
    broker.request_cancel("s1")
    assert broker.heartbeat("s1", ticket)["cancelled"] is True


def test_cancel_keeps_entry_so_container_can_learn(broker):
    """release() kaydı silerdi; o zaman konteyner nabız atamaz ve
    iptali hiç öğrenemezdi."""
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.request_cancel("s1")
    assert broker.heartbeat("s1", ticket) is not None


def test_cancelled_registration_cannot_be_claimed(broker):
    ticket = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.request_cancel("s1")
    assert broker.claim_remote("s1", ticket) is False


def test_is_cancelled_reports_state(broker):
    broker.register("s1", target_epoch=broker.clock() + 800)
    assert broker.is_cancelled("s1") is False
    broker.request_cancel("s1")
    assert broker.is_cancelled("s1") is True


# ── Çok kullanıcı bağımsızlığı ──


def test_sessions_are_independent(broker):
    """Bir kullanıcının iptali/devri diğerini etkilememeli."""
    t1 = broker.register("s1", target_epoch=broker.clock() + 800)
    t2 = broker.register("s2", target_epoch=broker.clock() + 800)
    broker.claim_remote("s1", t1)
    broker.request_cancel("s1")
    assert broker.owner_of("s2") is None
    assert broker.is_cancelled("s2") is False
    assert broker.claim_remote("s2", t2) is True


def test_ticket_of_one_session_cannot_claim_another(broker):
    """Bir kullanıcının konteyneri başkasının kaydını ateşleyememeli."""
    t1 = broker.register("s1", target_epoch=broker.clock() + 800)
    broker.register("s2", target_epoch=broker.clock() + 800)
    assert broker.claim_remote("s2", t1) is False
    assert broker.verify_ticket("s2", t1) is False


# ── Başlatma hatasında sınırlı yeniden deneme ──


def test_launch_failure_allows_retry(broker):
    """Run API geçici hata verirse izolasyon kalıcı kaybedilmemeli."""
    broker.register("s1", target_epoch=broker.clock() + 800)
    broker.mark_launched("s1")
    assert broker.due_for_launch() == []
    broker.launch_failed("s1", "503")
    assert [s for s, _ in broker.due_for_launch()] == ["s1"]


def test_launch_gives_up_after_three_attempts(broker):
    """Kalıcı hata Run API'sini 900 saniye boyunca dövmemeli."""
    broker.register("s1", target_epoch=broker.clock() + 800)
    for _ in range(3):
        broker.mark_launched("s1")
        broker.launch_failed("s1", "503")
    assert broker.due_for_launch() == []


def test_successful_launch_is_never_repeated(broker):
    broker.register("s1", target_epoch=broker.clock() + 800)
    broker.mark_launched("s1")
    assert broker.due_for_launch() == []
    assert broker.due_for_launch() == []


# ── Biten kayıtların temizliği ──


def test_finished_registrations_are_purged(broker):
    """Kayıtlar sonsuza kadar birikmemeli; servis aylarca ayakta kalıyor."""
    broker.register("s1", target_epoch=broker.clock() - 4000)  # çoktan geçti
    broker.register("s2", target_epoch=broker.clock() + 800)
    silinen = broker.purge_finished(older_than=3600.0)
    assert silinen == ["s1"]
    assert broker.target_of("s1") is None
    assert broker.target_of("s2") is not None


def test_purge_keeps_recently_fired_registrations(broker):
    """Yeni biten kayıt durmalı: kullanıcı hâlâ sonucu izliyor olabilir."""
    broker.register("s1", target_epoch=broker.clock() - 60)
    assert broker.purge_finished(older_than=3600.0) == []
