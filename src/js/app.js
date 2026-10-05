// The page: starts every part, after main.js has opened a protected page. Modules
// only declare things; everything that runs at start runs here, in this order.
import { buildCards } from "./cards.js";
import {
  initControls,
  initSettings,
  syncAvail,
  syncBadges,
  syncSort,
  syncSplit,
} from "./controls.js";
import { initCompare } from "./compare.js";
import { initDetail, openFromHash } from "./detail.js";
import { initFilters, syncFilters } from "./filters.js";
import { apply, fillGenres } from "./grid.js";
import { initHeader, initNewSince, initUpdated } from "./header.js";
import { translatePage } from "./i18n.js";
import { initImport, openSharedList } from "./import.js";
import { initRatingClicks, updateTray } from "./list.js";
import { initListDialog } from "./list-dialog.js";
import { initMenu } from "./menu.js";
import { initRequests } from "./requests.js";
import { initTooltips } from "./tooltips.js";

translatePage();
initHeader();
buildCards();
initRatingClicks();
initRequests();
initDetail();
initListDialog();
initMenu();
initImport();
initCompare();
initControls();
initSettings();
initFilters();
initTooltips();
initNewSince();
initUpdated();

fillGenres();
syncAvail();
syncSplit();
syncSort();
syncBadges();
syncFilters();
updateTray();
apply();
openFromHash(); // a shared link: open that title
openSharedList(); // a shared list: offer to import it
