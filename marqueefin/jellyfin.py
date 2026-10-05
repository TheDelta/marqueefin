"""The Jellyfin API: titles, episodes, user data, box sets."""

import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import USER_AGENT
from .cache import MISS
from .dates import utc_stamp
from .log import log, progress_logger
from .media import item_media
from .net import tls_context

ITEM_FIELDS = "ProviderIds,Overview,Genres,ProductionYear,CommunityRating,CriticRating,OfficialRating,RunTimeTicks,ChildCount,DateCreated,PremiereDate,EndDate,Status,SortName"
PAGE_SIZE = 500


class Jellyfin:
    def __init__(self, url, api_key, ctx=None, timeout=60, page_workers=4):
        self.base = url.rstrip("/")
        self.key = api_key
        self.timeout = timeout
        self.ctx = ctx or tls_context()
        self.page_workers = max(1, page_workers)  # pages fetched at the same time

    def request(self, path, params=None):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f'MediaBrowser Token="{self.key}"',
                "X-Emby-Token": self.key,  # older servers
                "User-Agent": USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout, context=self.ctx) as r:
            return r.read()

    def get_json(self, path, params=None):
        return json.loads(self.request(path, params))

    def libraries(self):
        return self.get_json("/Library/VirtualFolders")

    def user(self, user_id=None):
        """(id, name) of the given user, else of the first administrator."""
        users = self.get_json("/Users")
        norm = lambda s: (s or "").replace("-", "").lower()
        pick = (
            next((u for u in users if user_id and norm(u["Id"]) == norm(user_id)), None)
            or next((u for u in users if u.get("Policy", {}).get("IsAdministrator")), None)
            or (users[0] if users else None)
        )
        return (pick["Id"], pick.get("Name") or "?") if pick else (None, None)

    def admin_user_id(self):
        users = self.get_json("/Users")
        for u in users:
            if u.get("Policy", {}).get("IsAdministrator"):
                return u["Id"]
        return users[0]["Id"] if users else None

    def iter_items(
        self, path, types, parent_id=None, fields=ITEM_FIELDS, extra=None, progress=None
    ):
        """All matching items, in order. The first page gives the total; the rest are
        fetched page_workers at a time."""
        params = {
            "Recursive": "true",
            "IncludeItemTypes": types,
            "SortBy": "SortName",
            "SortOrder": "Ascending",
            "EnableImageTypes": "Primary",
            "ImageTypeLimit": 1,
            "Limit": PAGE_SIZE,
        }
        if fields:
            params["Fields"] = fields
        if extra:
            params.update(extra)
        if parent_id:
            params["ParentId"] = parent_id
        page = lambda start: self.get_json(path, {**params, "StartIndex": start})
        first = page(0)
        items, total = first.get("Items", []), first.get("TotalRecordCount", 0)
        done = len(items)
        if progress:
            progress(done, total)
        yield from items
        if not items or done >= total:
            return
        with ThreadPoolExecutor(max_workers=self.page_workers) as pool:
            # map() hands the pages back in order, whatever order they arrive in
            for data in pool.map(page, range(len(items), total, len(items))):
                items = data.get("Items", [])
                done += len(items)
                if progress:
                    progress(min(done, total), total)
                yield from items

    def items_by_id(self, ids, fields, batch=150, progress=None):
        """Items by id, in batches (150 ids keep the URL well under proxy limits),
        page_workers batches at a time."""
        if not ids:
            return []
        params = {"Fields": fields, "EnableImages": "false", "EnableUserData": "false"}
        batches = [ids[i : i + batch] for i in range(0, len(ids), batch)]
        path = "/Items"

        def fetch(part):
            return self.get_json(path, {**params, "Ids": ",".join(part)}).get("Items", [])

        try:  # the first batch also finds out whether /Items works without a user
            out = fetch(batches[0])
        except urllib.error.HTTPError as e:
            if e.code not in (400, 401, 403, 404):
                raise
            e.close()  # it holds the open response
            path = f"/Users/{self.admin_user_id()}/Items"
            out = fetch(batches[0])
        if progress:
            progress(len(out), len(ids))
        with ThreadPoolExecutor(max_workers=self.page_workers) as pool:
            for part in pool.map(fetch, batches[1:]):
                out += part
                if progress:
                    progress(len(out), len(ids))
        return out


def fetch_all_items(jf, types, parent_ids, user_id=None, **kw):
    """Fetch items; if /Items isn't allowed without a user, fall back to an admin user."""
    if user_id:
        return unique_items(jf, f"/Users/{user_id}/Items", types, parent_ids, **kw)
    try:
        items = unique_items(jf, "/Items", types, parent_ids, **kw)
        if items:
            return items
    except urllib.error.HTTPError as e:
        if e.code not in (400, 401, 403, 404):
            raise
        e.close()
    uid = jf.admin_user_id()
    if not uid:
        return []
    log("   (using user-scoped endpoint)")
    return unique_items(jf, f"/Users/{uid}/Items", types, parent_ids, **kw)


def unique_items(jf, path, types, parent_ids, **kw):
    """The items of every library in parent_ids, each once."""
    seen, out = set(), []
    for pid in parent_ids or [None]:
        for it in jf.iter_items(path, types, pid, **kw):
            if it["Id"] not in seen:
                seen.add(it["Id"])
                out.append(it)
    return out


def fetch_episodes(jf, parent_ids, user_id=None, media_cache=None):
    """All seasons and episodes, and the ids of missing (virtual) ones; with media_cache
    also each owned episode's file details."""
    lean = {"EnableImages": "false", "EnableUserData": "false"}
    items = fetch_all_items(
        jf,
        "Season,Episode",
        parent_ids,
        user_id,
        fields="DateCreated",
        extra=lean,
        progress=progress_logger("seasons/episodes"),
    )
    # Ask for missing ones explicitly too, in case the default query hides them
    try:
        missing = fetch_all_items(
            jf,
            "Episode",
            parent_ids,
            user_id,
            fields="",
            extra={**lean, "IsMissing": "true"},
            progress=progress_logger("missing episodes"),
        )
    except urllib.error.HTTPError as e:
        e.close()
        missing = []
    known = {it["Id"] for it in items}
    items += [it for it in missing if it["Id"] not in known]
    missing_ids = {it["Id"] for it in missing}
    if media_cache is not None:
        attach_episode_media(jf, items, missing_ids, media_cache)
    return items, missing_ids


def attach_episode_media(jf, items, missing_ids, cache):
    """ep["_media"] for owned episodes. File details cost about 15x the episode list, so
    they're cached by episode id (an upgraded file gets a new id, the expiry catches in-
    place swaps) and only unknown ids are fetched."""
    owned = [ep for ep in items if ep.get("Type") == "Episode" and not is_missing(ep, missing_ids)]
    todo = []
    for ep in owned:
        hit = cache.get(ep["Id"], MISS)
        if hit is MISS:
            todo.append(ep)
        else:
            ep["_media"] = hit
    got = jf.items_by_id(
        [ep["Id"] for ep in todo],
        "MediaSources",
        progress=progress_logger("episode file details"),
    )
    fetched = {it["Id"]: item_media(it) for it in got}
    for ep in todo:
        if ep["Id"] in fetched:
            ep["_media"] = fetched[ep["Id"]]
            cache.put(ep["Id"], fetched[ep["Id"]])
    log(f"   file details: {len(owned) - len(todo):,} remembered, {len(fetched):,} fetched")


def fetch_user_data(jf, user_id):
    """Watched / favorite state of every movie, series, season and collection for one
    user, by item id."""
    items = jf.iter_items(
        f"/Users/{user_id}/Items",
        "Movie,Series,Season,BoxSet",
        fields="",
        extra={
            "EnableImages": "false",
            "EnableUserData": "true",
            "CollapseBoxSetItems": "false",
        },
        progress=progress_logger("watched / favorites"),
    )
    return {it["Id"]: it.get("UserData") or {} for it in items}


def fetch_series_last_played(jf, user_id):
    """Last play date per series. Jellyfin only dates plays of movies and episodes."""
    last, report = {}, progress_logger("watched episodes")
    for flt in ("IsPlayed", "IsResumable"):
        for ep in jf.iter_items(
            f"/Users/{user_id}/Items",
            "Episode",
            fields="",
            extra={"EnableImages": "false", "EnableUserData": "true", "Filters": flt},
            progress=report if flt == "IsPlayed" else None,  # the in-progress ones are few
        ):
            stamp = utc_stamp((ep.get("UserData") or {}).get("LastPlayedDate"))
            sid = ep.get("SeriesId")
            if stamp and sid and stamp > last.get(sid, ""):
                last[sid] = stamp
    return last


def user_flags(target, ud):
    """watched, watchedPct (partly watched), fav and lastWatched (UTC) from Jellyfin's
    user data."""
    if not ud:
        return
    if ud.get("IsFavorite"):
        target["fav"] = True
    if ud.get("Played"):
        target["watched"] = True
    elif round(ud.get("PlayedPercentage") or 0):
        target["watchedPct"] = round(ud["PlayedPercentage"])
    if utc_stamp(ud.get("LastPlayedDate")):
        target["lastWatched"] = utc_stamp(ud["LastPlayedDate"])


def attach_user_data(records, user_data, series_played):
    for r in records:
        user_flags(r, user_data.get(r["id"]))
        if series_played.get(r["id"]):
            r["lastWatched"] = max(r.get("lastWatched", ""), series_played[r["id"]])
    # A collection: when any of its titles was last watched
    by_id = {r["id"]: r for r in records}
    for r in records:
        if r["type"] == "collection":
            played = [by_id[i]["lastWatched"] for i in r["items"] if by_id[i].get("lastWatched")]
            if played:
                r["lastWatched"] = max(played)


def fetch_collections(jf, user_id, workers, cache, known_ids):
    """All box sets and their members' ids, whatever --library says (box sets have a
    library of their own). Members are reused while ChildCount is unchanged and every
    remembered member still exists."""
    # The user endpoint works on every server, and only it fills in ChildCount
    path = f"/Users/{user_id or jf.admin_user_id()}/Items"
    boxsets = list(jf.iter_items(path, "BoxSet", progress=progress_logger("box sets")))
    lean = {"EnableImages": "false", "CollapseBoxSetItems": "false"}
    fetched = []

    def members(b):
        count, hit = b.get("ChildCount"), cache.get(b["Id"])
        if (
            hit
            and count is not None
            and hit["count"] == count
            and all(i in known_ids for i in hit["ids"])
        ):
            return hit["ids"]
        kids = jf.iter_items(path, "Movie,Series", b["Id"], fields="", extra=lean)
        ids = [k["Id"] for k in kids]
        cache.put(b["Id"], {"count": count, "ids": ids})
        fetched.append(b["Id"])
        return ids

    # One request per box set, run in parallel; progress as they finish
    report, out = progress_logger("box set contents"), {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(members, b): b["Id"] for b in boxsets}
        for n, fut in enumerate(as_completed(futs), 1):
            out[futs[fut]] = fut.result()
            report(n, len(futs))
    log(f"   box set contents: {len(boxsets) - len(fetched)} remembered, {len(fetched)} fetched")
    return boxsets, out


def is_missing(ep, missing_ids):
    return ep.get("LocationType") == "Virtual" or ep["Id"] in missing_ids
