"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Search, Loader2, Plus, ArrowLeft, Check } from "lucide-react";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { CourseInfo } from "@/lib/api";
import { DAY_SHORT } from "./schedule-builder";

interface DepartmentItem {
  bransKoduId: number;
  dersBransKodu: string;
}

interface CourseSearchProps {
  departments: DepartmentItem[];
  departmentsLoading: boolean;
  selectedCRNs: Set<string>;
  onAdd: (course: CourseInfo) => void;
}

/**
 * Kullanıcının yazdığını anlayan tek arama kutusu.
 *
 * Eski akış beş kademeliydi (alan seç → modal aç → kod öneki → ders kodu → section)
 * ve ilk kademe her zaman tek seçenek gösteriyordu, çünkü "ders alanı" zaten kod
 * önekinin kendisi. Burada önek sorgudan çıkarılıyor, o kademe tamamen kalkıyor.
 *
 * Sonuç hacmi alana göre uçuk değişiyor (AKM 4 section, ING 208). Bu yüzden
 * sorgu belirsizse ders KODLARI, belirginse SECTION'lar gösteriliyor.
 */

type Parsed =
  | { kind: "empty" }
  | { kind: "crn"; crn: string }
  | { kind: "code"; dept: string; num: string }
  | { kind: "dept"; dept: string }
  | { kind: "unknown" };

function parseQuery(raw: string): Parsed {
  const s = raw.trim().toUpperCase().replace(/\s+/g, " ");
  if (!s) return { kind: "empty" };
  if (/^\d{5}$/.test(s)) return { kind: "crn", crn: s };
  const m = s.match(/^([A-Z]{2,4}) ?([0-9]{1,3}[A-Z]?)$/);
  if (m) return { kind: "code", dept: m[1], num: m[2] };
  if (/^[A-Z]{2,4}$/.test(s)) return { kind: "dept", dept: s };
  return { kind: "unknown" };
}

const norm = (s: string) => s.toUpperCase().replace(/\s+/g, " ").trim();

type Result =
  | { kind: "none" }
  | { kind: "sections"; heading: string; sections: CourseInfo[] }
  | {
      kind: "codes";
      heading: string;
      codes: { code: string; name: string; count: number }[];
    };

export function CourseSearch({
  departments,
  departmentsLoading,
  selectedCRNs,
  onAdd,
}: CourseSearchProps) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Result>({ kind: "none" });
  const [message, setMessage] = useState<string | null>(null);

  // Bölüm bazında ders önbelleği — aynı alan tekrar sorgulanmasın
  const cacheRef = useRef<Map<number, CourseInfo[]>>(new Map());
  // Yarış koşulu koruması: geç dönen eski istek yeni sonucu ezmesin
  const runIdRef = useRef(0);

  const deptIndex = useMemo(() => {
    const m = new Map<string, DepartmentItem>();
    for (const d of departments) m.set(norm(d.dersBransKodu), d);
    return m;
  }, [departments]);

  const loadCourses = useCallback(async (dept: DepartmentItem) => {
    const hit = cacheRef.current.get(dept.bransKoduId);
    if (hit) return hit;
    const list = await api.getCourses(dept.bransKoduId);
    cacheRef.current.set(dept.bransKoduId, list);
    return list;
  }, []);

  const showCode = useCallback(
    async (dept: DepartmentItem, courseCode: string) => {
      const id = ++runIdRef.current;
      setLoading(true);
      setMessage(null);
      try {
        const all = await loadCourses(dept);
        if (runIdRef.current !== id) return;
        const sections = all.filter(
          (c) => norm(c.course_code) === norm(courseCode),
        );
        setResult({ kind: "sections", heading: courseCode, sections });
      } catch {
        if (runIdRef.current === id) setMessage("Ders bilgisi alınamadı");
      } finally {
        if (runIdRef.current === id) setLoading(false);
      }
    },
    [loadCourses],
  );

  useEffect(() => {
    const parsed = parseQuery(query);
    if (parsed.kind === "empty") {
      runIdRef.current++;
      setResult({ kind: "none" });
      setMessage(null);
      setLoading(false);
      return;
    }

    const id = ++runIdRef.current;
    const timer = setTimeout(async () => {
      setLoading(true);
      setMessage(null);
      try {
        if (parsed.kind === "crn") {
          const course = await api.lookupCRN(parsed.crn);
          if (runIdRef.current !== id) return;
          setResult({
            kind: "sections",
            heading: `CRN ${parsed.crn}`,
            sections: course ? [course] : [],
          });
          if (!course) setMessage(`CRN ${parsed.crn} bulunamadı`);
          return;
        }

        const deptCode = parsed.kind === "unknown" ? "" : parsed.dept;
        const dept = deptIndex.get(norm(deptCode));
        if (!dept) {
          if (runIdRef.current !== id) return;
          setResult({ kind: "none" });
          setMessage(
            parsed.kind === "unknown"
              ? "Anlaşılmadı — CRN (5 hane), ders kodu (MAT 103) veya alan (MAT) yaz"
              : `"${deptCode}" diye bir ders alanı yok`,
          );
          return;
        }

        const all = await loadCourses(dept);
        if (runIdRef.current !== id) return;

        if (parsed.kind === "code") {
          const target = norm(`${parsed.dept} ${parsed.num}`);
          let sections = all.filter((c) => norm(c.course_code) === target);
          // Tam eşleşme yoksa önek ile devam et: "MAT 10" → MAT 101, MAT 103…
          if (sections.length === 0) {
            sections = all.filter((c) => norm(c.course_code).startsWith(target));
          }
          setResult({
            kind: "sections",
            heading: `${parsed.dept} ${parsed.num}`,
            sections,
          });
          if (sections.length === 0) setMessage("Bu kodla ders bulunamadı");
          return;
        }

        // Yalnızca alan yazıldı → ders kodlarını göster (section değil).
        // ING gibi alanlarda 200+ section var; kod listesi 12-85 arası kalıyor.
        const byCode = new Map<string, { name: string; count: number }>();
        for (const c of all) {
          const k = norm(c.course_code);
          const prev = byCode.get(k);
          if (prev) prev.count += 1;
          else byCode.set(k, { name: c.course_name, count: 1 });
        }
        const codes = [...byCode.entries()]
          .map(([code, v]) => ({ code, name: v.name, count: v.count }))
          .sort((a, b) => a.code.localeCompare(b.code, "tr"));
        setResult({ kind: "codes", heading: dept.dersBransKodu, codes });
        if (codes.length === 0) setMessage("Bu alanda ders bulunamadı");
      } catch {
        if (runIdRef.current === id) setMessage("Arama başarısız — tekrar dene");
      } finally {
        if (runIdRef.current === id) setLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query, deptIndex, loadCourses]);

  const activeDept =
    result.kind === "codes" ? deptIndex.get(norm(result.heading)) : undefined;

  return (
    <div className="border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <p className="panel-label">Ders Ekle</p>
      </div>

      <div className="px-4 py-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="CRN, ders kodu veya alan ara…"
            aria-label="Ders ara: CRN, ders kodu veya ders alanı"
            className="pl-9 font-mono"
            autoComplete="off"
            spellCheck={false}
          />
          {loading && (
            <Loader2 className="absolute right-3 top-1/2 size-4 -translate-y-1/2 animate-spin text-muted-foreground" />
          )}
        </div>
        <p className="mt-2 font-mono text-[10px] tracking-wide text-muted-foreground/70">
          örn. 15261 · MAT 103 · BLG
        </p>
      </div>

      {departmentsLoading && (
        <p className="border-t border-border px-4 py-3 text-xs text-muted-foreground">
          Ders alanları yükleniyor…
        </p>
      )}

      {/* GÖZAT — kutu boşken tüm ders alanları listelenir.
          Kodu bilen yazıp geçer; bilmeyen buradan keşfeder. Arama kutusunu
          zorunlu kılmak, kod ezberlemeyen öğrenciyi çıkmaza sokuyordu. */}
      {!departmentsLoading && query.trim() === "" && departments.length > 0 && (
        <div className="border-t border-border">
          <p className="px-4 py-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            Gözat · {departments.length} ders alanı
          </p>
          <div className="max-h-[24rem] overflow-y-auto">
            <div className="grid grid-cols-3 gap-px bg-border">
              {departments.map((d) => (
                <button
                  key={d.bransKoduId}
                  onClick={() => setQuery(d.dersBransKodu)}
                  className="bg-card px-2 py-2.5 font-mono text-xs text-foreground transition-colors hover:bg-primary hover:text-primary-foreground"
                >
                  {d.dersBransKodu}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {message && (
        <p className="border-t border-border px-4 py-3 text-xs text-muted-foreground">
          {message}
        </p>
      )}

      {/* Ders kodu listesi — alan yazıldığında */}
      {result.kind === "codes" && result.codes.length > 0 && (
        <div className="border-t border-border">
          <p className="px-4 py-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            {result.heading} · {result.codes.length} ders
          </p>
          <div className="max-h-[22rem] overflow-y-auto">
            {result.codes.map((c) => (
              <button
                key={c.code}
                onClick={() => activeDept && showCode(activeDept, c.code)}
                className="flex w-full items-baseline gap-2 border-t border-border px-4 py-2.5 text-left transition-colors hover:bg-muted/50"
              >
                <span className="font-mono text-xs font-semibold text-primary">
                  {c.code}
                </span>
                <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                  {c.name}
                </span>
                <span className="shrink-0 font-mono text-[10px] text-muted-foreground/70">
                  {c.count}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Section listesi — ders kodu belirginleştiğinde */}
      {result.kind === "sections" && result.sections.length > 0 && (
        <div className="border-t border-border">
          <div className="flex items-center gap-2 px-4 py-2">
            {activeDeptBackVisible(query) && (
              <button
                onClick={() => setQuery(query.trim().split(/\s+/)[0] ?? "")}
                className="text-muted-foreground transition-colors hover:text-foreground"
                aria-label="Ders listesine dön"
              >
                <ArrowLeft className="size-3.5" />
              </button>
            )}
            <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              {result.heading} · {result.sections.length} CRN
            </p>
          </div>
          <div className="max-h-[26rem] overflow-y-auto">
            {result.sections.map((c) => {
              const added = selectedCRNs.has(c.crn);
              const full = c.capacity > 0 && c.enrolled >= c.capacity;
              return (
                <div
                  key={c.crn}
                  className="border-t border-border px-4 py-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-baseline gap-2">
                        <span className="font-mono text-[10px] text-muted-foreground">
                          CRN
                        </span>
                        <span className="font-mono text-xs font-semibold">
                          {c.crn}
                        </span>
                      </div>
                      <p className="mt-0.5 truncate text-xs text-foreground">
                        {c.course_code} · {c.course_name}
                      </p>
                    </div>
                    <button
                      onClick={() => onAdd(c)}
                      disabled={added}
                      className="flex shrink-0 items-center gap-1 border border-primary px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-primary transition-colors hover:bg-primary hover:text-primary-foreground disabled:border-border disabled:text-muted-foreground disabled:hover:bg-transparent disabled:hover:text-muted-foreground"
                      aria-label={`${c.course_code} CRN ${c.crn} ekle`}
                    >
                      {added ? (
                        <>
                          <Check className="size-3" /> Ekli
                        </>
                      ) : (
                        <>
                          <Plus className="size-3" /> Ekle
                        </>
                      )}
                    </button>
                  </div>

                  <p className="mt-1.5 truncate text-xs text-muted-foreground">
                    {c.instructor || "—"}
                  </p>

                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] text-muted-foreground">
                    {c.sessions.map((s, i) => (
                      <span key={i}>
                        {DAY_SHORT[s.day]} {s.start_time}–{s.end_time}
                        {s.room && s.room.replace(/-/g, "").trim()
                          ? ` · ${s.room}`
                          : ""}
                      </span>
                    ))}
                    <span className={full ? "text-status-err" : "text-status-ok"}>
                      {c.enrolled}/{c.capacity}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/** "MAT 103" gibi iki parçalı sorguda alan listesine dönüş oku gösterilir */
function activeDeptBackVisible(query: string): boolean {
  return /\s|[A-Za-z]{2,4}[0-9]/.test(query.trim());
}
