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
