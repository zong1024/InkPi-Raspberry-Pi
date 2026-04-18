import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDir, "..");
const staticDir = path.join(projectRoot, "web_ui", "static");
const indexPath = path.join(staticDir, "index.html");

if (!fs.existsSync(indexPath)) {
  throw new Error(`Missing built index file: ${indexPath}`);
}

const indexHtml = fs.readFileSync(indexPath, "utf8");
if (!indexHtml.includes('<div id="root"></div>')) {
  throw new Error("Built index.html does not contain the expected React root node.");
}

const assetRefs = [...indexHtml.matchAll(/(?:src|href)="([^"]+)"/g)]
  .map((match) => match[1])
  .filter((ref) => ref.startsWith("/static/"));

if (!assetRefs.length) {
  throw new Error("No bundled /static asset references were found in web_ui/static/index.html.");
}

for (const ref of assetRefs) {
  const relativePath = ref.replace(/^\/static\//, "");
  const absolutePath = path.join(staticDir, relativePath);
  if (!fs.existsSync(absolutePath)) {
    throw new Error(`Missing bundled asset referenced by index.html: ${ref}`);
  }
}

console.log(`Verified ${assetRefs.length} bundled asset reference(s) in ${indexPath}.`);
