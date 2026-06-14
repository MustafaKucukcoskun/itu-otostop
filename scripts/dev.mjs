/**
 * İTÜ Otostop — Dev Orchestrator
 *
 * Root dizinde `npm run dev` ile hem backend hem frontend'i
 * tek seferde ayağa kaldırır. Her iki process'in stdout/stderr'i
 * renkli prefix ile terminale basılır.
 *
 * - Backend:  python main.py  → http://localhost:8000
 * - Frontend: npm run dev     → http://localhost:3000
 *   (NEXT_PUBLIC_API_URL otomatik olarak localhost:8000'e ayarlanır)
 */

import { spawn } from "node:child_process";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

// ── ANSI Colors ──
const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";
const DIM = "\x1b[2m";
const CYAN = "\x1b[36m";
const YELLOW = "\x1b[33m";
const GREEN = "\x1b[32m";
const RED = "\x1b[31m";
const MAGENTA = "\x1b[35m";

const BACKEND_PREFIX = `${BOLD}${CYAN}[backend]${RESET} `;
const FRONTEND_PREFIX = `${BOLD}${YELLOW}[frontend]${RESET}`;

// ── Banner ──
console.log(`
${BOLD}${GREEN}  ╔══════════════════════════════════════╗
  ║     🚗  İTÜ Otostop — Dev Mode       ║
  ╚══════════════════════════════════════╝${RESET}
${DIM}  Backend:   http://localhost:8000
  Frontend:  http://localhost:3000
  API Docs:  http://localhost:8000/docs${RESET}
`);

// ── Helper: prefix each line of output ──
function prefixStream(stream, prefix) {
  let buffer = "";
  stream.on("data", (chunk) => {
    buffer += chunk.toString();
    const lines = buffer.split("\n");
    // Keep last incomplete line in buffer
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) {
        console.log(`${prefix} ${line}`);
      }
    }
  });
  stream.on("end", () => {
    if (buffer.trim()) {
      console.log(`${prefix} ${buffer}`);
    }
  });
}

// ── Detect Python command ──
import { execSync } from "node:child_process";
import { existsSync } from "node:fs";

function getPythonCmd() {
  // 1) backend/venv içindeki Python'ı tercih et — bağımlılıklar (fastapi vb.) burada kurulu.
  //    Yol backend cwd'sine göre göreli döndürülür (spawn cwd: backend ile çalışır).
  const venvRel =
    process.platform === "win32"
      ? "venv\\Scripts\\python.exe"
      : "venv/bin/python";
  if (existsSync(resolve(ROOT, "backend", venvRel))) {
    return venvRel;
  }

  // 2) venv yoksa sistem Python'ına düş.
  //    Windows: 'py' (Python Launcher) → 'python' → 'python3'
  //    Unix: 'python3' → 'python'
  const candidates =
    process.platform === "win32"
      ? ["py", "python", "python3"]
      : ["python3", "python"];

  for (const cmd of candidates) {
    try {
      execSync(`${cmd} --version`, { stdio: "ignore" });
      return cmd;
    } catch {
      // not found, try next
    }
  }
  // fallback
  return candidates[0];
}

const pythonCmd = getPythonCmd();
console.log(`${DIM}  Python:    ${pythonCmd}${RESET}\n`);

// ── Start Backend (FastAPI) ──
const backend = spawn(pythonCmd, ["main.py"], {
  cwd: resolve(ROOT, "backend"),
  stdio: ["ignore", "pipe", "pipe"],
  env: { ...process.env },
  shell: true,
});

prefixStream(backend.stdout, BACKEND_PREFIX);
prefixStream(backend.stderr, BACKEND_PREFIX);

backend.on("error", (err) => {
  console.error(`${RED}${BOLD}[backend] Failed to start: ${err.message}${RESET}`);
  console.error(`${DIM}  Make sure Python 3.11+ is installed and dependencies are set up:${RESET}`);
  console.error(`${DIM}  cd backend && pip install -r requirements.txt${RESET}`);
});

backend.on("exit", (code) => {
  if (code !== null && code !== 0) {
    console.error(`${RED}${BOLD}[backend] Exited with code ${code}${RESET}`);
  }
});

// ── Wait a moment for backend to initialize, then start Frontend ──
setTimeout(() => {
  console.log(`${MAGENTA}${BOLD}  → Starting frontend...${RESET}\n`);

  const frontend = spawn("npm", ["run", "dev"], {
    cwd: resolve(ROOT, "frontend"),
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      // Dev ortamında frontend'i local backend'e yönlendir
      NEXT_PUBLIC_API_URL: "http://localhost:8000",
    },
    shell: true,
  });

  prefixStream(frontend.stdout, FRONTEND_PREFIX);
  prefixStream(frontend.stderr, FRONTEND_PREFIX);

  frontend.on("error", (err) => {
    console.error(`${RED}${BOLD}[frontend] Failed to start: ${err.message}${RESET}`);
    console.error(`${DIM}  Make sure Node.js 18+ is installed and dependencies are set up:${RESET}`);
    console.error(`${DIM}  cd frontend && npm install${RESET}`);
  });

  frontend.on("exit", (code) => {
    if (code !== null && code !== 0) {
      console.error(`${RED}${BOLD}[frontend] Exited with code ${code}${RESET}`);
    }
    // Frontend kapandıysa backend'i de kapat
    backend.kill();
    process.exit(code || 0);
  });

  // ── Graceful shutdown ──
  const cleanup = () => {
    console.log(`\n${DIM}  Shutting down...${RESET}`);
    frontend.kill();
    backend.kill();
    // Give processes time to cleanup
    setTimeout(() => process.exit(0), 1000);
  };

  process.on("SIGINT", cleanup);
  process.on("SIGTERM", cleanup);

}, 1500);

// Eğer sadece backend başlatıldıysa, Ctrl+C ile temiz çıkış
process.on("SIGINT", () => {
  backend.kill();
  process.exit(0);
});
