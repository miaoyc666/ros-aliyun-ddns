import sys
import urllib.error
import urllib.request


try:
    urllib.request.urlopen("http://127.0.0.1:6180/ddns", timeout=2)
except urllib.error.HTTPError as exc:
    sys.exit(0 if exc.code < 500 else 1)
except Exception:
    sys.exit(1)
