#!/usr/bin/env python3
"""Headless smoke test for the dashboard: every section of both lanes renders, charts
draw, no console errors, at desktop and phone widths. Exits non-zero on failure."""

from __future__ import annotations

import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site" / "public"
URL = None  # set at boot (http://127.0.0.1:<port>/index.html)

CANVASES = {
    "overview": ["#oResolved", "#oTok", "#oThr", "#oWall"],
    "runs": [
        "#cResolved",
        "#cThr",
        "#cTok",
        "#cWall",
        "#cCache",
        "#cFail",
        "#cCalls",
        "#cDist",
        "#cGrid",
        "#cMc",
    ],
    "models": [
        "#mModelTps",
        "#mModelPp",
        # run-view canvases: present in the models panel, drawn only once a round is open
        "#mDecode",
        "#mPrefill",
        # performance-view canvases: hidden until the Performance submenu chip is on (and hidden
        # per chart when no round recorded that figure), so the submenu walk below gates them
        "#pfDecode",
        "#pfEncode",
        "#pfCache",
        "#pfMTP",
        "#pfCap",
    ],
}


OVERFLOW_JS = """(() => {
    const vw = window.innerWidth;
    const inScroller = el => {
        for (let n = el; n; n = n.parentElement) {
            const ox = getComputedStyle(n).overflowX;
            if (ox === 'auto' || ox === 'scroll') return true;
        }
        return false;
    };
    const canv = [...document.querySelectorAll('canvas')]
        .filter(c => !inScroller(c) && c.getBoundingClientRect().width > vw + 1)
        .map(c => c.id);
    const sw = document.documentElement.scrollWidth;
    return {canv, pageOverflow: sw > vw + 1, scrollWidth: sw, vw};
})()"""


def overflow_errors(page, label: str, where: str) -> list[str]:
    """Gate the mobile rule where the reader actually is: a section can only overflow
    once its own panels are visible, and heat maps / wide tables are allowed to scroll
    inside their own box, so only an un-scrolled canvas or page overflow is a failure."""
    wide = page.evaluate(OVERFLOW_JS)
    errors = []
    if wide["canv"]:
        errors.append(f"{label}/{where}: canvases wider than viewport: {wide['canv']}")
    if wide["pageOverflow"]:
        errors.append(
            f"{label}/{where}: page scrolls horizontally "
            f"(scrollWidth {wide['scrollWidth']} > viewport {wide['vw']})"
        )
    return errors


def drawn(canvas) -> bool:
    return canvas.evaluate(
        """c => { const g = c.getContext('2d');
            const d = g.getImageData(0, 0, c.width, c.height).data;
            for (let i = 3; i < d.length; i += 4) if (d[i] > 0) return true;
            return false; }"""
    )


def check_page(page, label: str) -> list[str]:
    errors: list[str] = []
    console: list[str] = []
    page.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console.append(str(e)))
    page.goto(URL, wait_until="networkidle")
    page.wait_for_function("typeof DATA !== 'undefined' && DATA.runs && DATA.runs.length > 0")
    page.wait_for_timeout(800)
    if "cohortTable" not in page.content():
        errors.append(f"{label}: page did not hydrate")
    for section, ids in CANVASES.items():
        page.evaluate(f"location.hash = '{section}'; showSection('{section}')")
        page.wait_for_timeout(900)
        for sel in ids:
            el = page.query_selector(sel)
            if el is None:
                errors.append(f"{label}/{section}: missing {sel}")
                continue
            if el.is_visible() and not drawn(el):
                errors.append(f"{label}/{section}: {sel} has no pixels (empty chart)")
        errors += overflow_errors(page, label, section)
        if section == "runs":
            math = page.evaluate("({b: binom(5, 2), p: mcNemarP(2, 5), p2: mcNemarP(21, 1)})")
            if math["b"] != 10 or abs(math["p"] - 0.453125) > 1e-9 or math["p2"] > 1e-4:
                errors.append(f"{label}: McNemar math wrong: {math}")
        if section == "models":
            # the lane overview is only an index — open every round the way a tab click does, so
            # each round's own charts, banner, table, disclaimer and overflow are gated (the
            # CANVASES check above skips #mDecode/#mPrefill: they are hidden until a round opens)
            rounds = page.evaluate("[...(DATA.model_runs || []).map(m => m.id)]")
            if not rounds:
                errors.append(f"{label}/models: DATA.model_runs is empty")
                continue
            for rid in rounds:
                page.evaluate(f"showSection('models/{rid}')")
                page.wait_for_timeout(700)
                for sel in ("#mDecode", "#mPrefill"):
                    el = page.query_selector(sel)
                    if el is None or (el.is_visible() and not drawn(el)):
                        errors.append(f"{label}/models/{rid}: {sel} missing or not drawn")
                for sel in ("#modelBanner", "#modelRows"):
                    if not page.query_selector(sel).inner_text().strip():
                        errors.append(f"{label}/models/{rid}: {sel} empty")
                comparable = page.evaluate(
                    """id => { const m = (DATA.model_runs || []).find(x => x.id === id);
                        return !!m && m.cells.some(c =>
                            m.legs.filter(l => c.legs[l] && c.legs[l].tps != null).length > 1); }""",
                    rid,
                )
                if not comparable and not page.query_selector("#cellNote").inner_text().strip():
                    errors.append(f"{label}/models/{rid}: one leg per cell, but no #cellNote disclaimer")
                errors += overflow_errors(page, label, f"models/{rid}")
            # the lane submenu switches views in place, exactly as its chips do, so each view's
            # own charts, notes and phone overflow get gated (the CANVASES pass above finds the
            # performance canvases hidden there and skips them — that is what this walk is for)
            for view in ("showdown", "perf"):
                page.evaluate(f"showSection('models'); modelView = '{view}'; render()")
                page.wait_for_timeout(800)
                where = f"models/{view}"
                # the submenu must carry an active chip, and it must be a button: these switch what
                # is on screen, so the keyboard has to be able to reach and operate them
                if not page.evaluate("document.querySelector('#modelSub .chip.on')?.tagName === 'BUTTON'"):
                    errors.append(f"{label}/{where}: submenu has no active chip button")
                if view == "showdown":
                    night, newest, nights = page.evaluate(
                        "[sdNight, sdNights(sdRuns())[0], sdNights(sdRuns()).length]"
                    )
                    if night != newest:
                        errors.append(f"{label}/{where}: night is {night}, newest night is {newest}")
                    if not page.query_selector_all("#sdCards .sd-card"):
                        errors.append(f"{label}/{where}: no round cards for night {night}")
                    stray = page.evaluate(
                        """() => [...document.querySelectorAll('#sdCards .sd-card')]
                               .filter(c => !c.title.includes('-' + sdNight + '-'))
                               .map(c => c.title)"""
                    )
                    if stray:
                        errors.append(f"{label}/{where}: cards outside the night: {stray[:3]}")
                    if nights > 1 and not page.query_selector("#sdNightNote").inner_text().strip():
                        errors.append(f"{label}/{where}: nights filtered with no #sdNightNote line")
                    # switching night is a click, not a page load: the cards change in place
                    if nights > 1:
                        cards = "#sdCards .sd-card"
                        before = [c.get_attribute("title") for c in page.query_selector_all(cards)]
                        page.evaluate("document.querySelectorAll('#sdNights .chip')[1].click()")
                        page.wait_for_timeout(400)
                        after = [c.get_attribute("title") for c in page.query_selector_all(cards)]
                        if before == after:
                            errors.append(f"{label}/{where}: night chip click left the cards unchanged")
                    if page.evaluate("location.hash") != "#models":
                        errors.append(f"{label}/{where}: night chip navigated instead of re-rendering")
                else:
                    # the cap chart draws (F5), and its one caption line states the verdict in words
                    if not page.query_selector("#pfCapNote").inner_text().strip():
                        errors.append(f"{label}/{where}: #pfCapNote has no cap-honesty caption")
                    for cid in ("#pfDecode", "#pfEncode", "#pfCache", "#pfMTP", "#pfCap"):
                        el = page.query_selector(cid)
                        if el is None:
                            errors.append(f"{label}/{where}: missing {cid}")
                        elif el.is_visible() and not drawn(el):
                            errors.append(f"{label}/{where}: {cid} has no pixels (empty chart)")
                        elif (
                            not el.is_visible() and not page.query_selector(f"{cid}Note").inner_text().strip()
                        ):
                            errors.append(f"{label}/{where}: {cid} hidden with nothing said about it")
                errors += overflow_errors(page, label, where)
            page.evaluate("showSection('models')")
            page.wait_for_timeout(300)
    for sel, sec in (("#rigBody", "rig"), ("#tuneBody", "calibration")):
        page.evaluate(f"showSection('{sec}')")
        page.wait_for_timeout(300)
        if not page.query_selector(sel).inner_text().strip():
            errors.append(f"{label}: {sel} empty")
    console = [c for c in console if "favicon" not in c]
    if console:
        errors.append(f"{label}: console errors: {console[:4]}")
    return errors


def main() -> int:
    global URL
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    URL = f"http://127.0.0.1:{server.server_address[1]}/index.html"
    all_errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        for label, vp in [
            ("desktop", {"width": 1280, "height": 900}),
            ("phone", {"width": 390, "height": 844}),
        ]:
            pg = browser.new_page(viewport=vp)
            all_errors += check_page(pg, label)
            shots = Path("smoke")
            shots.mkdir(exist_ok=True)
            pg.evaluate("showSection('overview')")
            pg.wait_for_timeout(400)
            pg.screenshot(path=str(shots / f"{label}.png"), full_page=False)
            pg.close()
        browser.close()
    if all_errors:
        print("SMOKE FAIL")
        for e in all_errors:
            print(" -", e)
        return 1
    n_canvas = sum(len(v) for v in CANVASES.values())
    print(f"SMOKE OK (desktop 1280px + phone 390px, {n_canvas} canvases, 0 console errors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
