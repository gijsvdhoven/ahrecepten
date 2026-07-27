#!/bin/sh
set -e

CRON_ENV=/app/cron-env

# Cron ziet de environment variables niet die via `docker run -e` of compose
# zijn meegegeven, dus schrijven we ze naar een bestand dat de cron job inleest
# (zie /etc/cron.d/trmnl-ah: die doet `set -a` zodat ze geëxporteerd worden --
# zonder dat blijven het shell-variabelen die het python-proces niet ziet).
#
# We overschrijven het bestand i.p.v. eraan toe te voegen, anders groeit het
# bij elke herstart van de container.
: > "$CRON_ENV"

for name in ICAL_URL TRMNL_WEBHOOK_URL; do
    eval "value=\${$name:-}"
    if [ -n "$value" ]; then
        echo "$name=$value" >> "$CRON_ENV"
    else
        echo "WAARSCHUWING: $name is niet gezet -- vul .env aan (zie .env.example)." >&2
    fi
done

# Laat de output van de dagelijkse cron-run meelopen in `docker compose logs`.
tail -F /var/log/cron.log 2>/dev/null &

# Bij opstarten meteen 1x draaien, zodat je niet tot 06:00 hoeft te wachten
# om te zien of het werkt. Zet RUN_ON_START=false om dit over te slaan.
if [ "${RUN_ON_START:-true}" = "true" ]; then
    echo "Initiele run bij opstarten..."
    python /app/main.py || echo "Initiele run mislukt, cron probeert het morgen om 06:00 opnieuw."
fi

cron -f
