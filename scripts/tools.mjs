// npm tools from node_modules (run with this Node), Python tools from .venv, else PATH
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

export const root = path.resolve(import.meta.dirname, "..");
const win = process.platform === "win32";

/** A Python tool's executable: .venv first, then PATH. */
export function pyTool(name) {
  const local = path.join(root, ".venv", win ? "Scripts" : "bin", win ? `${name}.exe` : name);
  return existsSync(local) ? local : name;
}

/** [node, script] for an npm package's command, e.g. nodeTool("prettier"). */
export function nodeTool(pkg, bin = pkg.split("/").pop()) {
  const dir = path.join(root, "node_modules", pkg);
  const manifest = JSON.parse(readFileSync(path.join(dir, "package.json"), "utf8"));
  const rel = typeof manifest.bin === "string" ? manifest.bin : manifest.bin[bin];
  return [process.execPath, path.join(dir, rel)];
}
