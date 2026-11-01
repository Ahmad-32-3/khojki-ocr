FROM python:3.12-slim

WORKDIR /app

# System libs OpenCV and FreeType need on slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY khojki ./khojki
RUN pip install --no-cache-dir .

RUN mkdir -p data/fonts khojki-scans
COPY demo ./demo
COPY site ./site
COPY data/bank.npz data/model.json ./data/
COPY data/fonts/ ./data/fonts/
COPY khojki-scans/sample_khojki_script_vatiations.pdf ./khojki-scans/
COPY khojki-scans/README.md ./khojki-scans/

ENV HOST=0.0.0.0
ENV PORT=7860
ENV ALLOWED_ORIGINS=https://m48ahmad.com,https://www.m48ahmad.com,http://127.0.0.1:5173,http://localhost:5173

EXPOSE 7860

CMD ["python", "-X", "utf8", "demo/server.py"]
