FROM python:3.12-slim
WORKDIR /app
COPY netpulse-ui/ /app/netpulse-ui/
COPY telecom_ops/ /app/telecom_ops/
RUN pip install --no-cache-dir -r /app/netpulse-ui/requirements.txt
WORKDIR /app/netpulse-ui
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
