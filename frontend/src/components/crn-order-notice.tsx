"use client";

import { useState, useSyncExternalStore } from "react";
import { usePathname } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

/**
 * CRN sırası uyarısı — kayıt gününün en pahalı bilgisi.
 *
 * 17 Eylül canlı loglarından ölçüldü: OBS, istekteki CRN listesini SIRAYLA
 * işliyor ve yoğun slotta CRN başına 170-1100ms harcıyor (5 CRN → 845ms,
 * 11 CRN → 10sn+ zaman aşımı). O gün kontenjana takılan dört dersin dördü de
 * listenin sonundaydı — TUR 121 9/11'de, TUR 122 ise 9/9'da. Listenin 9.
 * sırasındaki bir ders, isteğimiz OBS'e vardıktan yaklaşık sekiz saniye sonra
 * karara bağlanıyor; motorun tetik hassasiyeti ise milisaniye mertebesinde.
 * Yani sıralama, zamanlamadan üç basamak daha belirleyici.
 *
 * Uyarı sekme oturumu başına bir kez çıkar (sessionStorage): siteyi yeniden
 * açan görür, aynı sekmede çalışırken tekrar tekrar rahatsız edilmez. Her
 * yenilemede çıkarsaydı okunmadan kapatılmaya başlanırdı ki asıl amaç budur.
 */

const ONAY_ANAHTARI = "otostop_crn_sira_uyarisi_v1";
const GIZLI_YOLLAR = ["/sign-in", "/sign-up"];

// sessionStorage'ı effect içinde okuyup setState etmek React Compiler'da
// kademeli render uyarısı veriyor; tarayıcı durumunu okumanın doğru yolu
// useSyncExternalStore. Kimse bizden başka yazmadığı için abonelik boş.
const aboneOl = () => () => {};

function istemciOkundu() {
  try {
    return sessionStorage.getItem(ONAY_ANAHTARI) !== null;
  } catch {
    // Depolama kapalıysa (gizli sekme, site verisi engelli) uyarıyı yine
    // göster — bilgiyi kaçırmak, fazladan bir tık atmaktan pahalı.
    return false;
  }
}

// Sunucuda ve hidrasyon anında kapalı: sunucunun sessionStorage'ı yok.
const sunucuOkundu = () => true;

export function CrnOrderNotice() {
  const pathname = usePathname();
  const okundu = useSyncExternalStore(aboneOl, istemciOkundu, sunucuOkundu);
  const [kapatildi, setKapatildi] = useState(false);

  const gizliSayfa = GIZLI_YOLLAR.some((p) => pathname.startsWith(p));
  const acik = !gizliSayfa && !okundu && !kapatildi;

  const onayla = () => {
    try {
      sessionStorage.setItem(ONAY_ANAHTARI, "1");
    } catch {
      // Yazamazsak sonraki açılışta tekrar çıkar; kabul edilebilir.
    }
    setKapatildi(true);
  };

  return (
    <Dialog open={acik}>
      <DialogContent
        showCloseButton={false}
        onEscapeKeyDown={(e) => e.preventDefault()}
        onPointerDownOutside={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
        className="gap-0 rounded-none border p-0 sm:max-w-md"
      >
        <div className="flex h-11 items-center border-b px-4">
          <DialogTitle className="font-mono text-[11px] font-medium tracking-widest uppercase">
            Kayıt Günü Uyarısı
          </DialogTitle>
        </div>

        <div className="space-y-4 px-4 py-5">
          <p className="text-base leading-snug font-semibold">
            En çok kapışılan dersi CRN listesinin{" "}
            <span className="text-primary">en başına</span> yaz.
          </p>

          <DialogDescription className="text-sm leading-relaxed">
            OBS listeni sırayla işliyor ve yoğun saatlerde her CRN için ayrı
            zaman harcıyor. Listenin sonundaki ders, isteğin ulaştıktan
            saniyeler sonra değerlendiriliyor — o arada kontenjan bitebiliyor.
          </DialogDescription>

          <div className="border-l-2 border-primary bg-accent/40 px-3 py-2.5">
            <p className="font-mono text-[11px] leading-relaxed text-muted-foreground">
              17 Eylül ölçümü: 5 CRN → 845ms, 11 CRN → 10sn+.
              <br />O gün kontenjana takılan derslerin{" "}
              <span className="text-foreground">hepsi listenin sonundaydı.</span>
            </p>
          </div>

          <p className="text-sm leading-relaxed text-muted-foreground">
            Ayrıca listende <span className="text-foreground">olmayan bir CRN
            varsa sil</span> — o da sırada yer tutuyor ve işlenme süresi harcıyor.
          </p>
        </div>

        <div className="border-t px-4 py-3">
          <Button
            onClick={onayla}
            className="h-9 w-full rounded-none font-mono text-[11px] tracking-widest uppercase"
          >
            Okudum, listemi sıraladım
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
