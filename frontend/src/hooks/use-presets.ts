"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useUser } from "@clerk/nextjs";
import { toast } from "sonner";
import { PresetService } from "@/lib/preset-service";

export interface Preset {
  id: string;
  name: string;
  ecrn_list: string[];
  scrn_list: string[];
  kayit_saati: string;
  max_deneme: number;
  retry_aralik: number;
  created_at: number;
}

const STORAGE_KEY = "otostop-presets";
const OWNER_KEY = "otostop-presets-owner";

/**
 * GİRİŞ YAPMIŞ KULLANICIDA BULUT TEK DOĞRULUK KAYNAĞIDIR.
 *
 * localStorage yalnızca iki iş yapar: giriş yapmamış kullanıcı için tek cihazlık
 * saklama, ve giriş yapmış kullanıcı için buluta ulaşılamadığında gösterilecek
 * salt-okunur önbellek. Şablon listesi asla yerelden buluta doğru "tamir"
 * edilmez — eski sürüm bunu yapıyordu ve şablonları çoğaltıyordu.
 */
function loadLocal(): Preset[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveLocal(presets: Preset[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(presets));
  } catch {
    /* localStorage dolu veya kapalı */
  }
}

export function usePresets() {
  const { user } = useUser();
  const userId = user?.id ?? null;

  const [presets, setPresets] = useState<Preset[]>([]);
  const loadedForRef = useRef<string | null>(null);

  /** Buluttan tazele; başarılıysa true. */
  const refreshFromCloud = useCallback(async (uid: string) => {
    const cloud = await PresetService.getUserPresets(uid);
    if (cloud === null) return false; // buluta ulaşılamadı
    setPresets(cloud);
    saveLocal(cloud);
    return true;
  }, []);

  useEffect(() => {
    if (!userId) {
      // Giriş yok: tek cihazlık yerel liste
      if (loadedForRef.current !== null) loadedForRef.current = null;
      setPresets(loadLocal()); // eslint-disable-line react-hooks/set-state-in-effect -- SSR + kullanıcı değişimi
      return;
    }
    if (loadedForRef.current === userId) return;
    loadedForRef.current = userId;

    (async () => {
      const cloud = await PresetService.getUserPresets(userId);

      if (cloud === null) {
        // Buluta ulaşılamadı. Yerel önbelleği göster ama ona GÜVENME:
        // yeniden yükleme yapılmaz, yoksa her ağ hatası şablonları çoğaltır.
        const lastOwner = localStorage.getItem(OWNER_KEY);
        setPresets(lastOwner === userId ? loadLocal() : []);
        loadedForRef.current = null; // bir dahaki sefere yeniden dene
        toast.warning("Şablonlar buluttan okunamadı — çevrimdışı görünüm", {
          duration: 5000,
        });
        return;
      }

      if (cloud.length > 0) {
        setPresets(cloud);
        saveLocal(cloud);
        localStorage.setItem(OWNER_KEY, userId);
        return;
      }

      // Bulut GERÇEKTEN boş. Bu kullanıcıya ait yerel şablonlar varsa bir
      // defaya mahsus taşı — ve taşıdıktan sonra BULUTTAN YENİDEN OKU.
      // Eski sürüm okumuyordu: yerelde eski rastgele id kalıyordu, silme o id
      // ile buluta gidip hiçbir satır silmiyordu ve şablon geri geliyordu.
      const lastOwner = localStorage.getItem(OWNER_KEY);
      const local = lastOwner === userId ? loadLocal() : [];
      if (local.length > 0) {
        for (const p of local) {
          await PresetService.savePreset(userId, {
            name: p.name,
            ecrn_list: p.ecrn_list,
            scrn_list: p.scrn_list,
            kayit_saati: p.kayit_saati,
            max_deneme: p.max_deneme,
            retry_aralik: p.retry_aralik,
          });
        }
        await refreshFromCloud(userId);
      } else {
        setPresets([]);
        saveLocal([]);
      }
      localStorage.setItem(OWNER_KEY, userId);
    })();
  }, [userId, refreshFromCloud]);

  const addPreset = useCallback(
    (name: string, config: Omit<Preset, "id" | "name" | "created_at">): Preset => {
      const preset: Preset = {
        ...config,
        id: crypto.randomUUID(),
        name,
        created_at: Date.now(),
      };

      // İyimser gösterim — bulut id'si gelince gerçeğiyle değiştirilir
      setPresets((prev) => {
        const next = [...prev, preset];
        saveLocal(next);
        return next;
      });

      if (userId) {
        PresetService.savePreset(userId, {
          name: preset.name,
          ecrn_list: preset.ecrn_list,
          scrn_list: preset.scrn_list,
          kayit_saati: preset.kayit_saati,
          max_deneme: preset.max_deneme,
          retry_aralik: preset.retry_aralik,
        }).then((cloudId) => {
          if (cloudId) {
            // Bulut id'si YERELE YAZILIR. Yazılmazsa silme çalışmaz.
            setPresets((prev) => {
              const next = prev.map((p) =>
                p.id === preset.id ? { ...p, id: cloudId } : p,
              );
              saveLocal(next);
              return next;
            });
          } else {
            toast.warning(
              `"${preset.name}" buluta kaydedilemedi — yalnızca bu tarayıcıda duruyor`,
              { duration: 6000 },
            );
          }
        });
      }

      return preset;
    },
    [userId],
  );

  const deletePreset = useCallback(
    async (id: string) => {
      const hedef = presets.find((p) => p.id === id);

      // İyimser kaldır — ekran anında tepki versin
      setPresets((prev) => {
        const next = prev.filter((p) => p.id !== id);
        saveLocal(next);
        return next;
      });

      if (!userId || !hedef) return;

      await PresetService.deletePreset(userId, id);

      // SONUCU DOĞRULA. Silme "başarılı" görünüp hiçbir satır silmemiş olabilir:
      // eski göç hatası yüzünden bazı şablonların yerel id'si bulut id'siyle
      // uyuşmuyor. Kullanıcının gördüğü "silindi" mesajı gerçeği yansıtmalı.
      let cloud = await PresetService.getUserPresets(userId);

      if (cloud?.some((p) => p.id === id || p.name === hedef.name)) {
        // id ile silinememiş — onarım yolu: ada göre sil
        await PresetService.deletePresetsByName(userId, hedef.name);
        cloud = await PresetService.getUserPresets(userId);
      }

      if (cloud === null) {
        toast.warning(
          "Şablon buluttan silinemedi — başka cihazda görünmeye devam edebilir",
          { duration: 6000 },
        );
        return;
      }

      setPresets(cloud);
      saveLocal(cloud);

      if (cloud.some((p) => p.name === hedef.name)) {
        toast.error(
          `"${hedef.name}" buluttan silinemedi. Supabase'de 002_user_data.sql migration'ı çalıştırılmalı.`,
          { duration: 8000 },
        );
      }
    },
    [presets, userId],
  );

  const updatePreset = useCallback(
    (id: string, config: Partial<Omit<Preset, "id" | "created_at">>) => {
      setPresets((prev) => {
        const next = prev.map((p) => (p.id === id ? { ...p, ...config } : p));
        saveLocal(next);
        return next;
      });
    },
    [],
  );

  const exportPresets = useCallback((): string => {
    return JSON.stringify(presets, null, 2);
  }, [presets]);

  const importPresets = useCallback(
    (json: string): number => {
      try {
        const parsed = JSON.parse(json);
        if (!Array.isArray(parsed)) return 0;
        const mevcut = new Set(presets.map((p) => p.name));
        const yeniler = parsed.filter(
          (p) => p?.name && Array.isArray(p.ecrn_list) && !mevcut.has(p.name),
        );
        if (yeniler.length === 0) return 0;

        if (userId) {
          // Buluta yaz, sonra buluttan oku — id'ler gerçek olsun
          (async () => {
            for (const p of yeniler) {
              await PresetService.savePreset(userId, {
                name: p.name,
                ecrn_list: p.ecrn_list ?? [],
                scrn_list: p.scrn_list ?? [],
                kayit_saati: p.kayit_saati ?? "",
                max_deneme: p.max_deneme ?? 60,
                retry_aralik: p.retry_aralik ?? 3.0,
              });
            }
            await refreshFromCloud(userId);
          })();
        } else {
          const eklenecek: Preset[] = yeniler.map((p) => ({
            id: crypto.randomUUID(),
            name: p.name,
            ecrn_list: p.ecrn_list ?? [],
            scrn_list: p.scrn_list ?? [],
            kayit_saati: p.kayit_saati ?? "",
            max_deneme: p.max_deneme ?? 60,
            retry_aralik: p.retry_aralik ?? 3.0,
            created_at: p.created_at ?? Date.now(),
          }));
          setPresets((prev) => {
            const next = [...prev, ...eklenecek];
            saveLocal(next);
            return next;
          });
        }
        return yeniler.length;
      } catch {
        return -1; // ayrıştırma hatası
      }
    },
    [presets, userId, refreshFromCloud],
  );

  return {
    presets,
    addPreset,
    deletePreset,
    updatePreset,
    exportPresets,
    importPresets,
  };
}
