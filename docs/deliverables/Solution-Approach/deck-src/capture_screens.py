"""Capture screenshots of the Ferrero web app over the Chrome DevTools Protocol.

    python cdp_shots.py <base_url> <out_dir> <job> [job ...]

Jobs:
  page:<name>:<path>[:<user>]            navigate, wait for the page to settle, screenshot
  ask:<name>:<path>:<user>:<question>    navigate, type the question, send, wait for the answer, screenshot
"""
import base64
import json
import os
import sys
import time
import urllib.request

import websocket

BASE, OUT = sys.argv[1].rstrip("/"), sys.argv[2]
os.makedirs(OUT, exist_ok=True)
W, H, SCALE = 1600, 1000, 2

targets = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json"))
page = next(t for t in targets if t.get("type") == "page")
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=180, suppress_origin=True)
_id = 0


def cdp(method, **params):
    global _id
    _id += 1
    ws.send(json.dumps({"id": _id, "method": method, "params": params}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == _id:
            if "error" in msg:
                raise RuntimeError(f"{method}: {msg['error']}")
            return msg.get("result", {})


def js(expr):
    r = cdp("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
    return r.get("result", {}).get("value")


def wait_for(expr, timeout=30, interval=0.4):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if js(expr):
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def settle(extra=1.2):
    # app shell rendered and no "Loading" placeholders left
    wait_for("document.querySelector('main') !== null && !document.body.innerText.includes('Loading')", 30)
    time.sleep(extra)


def set_user(user):
    js(f"localStorage.setItem('ferrero.user', '{user}'); localStorage.setItem('ferrero.theme', 'light'); true")


def goto(path, user):
    cdp("Page.navigate", url=BASE + "/blank-for-storage")
    time.sleep(0.8)
    set_user(user)
    cdp("Page.navigate", url=BASE + path)
    time.sleep(1.5)
    settle()


def shot(name):
    data = cdp("Page.captureScreenshot", format="png", captureBeyondViewport=False)["data"]
    path = os.path.join(OUT, name + ".png")
    with open(path, "wb") as f:
        f.write(base64.b64decode(data))
    print("saved", path)


cdp("Page.enable")
cdp("Runtime.enable")
cdp("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=SCALE, mobile=False)

for job in sys.argv[3:]:
    kind, rest = job.split(":", 1)
    if kind == "page":
        parts = rest.split(":")
        name, path = parts[0], parts[1]
        user = parts[2] if len(parts) > 2 else "U-08"
        goto(path, user)
        shot(name)
    elif kind == "ask":
        name, path, user, question = rest.split(":", 3)
        goto(path, user)
        wait_for("(() => { const t = document.querySelector('textarea'); return t && !t.disabled; })()", 30)
        time.sleep(1.0)
        js("document.querySelector('textarea').focus(); true")
        cdp("Input.insertText", text=question)
        time.sleep(0.4)
        cdp("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13,
            nativeVirtualKeyCode=13, text="\r")
        cdp("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13,
            nativeVirtualKeyCode=13)
        time.sleep(2)
        ok = wait_for("!document.body.innerText.includes('Ferrero is checking the case files')", 180, 1.0)
        print("answer arrived" if ok else "TIMEOUT waiting for answer")
        time.sleep(1.5)
        # scroll the thread to the top of the answer so the question and the start of the answer are visible
        js("(() => { const el = [...document.querySelectorAll('div')].find(d => d.className && d.className.includes && "
           "d.className.includes('overflow-y-auto') && d.querySelector('blockquote, .animate-fade-up')); "
           "if (el) el.scrollTop = 0; return !!el; })()")
        time.sleep(0.8)
        shot(name)
        text = js("document.querySelector('main') ? document.querySelector('main').innerText : document.body.innerText")
        with open(os.path.join(OUT, name + ".txt"), "w", encoding="utf-8") as f:
            f.write(text or "")
ws.close()
