"use client";

import { useState, useRef } from "react";
import { m, AnimatePresence } from "motion/react";
import {
  Plus,
  X,
  Trash2,
  Download,
  Upload,
  Share2,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";
import { PanelHeader } from "@/components/panel";
import { usePresets, type Preset } from "@/hooks/use-presets";

interface PresetManagerProps {
  currentConfig: {
    ecrn_list: string[];
    scrn_list: string[];
    kayit_saati: string;
    max_deneme: number;
    retry_aralik: number;
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
    <div>
      <PanelHeader
        label="Ders Şablonları"
        action={
          presets.length > 0 && (
            <button
              onClick={handleExport}
              className="flex h-7 w-7 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
              title="Şablonları dışa aktar (JSON)"
            >
              <Share2 className="h-3.5 w-3.5" />
            </button>
          )
        }
      />

      <div className="space-y-3 p-4">
        <p className="text-[11px] text-muted-foreground">
          CRN ve ayarlarını kaydet, sonraki dönem hızlıca yükle
        </p>
        {/* Save / Import actions */}
        <div className="flex gap-2">
          {!saving ? (
            <>
              <button
                onClick={() => setSaving(true)}
                disabled={disabled}
                className="flex flex-1 items-center justify-center gap-2 border py-2 text-sm font-medium transition-colors hover:bg-accent disabled:opacity-40"
              >
                <Plus className="h-3.5 w-3.5" />
                Mevcut Ayarları Kaydet
              </button>
              <button
                onClick={() => importRef.current?.click()}
                disabled={disabled}
                className="flex h-9 items-center border px-3 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-40"
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
            <m.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex w-full gap-2"
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
                className="h-9 flex-1 border bg-background px-3 text-sm transition-colors focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              />
              <button
                onClick={handleSave}
                className="h-9 bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Kaydet
              </button>
              <button
                onClick={() => setSaving(false)}
                className="flex h-9 w-9 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
                aria-label="Vazgeç"
              >
                <X className="h-4 w-4" />
              </button>
            </m.div>
          )}
        </div>

        {/* Preset list */}
        <div className="space-y-1.5">
          <AnimatePresence mode="popLayout">
            {presets.map((preset) => (
              <m.div
                key={preset.id}
                layout
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: 30, scale: 0.95 }}
                onClick={() => !disabled && handleLoadClick(preset)}
                role="button"
                tabIndex={disabled ? -1 : 0}
                aria-disabled={disabled}
                className="group flex w-full cursor-pointer items-center justify-between border px-3.5 py-2.5 text-left transition-colors hover:border-primary hover:bg-accent/40 aria-disabled:opacity-40"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <Download className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {preset.name}
                    </p>
                    <p className="truncate text-[10px] text-muted-foreground">
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
                  className="flex h-6 w-6 shrink-0 items-center justify-center text-muted-foreground opacity-0 transition-all hover:text-[--status-err] group-hover:opacity-100"
                  aria-label="Şablonu sil"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </m.div>
            ))}
          </AnimatePresence>

          {presets.length === 0 && (
            <p className="py-4 text-center text-xs text-muted-foreground">
              Henüz şablon kaydedilmedi
            </p>
          )}
        </div>

        {/* Data persistence notice */}
        <p className="pt-1 text-center text-[9px] text-muted-foreground/60">
          Şablonlar hesabına bağlı olarak bulutta saklanır.
        </p>
      </div>

      {/* Confirmation dialog overlay */}
      <AnimatePresence>
        {confirmLoad && (
          <m.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/55 p-4"
            onClick={() => setConfirmLoad(null)}
          >
            <m.div
              initial={{ scale: 0.96, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.96, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-sm space-y-4 border bg-popover p-6"
            >
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-[--status-wait]" />
                <div>
                  <p className="text-sm font-semibold">Şablon Yükle</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    &ldquo;{confirmLoad.name}&rdquo; yüklemek mevcut CRN listeni
                    ve tüm ayarlarını değiştirecek.
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setConfirmLoad(null)}
                  className="h-9 flex-1 border text-sm font-medium transition-colors hover:bg-accent"
                >
                  Vazgeç
                </button>
                <button
                  onClick={() => doLoad(confirmLoad)}
                  className="h-9 flex-1 bg-primary text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  Yükle
                </button>
              </div>
            </m.div>
          </m.div>
        )}
      </AnimatePresence>
    </div>
  );
}
