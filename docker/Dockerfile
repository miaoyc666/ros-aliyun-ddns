FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt constraints.txt /app/
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt -c constraints.txt

COPY app.py docker/healthcheck.py /app/

RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 6180

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD ["python", "healthcheck.py"]

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:6180", "app:app"]
