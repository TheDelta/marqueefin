// Per-viewer settings and marks: kept in this browser only
export const STORE = "marqueefin:marks",
  MYRATE = "marqueefin:myratings",
  SEEN = "marqueefin:seen",
  FMT = "marqueefin:format",
  NOIDS = "marqueefin:noids",
  WANTED = "marqueefin:onlywanted",
  GROUP = "marqueefin:group",
  SPLIT = "marqueefin:split",
  RATINGS = "marqueefin:ratings",
  STATUS = "marqueefin:status",
  QUALITY = "marqueefin:quality",
  ALT = "marqueefin:alttitles",
  THEME = "marqueefin:theme",
  LANG = "marqueefin:lang",
  KEY = "marqueefin:key"; // a protected page's key, when the viewer asked to remember it

export const load = (k) => {
  try {
    return localStorage.getItem(k);
  } catch {
    return null;
  }
};
export const save = (k, v) => {
  try {
    localStorage.setItem(k, v);
  } catch {
    // Storage blocked or full: the setting just isn't remembered
  }
};
