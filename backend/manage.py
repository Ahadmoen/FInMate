#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
from datetime import datetime
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    if len(sys.argv) == 2 and sys.argv[1] == "runserver":
        default_port = os.getenv("BACKEND_PORT", "3100")
        sys.argv.append(default_port)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"{timestamp} | INFO | finmate.bootstrap | "
            f"Starting Django dev server on 127.0.0.1:{default_port}"
        )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
