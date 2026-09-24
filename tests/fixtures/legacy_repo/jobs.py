"""Source-only scheduler/integration fixture; do not run the job."""
import requests
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()


@scheduler.scheduled_job("cron", minute=0)
def reconcile_claims():
    response = requests.post(
        "https://notifications.example.test/api/reconciliation", json={"type": "claims"}
    )
    response.raise_for_status()
