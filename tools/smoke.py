#!/usr/bin/env python3
"""Headless smoke test for the dashboard: every section renders, charts draw,
no console errors, at desktop and phone widths. Exits non-zero on failure."""

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
    "runs": ["#cResolved", "#cThr", "#cTok", "#cWall", "#cCache", "#cDist", "#cGrid", "#cMc"],
}


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
    wide = page.evaluate(
        """(() => {
            const vw = window.innerWidth;
            const canv = [...document.querySelectorAll('canvas')]
                .filter(c => c.getBoundingClientRect().width > vw + 1)
                .map(c => c.id);
            const pageOverflow = document.documentElement.scrollWidth > vw + 1;
            return {canv, pageOverflow};
        })()"""
    )
    if wide["canv"]:
        errors.append(f"{label}: canvases wider than viewport: {wide['canv']}")
    if wide["pageOverflow"]:
        errors.append(f"{label}: page scrolls horizontally ({wide})")
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
        if section == "runs":
            math = page.evaluate("({b: binom(5, 2), p: mcNemarP(2, 5), p2: mcNemarP(21, 1)})")
            if math["b"] != 10 or abs(math["p"] - 0.453125) > 1e-9 or math["p2"] > 1e-4:
                errors.append(f"{label}: McNemar math wrong: {math}")
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
    print("SMOKE OK (desktop 1280px + phone 390px, 11 canvases, 0 console errors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
