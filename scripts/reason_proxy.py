#!/usr/bin/env python3
"""
Optional local streaming reverse proxy for OpenAI-compatible llama.cpp APIs.
Rewrites unsupported reasoning_effort values ("high"/"max" -> "xhigh", "minimal" -> "low")
for models whose chat templates only support low/medium/xhigh (e.g. Huihui-Qwen3.8-27B).

Usage:
  python reason_proxy.py 8002:8001 8003:8000
"""
import http.client
import http.server
import json
import socketserver
import sys
import threading


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def make_handler(target_host, target_port):
    class ProxyHandler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):
            pass

        def _forward(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else None

            if body and "application/json" in self.headers.get("Content-Type", ""):
                try:
                    data = json.loads(body.decode("utf-8"))
                    re_val = data.get("reasoning_effort")
                    if re_val in ("high", "max"):
                        data["reasoning_effort"] = "xhigh"
                        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                    elif re_val == "minimal":
                        data["reasoning_effort"] = "low"
                        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                except Exception:
                    pass

            headers = {}
            for k, v in self.headers.items():
                lk = k.lower()
                if lk in ("host", "content-length", "connection", "accept-encoding"):
                    continue
                headers[k] = v
            if body is not None:
                headers["Content-Length"] = str(len(body))
            headers["Connection"] = "close"

            conn = http.client.HTTPConnection(target_host, target_port, timeout=600)
            try:
                conn.request(self.command, self.path, body=body, headers=headers)
                resp = conn.getresponse()
                self.send_response(resp.status, resp.reason)
                is_chunked = False
                for k, v in resp.getheaders():
                    lk = k.lower()
                    if lk in ("transfer-encoding", "connection"):
                        if lk == "transfer-encoding" and "chunked" in v.lower():
                            is_chunked = True
                        continue
                    self.send_header(k, v)
                if is_chunked:
                    self.send_header("Connection", "close")
                self.end_headers()

                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except Exception as e:
                try:
                    err = json.dumps({"error": str(e)}).encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                except Exception:
                    pass
            finally:
                conn.close()

        def do_GET(self):
            self._forward()

        def do_POST(self):
            self._forward()

        def do_OPTIONS(self):
            self._forward()

    return ProxyHandler


def serve(listen_port, target_port):
    srv = ThreadingHTTPServer(("127.0.0.1", listen_port), make_handler("127.0.0.1", target_port))
    print(f"Proxy listening on 127.0.0.1:{listen_port} -> 127.0.0.1:{target_port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    pairs = sys.argv[1:] or ["8002:8001", "8003:8000"]
    threads = []
    for p in pairs:
        lp, tp = [int(x) for x in p.split(":")]
        t = threading.Thread(target=serve, args=(lp, tp), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
