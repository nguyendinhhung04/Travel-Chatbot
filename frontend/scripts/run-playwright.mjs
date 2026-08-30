import { spawn, spawnSync } from "node:child_process";
import path from "node:path";
import process from "node:process";

const frontendRoot = process.cwd();
const baseUrl = "http://localhost:3100";
const nextCli = path.join(
  frontendRoot,
  "node_modules",
  "next",
  "dist",
  "bin",
  "next",
);
const playwrightCli = path.join(
  frontendRoot,
  "node_modules",
  "@playwright",
  "test",
  "cli.js",
);

async function serverIsReady() {
  try {
    const response = await fetch(baseUrl, { redirect: "manual" });
    return response.status >= 200 && response.status < 500;
  } catch {
    return false;
  }
}

async function waitForServer(server) {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    if (server.exitCode !== null) {
      throw new Error(`Next.js E2E server exited with code ${server.exitCode}.`);
    }
    if (await serverIsReady()) return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("Timed out waiting for the Next.js E2E server.");
}

function stopServer(server) {
  if (!server.pid || server.exitCode !== null) return;
  server.kill("SIGTERM");
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(server.pid), "/t", "/f"], {
      stdio: "ignore",
      timeout: 10_000,
      windowsHide: true,
    });
  }
  server.unref();
}

if (await serverIsReady()) {
  throw new Error(`${baseUrl} is already in use; stop that process and retry.`);
}

const server = spawn(process.execPath, [nextCli, "dev", "--port", "3100"], {
  cwd: frontendRoot,
  env: {
    ...process.env,
    NEXT_DIST_DIR: ".next-playwright",
    NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN: "",
  },
  stdio: ["ignore", "inherit", "inherit"],
  windowsHide: true,
});

let interrupted = false;
process.once("SIGINT", () => {
  interrupted = true;
  stopServer(server);
});

try {
  await waitForServer(server);
  const testRun = spawn(
    process.execPath,
    [playwrightCli, "test", "--project=msedge", ...process.argv.slice(2)],
    {
      cwd: frontendRoot,
      stdio: "inherit",
      windowsHide: true,
    },
  );
  const exitCode = await new Promise((resolve, reject) => {
    testRun.once("error", reject);
    testRun.once("exit", (code) => resolve(code ?? 1));
  });
  process.exitCode = interrupted ? 130 : exitCode;
} finally {
  stopServer(server);
  process.exit(process.exitCode ?? 1);
}
