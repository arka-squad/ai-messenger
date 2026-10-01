import { readFileSync, readdirSync } from "node:fs";
import { extname, join } from "node:path";

const roots = ["src", "src-tauri/src", "scripts"];
const extensions = new Set([".css", ".html", ".js", ".rs"]);
const files = [];

const walk = (directory) => {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) walk(path);
    else if (extensions.has(extname(path))) files.push(path);
  }
};

roots.forEach(walk);
const oversized = files
  .map((path) => [path, readFileSync(path, "utf8").split("\n").length])
  .filter(([, lines]) => lines > 700);
if (oversized.length) {
  throw new Error(`700-line limit exceeded:\n${oversized.map(([path, lines]) => `${path}: ${lines}`).join("\n")}`);
}

const application = [
  "src-tauri/src/mailbox.rs",
  "src-tauri/src/domain.rs",
  "src-tauri/src/domain/models.rs",
  "src-tauri/src/domain/ports.rs",
].map((path) => readFileSync(path, "utf8").split("#[cfg(test)]")[0]).join("\n");
if (/(?:crate::(?:exchange|storage)|\b(?:exchange|storage)::)/.test(application)) {
  throw new Error("Application/domain layers must not import concrete adapters");
}

for (const path of ["src-tauri/src/exchange.rs", "src-tauri/src/storage.rs"]) {
  if (/crate::mailbox/.test(readFileSync(path, "utf8"))) {
    throw new Error(`${path} must not import the application service`);
  }
}

console.log(`Architecture: ${files.length} files <= 700 lines, dependency direction valid`);
