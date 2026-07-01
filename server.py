#!/usr/bin/env python3
"""World Tree Proxy v2 - Flask, streaming-ready, error-resilient"""
import os, json
from flask import Flask, request, Response, send_from_directory, jsonify
from flask_cors import CORS
import requests

OLLAMA = "http://localhost:11434"
MODEL  = "deepseek-r1:7b"
PORT   = 3001
BASE   = os.path.dirname(os.path.abspath(__file__ or "."))

app = Flask(__name__, static_folder=None)
CORS(app)

# --- Static files ---
@app.route("/")
def index():
    return send_from_directory(BASE, "text.html")

    return send_from_directory(BASE, path)

# --- Health check ---
@app.route("/api/ping")
def ping():
    return jsonify({"ok": True, "ollama": OLLAMA, "model": MODEL})

# --- Core: chat proxy ---
@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        body = request.get_json(force=True)
    except Exception as e:
        return jsonify({"error": f"Invalid JSON body: {e}"}), 400

    body["model"] = MODEL
    stream = body.get("stream", False)

    try:
        ollama_resp = requests.post(
            f"{OLLAMA}/v1/chat/completions",
            json=body,
            stream=True,
            timeout=(10, 300),
        )
    except requests.ConnectionError:
        return jsonify({"error": f"Cannot connect to Ollama ({OLLAMA}) - is ollama serve running?"}), 502
    except requests.Timeout:
        return jsonify({"error": "Ollama request timed out"}), 504
    except Exception as e:
        return jsonify({"error": f"Request failed: {e}"}), 502

    if not ollama_resp.ok:
        err = ""
        try: err = ollama_resp.text[:500]
        except: pass
        return jsonify({"error": f"Ollama {ollama_resp.status_code}: {err}"}), 502

    if stream:
        def generate():
            try:
                for chunk in ollama_resp.iter_content(chunk_size=None):
                    if chunk:
                        yield chunk
            except Exception as e:
                try: yield json.dumps({"error": str(e)}).encode()
                except: pass
        return Response(generate(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    else:
        try:
            chunks = []
            for chunk in ollama_resp.iter_content(chunk_size=None):
                if chunk: chunks.append(chunk)
            raw = b"".join(chunks)
            data = json.loads(raw)
            return jsonify(data)
        except json.JSONDecodeError:
            text = raw.decode("utf-8", errors="replace")[:1000]
            return jsonify({"error": "Ollama returned non-JSON data", "raw": text}), 502
        except Exception as e:
            return jsonify({"error": f"Response parsing failed: {e}"}), 500

# --- Global error handlers ---
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found", "path": request.path}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(Exception)
def all_exceptions(e):
    return jsonify({"error": f"Server error: {e}"}), 500

# --- Main ---
if __name__ == "__main__":
    os.chdir(BASE)
    print(f"\n{'='*50}")
    print(f"  World Tree Proxy v2 (Flask)")
    print(f"  http://localhost:{PORT}  ->  {OLLAMA}")
    print(f"  Model: {MODEL}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)