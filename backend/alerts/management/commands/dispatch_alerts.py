"""Cloud Run Job entrypoint — fires Workflow A + B for one window.

Cloud Scheduler hits the Run Job's :run endpoint 3 times a day with
the appropriate window arg. The Job runs all 3 dispatches in sequence
inside one process so we avoid the cost of 3 always-on services.

Usage:
    python manage.py dispatch_alerts PRE_MARKET
    python manage.py dispatch_alerts MID_SESSION
    python manage.py dispatch_alerts POST_MARKET --no-delay

`--no-delay` skips the 2-min and 5-min waits between sub-tasks (handy
for manual testing; default schedule keeps the delays so users see
the Top Pick before the Digest before the Position Alert).
"""
from __future__ import annotations

import logging
import time

from django.core.management.base import BaseCommand, CommandError

from alerts import services

logger = logging.getLogger(__name__)

VALID_WINDOWS = ("PRE_MARKET", "MID_SESSION", "POST_MARKET")
DIGEST_DELAY_SEC = 120   # 2 min — matches n8n 'Digest: wait 2 min'
POSITION_DELAY_SEC = 180  # 3 min more (total 5 min from start) — matches Workflow B


class Command(BaseCommand):
    help = "Fire alert Workflow A + B for one PSX window."

    def add_arguments(self, parser):
        parser.add_argument(
            "window",
            choices=VALID_WINDOWS,
            help="Which PSX window to dispatch for.",
        )
        parser.add_argument(
            "--no-delay",
            action="store_true",
            help="Skip the 2-min and 5-min waits between sub-tasks.",
        )
        parser.add_argument(
            "--skip-position",
            action="store_true",
            help="Skip the portfolio Workflow B (top pick + digest only).",
        )

    def handle(self, *args, **opts):
        window = opts["window"]
        if window not in VALID_WINDOWS:
            raise CommandError(f"Bad window: {window}")

        self.stdout.write(self.style.NOTICE(f"[{window}] dispatch_top_pick"))
        top_result = services.dispatch_top_pick(window)
        self.stdout.write(f"  top_pick: {top_result}")

        if not opts["no_delay"]:
            self.stdout.write(f"  ... waiting {DIGEST_DELAY_SEC}s before digest")
            time.sleep(DIGEST_DELAY_SEC)

        self.stdout.write(self.style.NOTICE(f"[{window}] dispatch_digest"))
        digest_result = services.dispatch_digest(window)
        self.stdout.write(f"  digest: {digest_result}")

        if opts["skip_position"]:
            self.stdout.write("  skip-position flag set — Workflow B skipped")
            return

        if not opts["no_delay"]:
            self.stdout.write(f"  ... waiting {POSITION_DELAY_SEC}s before position alerts")
            time.sleep(POSITION_DELAY_SEC)

        self.stdout.write(self.style.NOTICE(f"[{window}] dispatch_position_alerts"))
        position_result = services.dispatch_position_alerts(window)
        self.stdout.write(f"  position_alerts: {position_result}")

        self.stdout.write(self.style.SUCCESS(f"[{window}] DONE"))
