// What the page shows. f: the Filters panel (null or '' = any)
import { ALT, GROUP, QUALITY, RATINGS, SPLIT, STATUS, load } from "./store.js";

export const state = {
  type: "all",
  q: "",
  genre: "",
  avail: "",
  sort: "new",
  group: load(GROUP) !== "0",
  split: load(SPLIT) === "1",
  ratings: load(RATINGS) !== "0",
  status: load(STATUS) !== "0",
  quality: load(QUALITY) !== "0",
  alt: load(ALT) === "1",
  f: {
    yFrom: null,
    yTo: null,
    rFrom: null,
    rTo: null,
    quality: "",
    watched: "",
    fav: "",
    mark: "",
  },
};
