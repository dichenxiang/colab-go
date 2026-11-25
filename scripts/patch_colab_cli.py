#!/usr/bin/env python3
"""
Idempotent patch for google-colab-cli (`colab_cli/client.py`):
Google Colab's /tun/m/assign and /tun/m/unassign endpoints (or HTTP proxies in front of them)
can reject empty POST requests with HTTP 411 Length Required when no body is sent.
This patch ensures empty POST requests include `json={}` so Content-Length is set cleanly.

Run inside the same environment where `colab` is installed (e.g. WSL Ubuntu on Windows):
  python3 patch_colab_cli.py
"""
import glob
import os
import pathlib
import shutil
import subprocess
import sys


def find_client_py() -> list[pathlib.Path]:
    candidates = set()

    # 1. uv tool environment
    for pattern in [
        os.path.expanduser("~/.local/share/uv/tools/google-colab-cli/lib/python*/site-packages/colab_cli/client.py"),
        os.path.expanduser("~/.local/pipx/venvs/google-colab-cli/lib/python*/site-packages/colab_cli/client.py"),
    ]:
        for p in glob.glob(pattern):
            candidates.add(pathlib.Path(p))

    # 2. From `colab` executable shebang
    colab_bin = shutil.which("colab") or os.path.expanduser("~/.local/bin/colab")
    if colab_bin and os.path.exists(colab_bin):
        try:
            first_line = pathlib.Path(colab_bin).read_text(errors="ignore").splitlines()[0]
            if first_line.startswith("#!"):
                py_exe = first_line[2:].strip().split()[0]
                out = subprocess.check_output(
                    [py_exe, "-c", "import colab_cli.client as c; print(c.__file__)"],
                    text=True,
                ).strip()
                if out:
                    candidates.add(pathlib.Path(out))
        except Exception:
            pass

    # 3. Current Python environment
    try:
        import colab_cli.client as c
        candidates.add(pathlib.Path(c.__file__))
    except Exception:
        pass

    return sorted(p for p in candidates if p.exists())


def patch_file(path: pathlib.Path) -> str:
    txt = path.read_text(encoding="utf-8")
    marker = "colab-go-empty-post-fix"
    if marker in txt:
        return f"ALREADY_PATCHED: {path}"

    target = (
        "        response = self.session.request(\n"
        "            method, endpoint, headers=request_headers, params=params, **kwargs\n"
        "        )"
    )
    replacement = (
        f"        # {marker}: prevent HTTP 411 on empty POST requests\n"
        '        if method.upper() == "POST" and "data" not in kwargs and "json" not in kwargs and "files" not in kwargs:\n'
        '            kwargs["json"] = {}\n'
        "        response = self.session.request(\n"
        "            method, endpoint, headers=request_headers, params=params, **kwargs\n"
        "        )"
    )
    if target not in txt:
        return f"SKIPPED_TARGET_NOT_FOUND: {path}"

    path.write_text(txt.replace(target, replacement, 1), encoding="utf-8")
    return f"PATCHED_OK: {path}"


def main():
    paths = find_client_py()
    if not paths:
        print("ERROR: Could not locate colab_cli/client.py. Install google-colab-cli first.", file=sys.stderr)
        sys.exit(1)
    for p in paths:
        print(patch_file(p))


if __name__ == "__main__":
    main()
