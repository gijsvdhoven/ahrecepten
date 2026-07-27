#!/bin/sh
set -e

# Zet alle container env vars in /etc/environment zodat de cron job ze kan lezen
printenv | grep -E '^(ICAL_URL|TRMNL_WEBHOOK_URL)=' >> /etc/environment

# Bij opstarten meteen 1x draaien, zodat je niet tot 06:00 hoeft te wachten
# om te zien of het werkt. Zet RUN_ON_START=false om dit over te slaan.
if [ "${RUN_ON_START:-true}" = "true" ]; then
    echo "Initiele run bij opstarten..."
    python /app/main.py || echo "Initiele run mislukt, cron probeert het morgen om 06:00 opnieuw."
fi

cron -f
