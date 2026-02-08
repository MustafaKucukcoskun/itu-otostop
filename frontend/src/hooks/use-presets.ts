"use client";

import { useState, useCallback, useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { PresetService } from "@/lib/preset-service";

export interface Preset {
  id: string;
  name: string;
  ecrn_list: string[];
  scrn_list: string[];
  kayit_saati: string;
  max_deneme: number;
  retry_aralik: number;
  gecikme_buffer: number;
  created_at: number;
}

const STORAGE_KEY = "otostop-presets";

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
    /* localStorage full or unavailable */
  }
}

export function usePresets() {
  const { user } = useUser();
  const userId = user?.id ?? null;

  const [presets, setPresets] = useState<Preset[]>([]);
  const [cloudLoaded, setCloudLoaded] = useState(false);

  // Load presets — cloud if logged in, localStorage fallback
  useEffect(() => {
    if (userId && !cloudLoaded) {
      PresetService.getUserPresets(userId).then((cloud) => {
        if (cloud.length > 0) {
          setPresets(cloud);
          saveLocal(cloud); // keep local in sync
        } else {
          // First login: migrate localStorage presets to cloud
          const local = loadLocal();
          if (local.length > 0) {
            setPresets(local);
            // Upload each to cloud
            local.forEach((p) =>
              PresetService.savePreset(userId, {
                name: p.name,
                ecrn_list: p.ecrn_list,
                scrn_list: p.scrn_list,
                kayit_saati: p.kayit_saati,
                max_deneme: p.max_deneme,
                retry_aralik: p.retry_aralik,
                gecikme_buffer: p.gecikme_buffer,
              }),
            );
          } else {
            setPresets([]);
          }
        }
        setCloudLoaded(true);
      });
    } else if (!userId) {
      setPresets(loadLocal());
    }
  }, [userId, cloudLoaded]);

  const addPreset = useCallback(
    (
      name: string,
      config: Omit<Preset, "id" | "name" | "created_at">,
    ): Preset => {
      const preset: Preset = {
        ...config,
        id: crypto.randomUUID(),
        name,
        created_at: Date.now(),
      };
      const updated = [...presets, preset];
      saveLocal(updated);
      setPresets(updated);

      // Cloud sync
      if (userId) {
        PresetService.savePreset(userId, {
          name: preset.name,
          ecrn_list: preset.ecrn_list,
          scrn_list: preset.scrn_list,
          kayit_saati: preset.kayit_saati,
          max_deneme: preset.max_deneme,
          retry_aralik: preset.retry_aralik,
          gecikme_buffer: preset.gecikme_buffer,
        }).then((cloudId) => {
          if (cloudId) {
            // Update local preset with cloud UUID
            const withCloudId = updated.map((p) =>
              p.id === preset.id ? { ...p, id: cloudId } : p,
            );
            saveLocal(withCloudId);
            setPresets(withCloudId);
          }
        });
      }

      return preset;
    },
    [presets, userId],
  );

  const deletePreset = useCallback(
    (id: string) => {
      const updated = presets.filter((p) => p.id !== id);
      saveLocal(updated);
      setPresets(updated);

      // Cloud sync
      if (userId) {
        PresetService.deletePreset(userId, id);
      }
    },
    [presets, userId],
  );

  const updatePreset = useCallback(
    (id: string, config: Partial<Omit<Preset, "id" | "created_at">>) => {
      const updated = presets.map((p) =>
        p.id === id ? { ...p, ...config } : p,
      );
      saveLocal(updated);
      setPresets(updated);
    },
    [presets],
  );

  // Export presets as JSON string
  const exportPresets = useCallback((): string => {
    return JSON.stringify(presets, null, 2);
  }, [presets]);

  // Import presets from JSON string, returns count of imported
  const importPresets = useCallback(
    (json: string): number => {
      try {
        const parsed = JSON.parse(json);
        if (!Array.isArray(parsed)) return 0;
        const existingIds = new Set(presets.map((p) => p.id));
        const newPresets: Preset[] = [];
        for (const p of parsed) {
          if (
            p.id &&
            p.name &&
            Array.isArray(p.ecrn_list) &&
            !existingIds.has(p.id)
          ) {
            const preset: Preset = {
              id: p.id,
              name: p.name,
              ecrn_list: p.ecrn_list || [],
              scrn_list: p.scrn_list || [],
              kayit_saati: p.kayit_saati || "",
              max_deneme: p.max_deneme || 60,
              retry_aralik: p.retry_aralik || 3.0,
              gecikme_buffer: p.gecikme_buffer || 0.005,
              created_at: p.created_at || Date.now(),
            };
            newPresets.push(preset);

            // Cloud sync
            if (userId) {
              PresetService.savePreset(userId, {
                name: preset.name,
                ecrn_list: preset.ecrn_list,
                scrn_list: preset.scrn_list,
                kayit_saati: preset.kayit_saati,
                max_deneme: preset.max_deneme,
                retry_aralik: preset.retry_aralik,
                gecikme_buffer: preset.gecikme_buffer,
              });
            }
          }
        }
        if (newPresets.length === 0) return 0;
        const updated = [...presets, ...newPresets];
        saveLocal(updated);
        setPresets(updated);
        return newPresets.length;
      } catch {
        return -1; // parse error
      }
    },
    [presets, userId],
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
