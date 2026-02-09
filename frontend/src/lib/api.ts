const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Session ID (per-tab, sessionStorage persist) ──

function getSessionId(): string {
  if (typeof window === "undefined") return "ssr";
  let sid = sessionStorage.getItem("otostop_session_id");
  if (!sid) {
    sid = crypto.randomUUID();
    sessionStorage.setItem("otostop_session_id", sid);
  }
  return sid;
}

// ── Types ──

export interface ConfigData {
  token?: string; // undefined = mevcut token korunsun
  ecrn_list: string[];
  scrn_list: string[];
  kayit_saati: string;
  max_deneme: number;
  retry_aralik: number;
  gecikme_buffer: number;
  dry_run: boolean;
}

export interface ConfigResponse {
  ecrn_list: string[];
  scrn_list: string[];
  kayit_saati: string;
  max_deneme: number;
  retry_aralik: number;
  gecikme_buffer: number;
  token_set: boolean;
  token_preview: string;
  dry_run: boolean;
}

export interface CalibrationResult {
  server_offset_ms: number;
  rtt_one_way_ms: number;
  rtt_full_ms: number;
  ntp_offset_ms: number | null;
  server_ntp_diff_ms: number | null;
  accuracy_ms: number;
  source?: "manual" | "initial" | "auto" | "final";
}

export interface CRNResultItem {
  crn: string;
  status:
    | "pending"
    | "success"
    | "already"
    | "full"
    | "conflict"
    | "upgrade"
    | "debounce"
    | "error";
  message: string;
}

export interface RegistrationState {
  phase: "idle" | "calibrating" | "waiting" | "registering" | "done";
  running: boolean;
  current_attempt: number;
  max_attempts: number;
  crn_results: CRNResultItem[];
  calibration: CalibrationResult | null;
  countdown_seconds: number | null;
  trigger_time: number | null;
}

export interface TokenTestResult {
  valid: boolean;
  status_code: number;
  message: string;
}

export interface WSEvent {
  type:
    | "log"
    | "state"
    | "crn_update"
    | "calibration"
    | "countdown"
    | "done"
    | "pong";
  data: Record<string, unknown>;
  timestamp: number;
}

// ── OBS Course Types ──

export interface CourseSession {
  day: number; // 0=Pzt, 1=Sal, ..., 4=Cum
  start_time: string; // "08:30"
  end_time: string; // "11:29"
  room: string; // "A11"
  building: string; // "MED"
}

export interface CourseInfo {
  crn: string;
  course_code: string;
  course_name: string;
  instructor: string;
  teaching_method: string;
  capacity: number;
  enrolled: number;
  programmes: string;
  sessions: CourseSession[];
}

// ── API Functions ──

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Session-ID": getSessionId(),
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  health: () => fetchAPI<{ status: string }>("/api/health"),

  getConfig: () => fetchAPI<ConfigResponse>("/api/config"),

  setConfig: (config: ConfigData) =>
    fetchAPI<ConfigResponse>("/api/config", {
      method: "POST",
      body: JSON.stringify(config),
    }),

  testToken: () =>
    fetchAPI<TokenTestResult>("/api/test-token", { method: "POST" }),

  calibrate: () =>
    fetchAPI<CalibrationResult>("/api/calibrate", { method: "POST" }),

  startRegistration: () =>
    fetchAPI<{ status: string }>("/api/register/start", { method: "POST" }),

  cancelRegistration: () =>
    fetchAPI<{ status: string }>("/api/register/cancel", { method: "POST" }),

  resetRegistration: () =>
    fetchAPI<{ status: string }>("/api/register/reset", { method: "POST" }),

  getStatus: () => fetchAPI<RegistrationState>("/api/register/status"),

  // OBS Course Lookup
  lookupCRN: (crn: string) =>
    fetchAPI<CourseInfo>(`/api/crn-lookup/${crn}`).catch(() => null),

  lookupCRNs: (crns: string[]) =>
    fetchAPI<Record<string, CourseInfo | null>>("/api/crn-lookup", {
      method: "POST",
      body: JSON.stringify({ crns }),
    }),

  getDepartments: () =>
    fetchAPI<Array<{ bransKoduId: number; dersBransKodu: string }>>(
      "/api/departments",
    ),
};

// ── WebSocket ──

export function createWebSocket(): WebSocket {
  const wsUrl =
    API_BASE.replace("http", "ws") +
    `/ws?session_id=${encodeURIComponent(getSessionId())}`;
  return new WebSocket(wsUrl);
}
