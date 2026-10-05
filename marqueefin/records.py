"""The page's records: titles, seasons, collections."""

from collections import Counter

from .dates import local_date, year_of
from .jellyfin import is_missing
from .media import combined_media, item_media


def build_links(item, kind, public_url):
    ids = {k.lower(): v for k, v in (item.get("ProviderIds") or {}).items() if v}
    links = []
    if ids.get("imdb"):
        links.append({"label": "IMDb", "url": f"https://www.imdb.com/title/{ids['imdb']}/"})
    if ids.get("tmdb"):
        path = {"movie": "movie", "collection": "collection"}.get(kind, "tv")
        links.append({"label": "TMDB", "url": f"https://www.themoviedb.org/{path}/{ids['tmdb']}"})
    if ids.get("tvdb") and kind != "collection":
        path = "movie" if kind == "movie" else "series"
        links.append(
            {
                "label": "TVDB",
                "url": f"https://www.thetvdb.com/dereferrer/{path}/{ids['tvdb']}",
            }
        )
    if public_url:
        links.append(
            {
                "label": "Jellyfin",
                "url": f"{public_url.rstrip('/')}/web/#/details?id={item['Id']}",
            }
        )
    return links


def build_record(item, public_url):
    kind = {"Movie": "movie", "BoxSet": "collection"}.get(item.get("Type"), "series")
    rec = {
        "id": item["Id"],
        "type": kind,
        "title": item.get("Name") or "Untitled",
        "sort": (item.get("SortName") or item.get("Name") or "").lower(),
        "year": item.get("ProductionYear") or year_of(item.get("PremiereDate")),
        "rating": round(item["CommunityRating"], 1) if item.get("CommunityRating") else None,
        "critic": item.get("CriticRating"),
        "cert": item.get("OfficialRating"),
        "genres": item.get("Genres") or [],
        "overview": item.get("Overview") or "",
        "added": (item.get("DateCreated") or "")[:10],
        "released": local_date(item.get("PremiereDate")),
        "links": build_links(item, kind, public_url),
        "poster": None,
    }
    if kind == "movie" and item.get("RunTimeTicks"):
        rec["runtime"] = round(item["RunTimeTicks"] / 600_000_000)
    media = item_media(item)
    if media:
        rec["media"] = media
    if kind == "series":
        rec["seasons"] = item.get("ChildCount")
        rec["status"] = item.get("Status")
        rec["endYear"] = year_of(item.get("EndDate"))
    return rec


def episode_ranges(nums):
    """[1, 2, 3, 7] -> 'E1–E3, E7'"""
    nums, out, i = sorted(nums), [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(f"E{nums[i]}" if i == j else f"E{nums[i]}–E{nums[j]}")
        i = j + 1
    return ", ".join(out)


def season_items(items):
    """(season number by season id, {(series id, n): {ids, name, year}}). Several ids:
    stale duplicate season items exist, and only the real one has watched data."""
    index, info = {}, {}
    for it in items:
        n = it.get("IndexNumber")
        if it.get("Type") != "Season" or not it.get("SeriesId") or n is None:
            continue
        index[it["Id"]] = n
        s = info.setdefault((it["SeriesId"], n), {"ids": []})
        s["ids"].append(it["Id"])
        s["name"] = it.get("Name")
        s["year"] = it.get("ProductionYear") or year_of(it.get("PremiereDate"))
    return index, info


def group_episodes(items, index, info):
    """{series id: {season number: [episodes]}}, including announced seasons that
    have no episodes yet."""
    groups = {}
    for it in items:
        if it.get("Type") != "Episode" or not it.get("SeriesId"):
            continue
        n = it.get("ParentIndexNumber")
        if n is None:
            n = index.get(it.get("SeasonId"))
        if n is not None:
            groups.setdefault(it["SeriesId"], {}).setdefault(n, []).append(it)
    for series_id, n in info:
        groups.setdefault(series_id, {}).setdefault(n, [])
    return groups


def count_episodes(eps, missing_ids, today):
    """(numbers you have, unnumbered ones you have, missing, upcoming, next air date).
    Missing: virtual and aired; unaired or undated ones are upcoming."""
    have, unnumbered = owned_numbers(eps, missing_ids)
    return (have, unnumbered, *not_there(eps, missing_ids, have, today))


def owned_numbers(eps, missing_ids):
    have, unnumbered = set(), 0
    for ep in eps:
        if is_missing(ep, missing_ids):
            continue
        i = ep.get("IndexNumber")
        if i is None:
            unnumbered += 1
        else:
            have.update(range(i, (ep.get("IndexNumberEnd") or i) + 1))
    return have, unnumbered


def not_there(eps, missing_ids, have, today):
    """(missing, upcoming, next air date) of the episodes you don't have."""
    missing, upcoming, dates = set(), set(), []
    for ep in eps:
        i = ep.get("IndexNumber")
        if not is_missing(ep, missing_ids) or i in have:
            continue
        aired = local_date(ep.get("PremiereDate"))
        key = i if i is not None else ep["Id"]
        if aired and aired <= today:
            missing.add(key)
            continue
        upcoming.add(key)
        if aired:
            dates.append(aired)
    return missing, upcoming, min(dates, default=None)


def season_status(got, missing, upcoming):
    if not got:
        return "missing" if missing else "tba"
    if missing:
        return "partial"
    # Everything aired is there; "airing" while more are still to come
    return "airing" if upcoming else "available"


def season_record(n, eps, info, missing_ids, today):
    """One season of a series, or None for specials you have none of."""
    have, unnumbered, missing, upcoming, next_date = count_episodes(eps, missing_ids, today)
    got = len(have) + unnumbered
    if n == 0 and not got:
        return None
    dates = [d for ep in eps if (d := local_date(ep.get("PremiereDate")))]
    first = min(dates, default=None)
    numbered = [m for m in missing if isinstance(m, int)]
    extras = {
        "missing": episode_ranges(numbered) if numbered else None,
        "upcoming": len(upcoming) or None,
        "next": next_date,
        "year": year_of(first) or info.get("year"),  # when its first episode aired
        "date": first,
        "q": season_quality(eps, missing_ids),
    }
    return {
        "_ids": info.get("ids", []),  # for user data; removed after
        "n": n,
        "name": info.get("name") or ("Specials" if n == 0 else f"Season {n}"),
        "status": season_status(got, missing, upcoming),
        "have": got,
        "total": got + len(missing) + len(upcoming),
        **{k: v for k, v in extras.items() if v},
    }


def season_quality(eps, missing_ids):
    q = combined_media([item_media(ep) for ep in eps if not is_missing(ep, missing_ids)])
    return {k: q[k] for k in ("res", "resMixed", "hdr", "size") if k in q} if q else None


def build_seasons(items, missing_ids, today):
    """Per series: its seasons with a status (available / airing / partial / missing /
    tba) and the year their first episode aired. Specials last."""
    index, info = season_items(items)
    result = {}
    for series_id, seasons in group_episodes(items, index, info).items():
        out = [season_record(n, eps, info.get((series_id, n), {}), missing_ids, today)
               for n, eps in seasons.items()]  # fmt: skip
        out = [s for s in out if s]
        out.sort(key=lambda s: (s["n"] == 0, s["n"]))
        result[series_id] = out
    return result


def attach_seasons(rec, seasons):
    rec["seasonList"] = seasons
    regular = [s for s in seasons if s["n"] > 0 and s["status"] != "tba"]
    if regular:
        rec["seasons"] = len(regular)
        rec["complete"] = all(s["status"] in ("available", "airing") for s in regular)


def attach_episodes(rec, owned):
    """Series info from the episodes you have: when the newest one was added
    (shown as 'updated'), and a media summary across all of them."""
    latest = max(((ep.get("DateCreated") or "")[:10] for ep in owned), default="")
    if latest > rec["added"]:
        rec["updated"] = latest
    media = combined_media([item_media(ep) for ep in owned])
    if media:
        rec["media"] = media


def has_poster(item):
    return bool((item.get("ImageTags") or {}).get("Primary"))


def collection_key(boxset):
    """The same for duplicates of one TMDB collection."""
    tmdb = {k.lower(): v for k, v in (boxset.get("ProviderIds") or {}).items()}.get("tmdb")
    return f"tmdb:{tmdb}" if tmdb else boxset["Id"]


def pick_collections(boxsets, members, by_id):
    """[(box set, member ids by year)] for box sets with exported members; duplicates
    (one TMDB collection) merged into the one with a poster."""
    merged = {}
    for b in boxsets:
        ids = [i for i in members.get(b["Id"], []) if i in by_id]
        if ids:
            merge_boxset(merged, b, ids)
    by_year = lambda i: (by_id[i].get("year") or 9999, by_id[i]["sort"])
    return [(b, sorted(ids, key=by_year)) for b, ids in merged.values()]


def merge_boxset(merged, boxset, ids):
    """Into merged (by collection_key): a duplicate adds its members, and its poster
    where the first one has none."""
    key = collection_key(boxset)
    if key not in merged:
        merged[key] = [boxset, ids]
        return
    keep, have = merged[key]
    if has_poster(boxset) and not has_poster(keep):
        merged[key][0] = boxset
    have += [i for i in ids if i not in have]


def collection_record(item, ids, by_id, public_url):
    rec = build_record(item, public_url)
    members = [by_id[i] for i in ids]
    years = [m["year"] for m in members if m.get("year")]
    released = [m["released"] for m in members if m.get("released")]
    rec["items"] = ids
    rec["year"] = min(years, default=rec["year"])
    rec["endYear"] = max(years, default=None)
    rec["released"] = min(released, default=rec["released"])
    latest = max(m["added"] for m in members)  # newest title added to it
    if latest > rec["added"]:
        rec["updated"] = latest
    if not rec["rating"]:  # box sets have no rating: the average of their titles
        rec.update(average_rating(members))
    if not rec["genres"]:  # box sets often have none; borrow from the members
        rec["genres"] = [
            g for g, _ in Counter(g for m in members for g in m["genres"]).most_common(4)
        ]
    return rec


def average_rating(members):
    rated = [m["rating"] for m in members if m.get("rating")]
    return {"rating": round(sum(rated) / len(rated), 1), "ratingOf": len(rated)} if rated else {}
