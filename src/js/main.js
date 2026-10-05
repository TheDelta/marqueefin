// The page's script, bundled by esbuild (npm run build). A page protected by a
// passphrase is opened first (unlock.js); only then is app.js loaded, whose modules
// read the page's data. esbuild keeps the dynamic import in the same file and runs
import { unlock } from "./unlock.js";

await unlock();
await import("./app.js");
