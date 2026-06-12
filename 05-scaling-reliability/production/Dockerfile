# Stage 1: Builder
FROM python:3.11-slim AS builder
WORKDIR /app
COPY 05-scaling-reliability/production/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim AS runtime
RUN groupadd -r appuser && useradd -r -g appuser appuser
WORKDIR /app
COPY --from=builder /root/.local /home/appuser/.local
COPY 05-scaling-reliability/production/app.py .
RUN mkdir -p /app/utils
COPY utils/mock_llm.py /app/utils/mock_llm.py
RUN chown -R appuser:appuser /app
USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
