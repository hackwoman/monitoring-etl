#!/usr/bin/env python3
"""Demo: generate sample logs to test the pipeline."""
import json
import time
import random
from datetime import datetime, timezone

SERVICES = ["payment-service", "order-service", "user-service", "inventory-service"]
LEVELS = ["info", "info", "info", "info", "warn", "error"]
HOSTS = ["host-01", "host-02", "host-03"]

MESSAGES = {
    "info": [
        "Request processed successfully",
        "Cache hit for key: user:{id}",
        "Health check passed",
        "Scheduled task completed",
        "Connection pool refreshed",
    ],
    "warn": [
        "Slow query detected: 850ms",
        "Memory usage above 80%",
        "Retry attempt 2/3",
        "Connection pool nearing limit",
    ],
    "error": [
        "ConnectionTimeout: upstream service unavailable",
        "NullPointerException in OrderProcessor",
        "Database connection refused",
        "Authentication failed for user",
    ],
}


def generate_log():
    level = random.choice(LEVELS)
    service = random.choice(SERVICES)
    host = random.choice(HOSTS)
    msg = random.choice(MESSAGES[level])

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "service_name": service,
        "host_name": host,
        "message": msg,
        "trace_id": f"trace-{random.randint(100000, 999999)}",
        "span_id": f"span-{random.randint(100000, 999999)}",
    }


if __name__ == "__main__":
    print("Generating sample logs (Ctrl+C to stop)...")
    count = 0
    while True:
        log = generate_log()
        print(json.dumps(log))
        count += 1
        if count % 100 == 0:
            print(f"Generated {count} logs...", flush=True)
        time.sleep(random.uniform(0.01, 0.1))
