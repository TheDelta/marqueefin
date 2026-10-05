// "New since your last visit": {at, items: {id: latest change}}; moves on only with
// "Mark all as seen". New episodes and new collection members count as changes.
import { DATA } from "./dom.js";
import { changed } from "./lib.js";
import { SEEN, load, save } from "./store.js";

const snapshot = () => ({
  at: new Date().toISOString(),
  items: Object.fromEntries(DATA.map((d) => [d.id, changed(d)])),
});
let seen;
try {
  seen = JSON.parse(load(SEEN) || "null");
} catch {
  seen = null;
}
if (!seen?.items) {
  seen = snapshot();
  save(SEEN, JSON.stringify(seen));
}

export const isNew = (d) => seen.items[d.id] !== changed(d);
export const seenSince = () => seen.at;
export function markAllSeen() {
  seen = snapshot();
  save(SEEN, JSON.stringify(seen));
}
