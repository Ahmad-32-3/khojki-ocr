"""Create or update the public Hugging Face Docker Space that hosts the pipeline API.

usage:
  set HF_TOKEN=hf_...
  set HF_USER=your-username   # optional if whoami works
  python -X utf8 scripts/deploy_hf_space.py

Needs: pip install huggingface_hub, git, git-lfs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPACE = os.environ.get("HF_SPACE", "khojki-api")
TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")

FILES = [
    "Dockerfile",
    ".dockerignore",
    "pyproject.toml",
    "README.md",
    "khojki",
    "demo",
    "site",
    "data/bank.npz",
    "data/model.json",
    "data/fonts",
    "khojki-scans/sample_khojki_script_vatiations.pdf",
    "khojki-scans/README.md",
]


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd)


def main() -> None:
    if not TOKEN:
        raise SystemExit("Set HF_TOKEN to a Hugging Face write token, then re-run.")

    from huggingface_hub import HfApi, whoami

    api = HfApi(token=TOKEN)
    user = os.environ.get("HF_USER") or whoami(token=TOKEN)["name"]
    repo_id = f"{user}/{SPACE}"
    url = f"https://{user}-{SPACE}.hf.space".replace("_", "-")  # HF mangles underscores
    # Actual Space URL pattern: https://huggingface.co/spaces/{user}/{space}
    # Runtime: https://{user}-{space}.hf.space with underscores kept as hyphens in host
    host = f"https://{user.replace('_', '-')}-{SPACE.replace('_', '-')}.hf.space"

    print(f"deploying {repo_id}")
    api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
    # README with Space YAML so HF treats it as Docker
    readme = (
        "---\n"
        "title: Khojki OCR API\n"
        "emoji: 📜\n"
        "colorFrom: yellow\n"
        "colorTo: red\n"
        "sdk: docker\n"
        "app_port: 7860\n"
        "---\n\n"
        "Docker Space that runs the Khojki OCR pipeline API for m48ahmad.com.\n"
    )

    work = Path(tempfile.mkdtemp(prefix="khojki-space-"))
    try:
        (work / "README.md").write_text(readme, encoding="utf-8")
        for rel in FILES:
            src = ROOT / rel
            if not src.exists():
                raise SystemExit(f"missing {src}")
            dest = work / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(
                    src,
                    dest,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "previews", "VOICE.md"),
                )
            else:
                shutil.copy2(src, dest)

        # Prefer the package README content under the YAML header for humans.
        pkg = (ROOT / "README.md").read_text(encoding="utf-8")
        (work / "README.md").write_text(readme + "\n" + pkg, encoding="utf-8")

        run(["git", "init"], cwd=work)
        run(["git", "lfs", "install"], cwd=work)
        run(["git", "lfs", "track", "*.npz", "*.pdf"], cwd=work)
        run(["git", "add", "-A"], cwd=work)
        run(["git", "-c", "user.email=deploy@local", "-c", "user.name=deploy", "commit", "-m", "Deploy Khojki OCR API"], cwd=work)
        remote = f"https://user:{TOKEN}@huggingface.co/spaces/{repo_id}"
        run(["git", "remote", "add", "origin", remote], cwd=work)
        run(["git", "branch", "-M", "main"], cwd=work)
        run(["git", "push", "-u", "origin", "main", "--force"], cwd=work)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print(f"pushed {repo_id}")
    print(f"space page: https://huggingface.co/spaces/{repo_id}")
    print(f"api host (set this in demo/site if different): {host}")
    print(url)


if __name__ == "__main__":
    main()
