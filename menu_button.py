import os, json, urllib.request

def set_menu_button():
    token = (os.environ.get("BOT_TOKEN") or "").strip()
    url = (os.environ.get("WEBAPP_URL") or "").strip() or "https://sport-helper-robot.online/tracker.html"
    if not token:
        return

    api = f"https://api.telegram.org/bot{token}/setChatMenuButton"
    body = {
        "menu_button": {
            "type": "web_app",
        "text": "Открыть",
            "web_app": {"url": url}
        }
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(api, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception:
        pass
