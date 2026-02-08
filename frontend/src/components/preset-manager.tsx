"use client";

import { useState, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  BookmarkPlus,
  Plus,
  Trash2,
  Download,
  Upload,
  Share2,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";
import { useUser } from "@clerk/nextjs";
import { usePresets, type Preset } from "@/hooks/use-presets";

interface PresetManagerProps {
  currentConfig: {
    ecrn_list: string[];
    scrn_list: string[];
    kayit_saati: string;
    max_deneme: number;
    retry_aralik: number;
    gecikme_buffer: number;
  };
  onLoadPreset: (preset: Preset) => void;
  courseLabels?: Record<string, string>; // crn → course_code map
  disabled?: boolean;
}

export function PresetManager({
  currentConfig,
  onLoadPreset,
  courseLabels = {},
  disabled,
}: PresetManagerProps) {
  const { presets, addPreset, deletePreset, exportPresets, importPresets } =
    usePresets();
  const { user } = useUser();
  const isLoggedIn = !!user;
  const [saving, setSaving] = useState(false);
  const [newName, setNewName] = useState("");
  const [confirmLoad, setConfirmLoad] = useState<Preset | null>(null);
  const importRef = useRef<HTMLInputElement>(null);

  const handleSave = () => {
    const trimmed = newName.trim();
    if (!trimmed) {
      toast.error("Şablon adı girin");
      return;
    }
    addPreset(trimmed, currentConfig);
    setNewName("");
    setSaving(false);
    toast.success(`"${trimmed}" kaydedildi`);
  };

  const handleLoadClick = (preset: Preset) => {
    // If user has CRNs, show confirmation
    if (
      currentConfig.ecrn_list.length > 0 ||
      currentConfig.scrn_list.length > 0
    ) {
      setConfirmLoad(preset);
    } else {
      doLoad(preset);
    }
  };

  const doLoad = (preset: Preset) => {
    onLoadPreset(preset);
    setConfirmLoad(null);
    toast.success(`"${preset.name}" yüklendi`);
  };

  const handleDelete = (e: React.MouseEvent, preset: Preset) => {
    e.stopPropagation();
    deletePreset(preset.id);
    toast.info(`"${preset.name}" silindi`);
  };

  const handleExport = () => {
    const json = exportPresets();
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `otostop-sablonlar-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Şablonlar indirildi");
  };

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      const count = importPresets(text);
      if (count === -1) {
        toast.error("Geçersiz dosya formatı");
      } else if (count === 0) {
        toast.info("İçe aktarılacak yeni şablon bulunamadı");
      } else {
        toast.success(`${count} şablon içe aktarıldı`);
      }
    };
    reader.readAsText(file);
    // Reset input so the same file can be imported again
    e.target.value = "";
  };

  // Helper: show course codes for a preset's CRN list
  const crnSummary = (crns: string[]) => {
    const codes = crns
      .slice(0, 4)
      .map((crn) => courseLabels[crn] || crn)
      .join(", ");
    return crns.length > 4 ? `${codes} +${crns.length - 4}` : codes;
  };

  return (
    <div className="overflow-hidden">
      {/* Header — always visible */}
      <div className="flex items-center justify-between px-5 pt-5 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-orange-500/10 flex items-center justify-center">
            <BookmarkPlus className="h-4 w-4 text-orange-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold">Ders Şablonları</h3>
            <p className="text-[10px] text-muted-foreground">
              CRN ve ayarlarını kaydet, sonraki dönem hızlıca yükle
            </p>
          </div>
        </div>
        {presets.length > 0 && (
          <div className="flex items-center gap-1">
            <button
              onClick={handleExport}
              className="h-7 w-7 rounded-lg flex items-center justify-center text-muted-foreground/50 hover:text-foreground hover:bg-muted/40 transition-colors"
              title="Şablonları dışa aktar (JSON)"
            >
              <Share2 className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      <div className="px-5 pb-5 space-y-3">
        {/* Save / Import actions */}
        <div className="flex gap-2">
          {!saving ? (
            <>
              <button
                onClick={() => setSaving(true)}
                disabled={disabled}
                className="flex-1 flex items-center justify-center gap-2 py-2 rounded-xl ring-1 ring-border/30 bg-background/40 hover:bg-muted/40 text-sm font-medium transition-colors disabled:opacity-40"
              >
                <Plus className="h-3.5 w-3.5" />
                Mevcut Ayarları Kaydet
              </button>
              <button
                onClick={() => importRef.current?.click()}
                disabled={disabled}
                className="h-9 px-3 rounded-xl ring-1 ring-border/30 bg-background/40 hover:bg-muted/40 text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
                title="Şablon dosyası içe aktar"
              >
                <Upload className="h-3.5 w-3.5" />
              </button>
              <input
                ref={importRef}
                type="file"
                accept=".json"
                onChange={handleImport}
                className="hidden"
              />
            </>
          ) : (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-2 w-full"
            >
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSave();
                  if (e.key === "Escape") setSaving(false);
                }}
                placeholder="Şablon adı (ör: Güz 2026)"
                autoFocus
                className="flex-1 h-9 rounded-xl bg-background/60 ring-1 ring-border/30 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 transition-shadow"
              />
              <button
                onClick={handleSave}
                className="h-9 px-4 rounded-xl bg-primary/15 text-primary text-sm font-medium hover:bg-primary/25 transition-colors"
              >
                Kaydet
              </button>
              <button
                onClick={() => setSaving(false)}
                className="h-9 px-2 rounded-xl text-muted-foreground hover:text-foreground transition-colors text-sm"
              >
                ✕
              </button>
            </motion.div>
          )}
        </div>

        {/* Preset list */}
        <div className="space-y-1.5">
          <AnimatePresence mode="popLayout">
            {presets.map((preset) => (
              <motion.div
                key={preset.id}
                layout
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: 30, scale: 0.95 }}
                onClick={() => !disabled && handleLoadClick(preset)}
                role="button"
                tabIndex={disabled ? -1 : 0}
                aria-disabled={disabled}
                className="w-full flex items-center justify-between py-2.5 px-3.5 rounded-xl bg-background/40 ring-1 ring-border/20 hover:ring-primary/30 hover:bg-muted/30 group transition-all aria-disabled:opacity-40 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Download className="h-3.5 w-3.5 text-muted-foreground shrink-0 group-hover:text-primary transition-colors" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">
                      {preset.name}
                    </p>
                    <p className="text-[10px] text-muted-foreground truncate">
                      {crnSummary(preset.ecrn_list)}
                      {preset.kayit_saati &&
                        ` · ${preset.kayit_saati.slice(0, 5)}`}
                      {preset.scrn_list.length > 0 &&
                        ` · ${preset.scrn_list.length} bırak`}
                    </p>
                  </div>
                </div>
                <button
                  onClick={(e) => handleDelete(e, preset)}
                  className="h-6 w-6 rounded-lg flex items-center justify-center text-muted-foreground/40 hover:text-red-400 hover:bg-red-400/10 opacity-0 group-hover:opacity-100 transition-all shrink-0"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>

          {presets.length === 0 && (
            <p className="text-center py-4 text-muted-foreground/40 text-xs">
              Henüz şablon kaydedilmedi
            </p>
          )}
        </div>

        {/* Data persistence notice */}
        <p className="text-[9px] text-muted-foreground/30 text-center pt-1">
          {isLoggedIn
            ? "Şablonlar hesabına bağlı olarak bulutta saklanır."
            : "Şablonlar bu tarayıcıda saklanır. Giriş yapılarak bulut senkronizasyonu aktif edilebilir."}
        </p>
      </div>

      {/* Confirmation dialog overlay */}
      <AnimatePresence>
        {confirmLoad && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm"
            onClick={() => setConfirmLoad(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="rounded-2xl p-6 mx-4 max-w-sm w-full space-y-4 ring-1 ring-border/30 shadow-2xl bg-zinc-900/95 backdrop-blur-xl"
            >
              <div className="flex items-start gap-3">
                <div className="h-9 w-9 rounded-lg bg-amber-500/10 flex items-center justify-center shrink-0 mt-0.5">
                  <AlertTriangle className="h-4.5 w-4.5 text-amber-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold">Şablon Yükle</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    &ldquo;{confirmLoad.name}&rdquo; yüklemek mevcut CRN listeni
                    ve tüm ayarlarını değiştirecek.
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setConfirmLoad(null)}
                  className="flex-1 h-9 rounded-xl ring-1 ring-border/30 bg-background/40 text-sm font-medium hover:bg-muted/40 transition-colors"
                >
                  Vazgeç
                </button>
                <button
                  onClick={() => doLoad(confirmLoad)}
                  className="flex-1 h-9 rounded-xl bg-primary/15 text-primary text-sm font-medium hover:bg-primary/25 transition-colors"
                >
                  Yükle
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
