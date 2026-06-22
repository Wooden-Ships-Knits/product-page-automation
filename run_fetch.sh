#!/bin/bash
# Wrapper so cron runs the fetch jobs from the correct directory with the venv.
# All output (and errors) are appended to cron_fetch.log in the project folder.

PROJECT_DIR="/Users/woodenship/Library/CloudStorage/GoogleDrive-web@pt-infashion.com (25-05-26 14.53)/Shared drives/WEB SERVER/LUTHFI/SAS_L/PPA"

cd "$PROJECT_DIR" || exit 1
"$PROJECT_DIR/venv/bin/python" cron_fetch.py >> "$PROJECT_DIR/cron_fetch.log" 2>&1
