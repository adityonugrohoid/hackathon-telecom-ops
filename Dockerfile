FROM python:3.12-slim
WORKDIR /app

# Copy both packages (netpulse-ui imports from telecom_ops via sys.path.insert)
COPY netpulse-ui/ /app/netpulse-ui/
COPY telecom_ops/ /app/telecom_ops/

# Copy the seed pipeline + canonical CSVs, then materialize the SQLite file at
# image-build time. The agent + the data viewer tabs read /app/data/netpulse.sqlite
# at runtime; baking it into the image means a fresh container has data on cold
# start with no managed-backend dependency.
COPY scripts/build_sqlite.py /app/scripts/build_sqlite.py
COPY docs/seed-data/ /app/docs/seed-data/

RUN pip install --no-cache-dir -r /app/netpulse-ui/requirements.txt
RUN python /app/scripts/build_sqlite.py

WORKDIR /app/netpulse-ui
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
