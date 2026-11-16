import base64, json, os, sys, time, urllib.request
import websocket
BASE, OUT = sys.argv[1].rstrip('/'), sys.argv[2]
targets = json.load(urllib.request.urlopen('http://127.0.0.1:9333/json'))
page = next(t for t in targets if t.get('type') == 'page')
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=180, suppress_origin=True)
_id = 0
def cdp(method, **params):
    global _id
    _id += 1
    ws.send(json.dumps({'id': _id, 'method': method, 'params': params}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == _id:
            if 'error' in msg: raise RuntimeError(f"{method}: {msg['error']}")
            return msg.get('result', {})
def js(expr):
    r = cdp('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True)
    return r.get('result', {}).get('value')
cdp('Page.enable'); cdp('Runtime.enable')
cdp('Emulation.setDeviceMetricsOverride', width=1600, height=1000, deviceScaleFactor=2, mobile=False)
for job in sys.argv[3:]:
    name, path, user, wait = job.split('|')
    cdp('Page.navigate', url=BASE + '/blank-for-storage'); time.sleep(0.8)
    js(f"localStorage.setItem('ferrero.user', '{user}'); localStorage.setItem('ferrero.theme', 'light'); true")
    cdp('Page.navigate', url=BASE + path)
    time.sleep(float(wait))
    data = cdp('Page.captureScreenshot', format='png')['data']
    p = os.path.join(OUT, name + '.png'); open(p, 'wb').write(base64.b64decode(data)); print('saved', p)
    print('  text:', (js("document.querySelector('main') ? document.querySelector('main').innerText.slice(0,400) : ''") or '').replace('\n',' | '))
ws.close()
