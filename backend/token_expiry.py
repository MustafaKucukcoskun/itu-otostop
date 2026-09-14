"""OBS token'ının kayıt saatinden önce dolup dolmadığını anlar.

NEDEN VAR — dersi kaçırmanın en sessiz yolu buydu:

Kullanıcı akşam kurulum yapıyor, arayüz "6 saat sonra sona erecek" diyor
(sakin bir bilgi), motor başlıyor ve BAŞLANGIÇTAKİ token kontrolü geçiyor.
Motor saatlerce bekliyor, ertesi gün ateşliyor — ama token gece yarısı ölmüş.
OBS 401 dönüyor, ders gidiyor. Hiçbir aşamada uyarı yok, çünkü token yalnızca
BAŞLARKEN kontrol ediliyordu, ATEŞLEME ANINA göre değil.

Token OBS'in gizli anahtarıyla imzalı; doğrulayamayız. Ama `exp` alanı imzasız
da okunabilir ve tek ihtiyacımız olan o. İmza doğrulanmadığı için bu değere
güvenlik kararı bağlanmaz — yalnızca kullanıcıyı uyarmak için kullanılır.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Optional

# Ateşlemeden sonra yeniden denemeler için gereken asgari pay.
# Motor max_deneme × retry_aralik boyunca deneyebiliyor; token tam tetikte
# ölürse ilk istek bile geçmeyebilir.
DEFAULT_MARGIN = 120.0


def token_exp(token: str) -> Optional[float]:
    """Token'ın `exp` alanını döndürür; okunamazsa None.

    None "sorun yok" demek DEĞİL, "bilmiyoruz" demektir. Çağıran taraf
    bilinmezlik yüzünden kullanıcıyı engellememelidir.
    """
    if not token or not isinstance(token, str):
        return None
    parcalar = token.split(".")
    if len(parcalar) < 2:
        return None
    govde = parcalar[1]
    # JWT base64'ü dolgusuz (padding'siz) gelir; eksik '=' tamamlanmalı
    govde += "=" * (-len(govde) % 4)
    try:
        veri = json.loads(base64.urlsafe_b64decode(govde))
    except Exception:
        return None
    exp = veri.get("exp")
    if isinstance(exp, (int, float)) and exp > 0:
        return float(exp)
    return None


def expires_before(
    token: str, target_epoch: float, margin: float = DEFAULT_MARGIN
) -> bool:
    """Token ateşleme anından önce (ya da payın içinde) ölüyor mu?

    True → bu token'la kayıt yapılamaz, kullanıcı yenisini almalı.
    False → ya yeterince uzun geçerli ya da exp okunamadı (belirsizlikte geç).
    """
    exp = token_exp(token)
    if exp is None:
        return False
    return exp <= (target_epoch + margin)


def remaining_after_target(token: str, target_epoch: float) -> Optional[float]:
    """Ateşleme anında token'ın ömründen kaç saniye kalıyor (teşhis için)."""
    exp = token_exp(token)
    return None if exp is None else exp - target_epoch


def _now() -> float:  # testlerde saat enjekte etmeyi kolaylaştırır
    return time.time()
