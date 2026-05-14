import { copyFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";

const mode = process.argv[2] || "dev";
const passthroughArgs = process.argv.slice(3);
const viteBin = join(process.cwd(), "node_modules", "vite", "bin", "vite.js");

const env = { ...process.env };

if (process.platform === "win32") {
  const source = join(process.cwd(), "node_modules", "@esbuild", "win32-x64", "esbuild.exe");
  const target = join(tmpdir(), `esbuild-${process.pid}-${Date.now()}.exe`);
  if (existsSync(source)) {
    try {
      copyFileSync(source, target);
      env.ESBUILD_BINARY_PATH = target;
    } catch {
      // Fall back to node_modules binary if temp copy is blocked by endpoint protection.
      env.ESBUILD_BINARY_PATH = source;
    }
  }
}

const args = [viteBin];
if (mode !== "dev") {
  args.push(mode);
}
args.push(...passthroughArgs);

const result = spawnSync(process.execPath, args, {
  stdio: "inherit",
  env,
});

process.exit(result.status ?? 1);
