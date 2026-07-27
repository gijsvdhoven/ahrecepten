FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py ah_scraper.py .

# Draai elke dag om 06:00. cron ziet standaard geen environment variables die
# via `docker run -e` of compose zijn meegegeven; entrypoint.sh schrijft ze bij
# het opstarten naar /app/cron-env. `set -a` eromheen is essentieel: zonder dat
# worden de variabelen wel gezet maar niet geëxporteerd, en ziet main.py ze niet.
RUN echo "0 6 * * * root set -a; . /app/cron-env; set +a; /usr/local/bin/python /app/main.py >> /var/log/cron.log 2>&1" \
    > /etc/cron.d/trmnl-ah \
    && chmod 0644 /etc/cron.d/trmnl-ah \
    && touch /var/log/cron.log

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
