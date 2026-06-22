"""
Standalone runner for the periodic fetch jobs (intended for cron).
Runs the two refresh steps that main.py keeps commented out:
  - fetch_id.fetch()              -> refresh Product IDs in Google Sheets
  - fetch_image.list_shop_files() -> refresh image name/link list
Run from the project root so relative paths (credentials/, Setup/.env) resolve.
"""
from datetime import datetime

import Setup.fetch_product_id_new as fetch_id
import Setup.fetch_images_name_link as fetch_image


def main():
    print(f"\n===== cron_fetch run @ {datetime.now():%Y-%m-%d %H:%M:%S} =====")
    fetch_id.fetch()
    fetch_image.list_shop_files()
    print("===== done =====")


if __name__ == "__main__":
    main()
