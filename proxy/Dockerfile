FROM python:3.15-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
COPY metrics.py server.py ./

USER nobody
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD ["python", "server.py", "--healthcheck"]
CMD ["python", "server.py"]
