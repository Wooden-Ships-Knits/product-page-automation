"""
drive_sync.py — fetch IM Master workbook(s) from Google Drive to local disk.

Purpose
-------
On the Mac, the IM Master .xlsx is reached through the Google Drive for Desktop
mount. On a headless Debian VM / inside Docker there is NO such mount, so the
hardcoded path in ProductInfo.get_im_path() would not exist.

This module downloads the needed IM workbook via the **Drive API** (using the
existing service account) and writes it to the *exact* local path get_im_path()
expects — so the existing PPA code reads it from disk, UNCHANGED. Fully additive:
no existing file is modified.

Auth
----
Reuses the same service-account key the Sheets code already uses. That account
must be a MEMBER (Viewer is enough) of the 'PTIF SERVER' Shared Drive.
No OAuth / browser flow / token refresh to babysit.

Usage
-----
    python drive_sync.py --check
        Verify the service account can see the Shared Drive and list the
        IM Master workbooks it can find (run this first, once access is granted).

    python drive_sync.py --ensure "/absolute/path/to/F26 IM MASTER.xlsx"
        Download the workbook whose filename matches the path's basename to that
        exact local path (creating parent folders). No-op if already present.
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# The IM workbooks live under this Shared Drive. get_im_path() builds paths like
#   .../PTIF SERVER/Collection/<year season>/IM/<code> IM MASTER.xlsx
# so we resolve the file by walking that folder chain, NOT by bare filename
# (the Drive has hundreds of similarly-named copies).
SHARED_DRIVE_NAME = "PTIF SERVER"


def _key_file() -> str:
    """Locate the service-account key (same one the rest of the project uses)."""
    env = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if env and Path(env).exists():
        return env
    matches = glob.glob("credentials/*.json")
    if not matches:
        raise FileNotFoundError("No service-account key found under credentials/.")
    return matches[0]


def _drive():
    creds = Credentials.from_service_account_file(_key_file(), scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def _shared_drive_id(svc, name: str = SHARED_DRIVE_NAME) -> str:
    """Resolve the Shared Drive's id by its name."""
    resp = svc.drives().list(q=f"name = '{name}'", fields="drives(id, name)").execute()
    drives = resp.get("drives", [])
    if not drives:
        raise FileNotFoundError(
            f"Shared Drive '{name}' not visible to the service account. "
            f"Confirm it was added as a member."
        )
    return drives[0]["id"]


def _child(svc, parent_id: str, name: str, drive_id: str, want_folder=None):
    """List children of `parent_id` named `name` within the given shared drive.
    want_folder=True restricts to folders, False to non-folders, None to either.
    """
    q = f"name = '{name}' and trashed = false and '{parent_id}' in parents"
    if want_folder is True:
        q += " and mimeType = 'application/vnd.google-apps.folder'"
    elif want_folder is False:
        q += " and mimeType != 'application/vnd.google-apps.folder'"
    resp = svc.files().list(
        q=q,
        corpora="drive",
        driveId=drive_id,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        fields="files(id, name, mimeType, modifiedTime, size)",
    ).execute()
    return resp.get("files", [])


def _rel_parts_from_local(local_path: str):
    """Map a get_im_path()-style local path to its location inside the Shared
    Drive: always Collection / <season> / IM / <file>.

    Uses only the LAST THREE path segments (season, 'IM', filename) that
    get_im_path() always emits, so it works no matter the local base dir — the
    Mac's Drive mount OR a Debian cache dir (IM_COLLECTION_BASE).
    """
    parts = [seg for seg in local_path.replace("\\", "/").split("/") if seg]
    if len(parts) < 3:
        raise ValueError(f"Path too short to locate IM workbook: {local_path!r}")
    season_year, im_folder, filename = parts[-3], parts[-2], parts[-1]
    return ["Collection", season_year, im_folder, filename]


def _pick_im_workbook(svc, folder_id: str, drive_id: str, preferred_name: str):
    """From a season's IM folder, return the IM Master workbook.

    The IM folder placement is consistent; filenames are less so. Preference:
    (1) exact `preferred_name`; (2) the single Excel workbook present; else raise
    with the folder contents so an ambiguity is diagnosable, never guessed.
    """
    resp = svc.files().list(
        q=f"'{folder_id}' in parents and trashed = false "
          f"and mimeType != 'application/vnd.google-apps.folder'",
        corpora="drive",
        driveId=drive_id,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        fields="files(id, name, mimeType, modifiedTime, size)",
    ).execute()
    files = resp.get("files", [])
    workbooks = [
        f for f in files
        if f["name"].lower().endswith((".xlsx", ".xls"))
        and "@syno" not in f["name"].lower()          # skip Synology metadata junk
        and "im master" in f["name"].lower()
    ]
    for f in workbooks:                                # (1) exact name
        if f["name"].casefold() == preferred_name.casefold():
            return f
    if len(workbooks) == 1:                            # (2) the only candidate
        return workbooks[0]
    if not workbooks:
        raise FileNotFoundError(
            f"No IM Master workbook in the IM folder (wanted '{preferred_name}'). "
            f"Files present: {[f['name'] for f in files]}"
        )
    raise FileNotFoundError(
        f"Multiple IM Master workbooks in the IM folder; can't disambiguate "
        f"'{preferred_name}': {[f['name'] for f in workbooks]}"
    )


def resolve_by_path(svc, rel_parts, drive_name: str = SHARED_DRIVE_NAME):
    """Walk the folder chain (all parts except the last) from the Shared Drive
    root, then pick the IM Master workbook inside the final IM folder."""
    drive_id = _shared_drive_id(svc, drive_name)
    parent = drive_id
    walked = []
    *folders, filename = rel_parts
    for part in folders:
        matches = _child(svc, parent, part, drive_id, want_folder=True)
        if not matches:
            raise FileNotFoundError(
                f"folder '{part}' not found under {drive_name}/" + "/".join(walked)
            )
        parent = matches[0]["id"]
        walked.append(part)
    return _pick_im_workbook(svc, parent, drive_id, filename)


def check() -> None:
    """Confirm access and list IM Master workbooks the service account can see."""
    svc = _drive()
    print(f"Auth OK using key: {_key_file()}")
    resp = svc.files().list(
        q="name contains 'IM MASTER' and trashed = false",
        corpora="allDrives",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        fields="files(id, name, driveId, modifiedTime, size)",
        orderBy="name",
    ).execute()
    files = resp.get("files", [])
    if not files:
        print("No 'IM MASTER' files visible. Is the service account a member of")
        print("the 'PTIF SERVER' Shared Drive yet?")
        return
    print(f"Visible IM Master workbooks ({len(files)}):")
    for f in files:
        size = f.get("size", "?")
        print(f"  - {f['name']}   id={f['id']}   modified={f.get('modifiedTime')}   bytes={size}")


def _download(svc, file_id: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.FileIO(dest, "wb")
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    buf.close()


def ensure_local(local_path: str, force: bool = False) -> str:
    """Ensure the IM workbook for `local_path` exists on disk; download if missing.

    Resolves the Drive file by walking the folder chain embedded in `local_path`
    (Collection/<season>/IM/<file>), so the correct workbook is found even though
    the Drive holds many similarly-named copies. Writes to the exact `local_path`
    get_im_path() expects, so the existing PPA code reads it unchanged.
    """
    dest = Path(local_path)
    if dest.exists() and not force:
        return str(dest)

    rel_parts = _rel_parts_from_local(local_path)
    svc = _drive()
    record = resolve_by_path(svc, rel_parts)
    _download(svc, record["id"], dest)
    print(f"Downloaded {'/'.join(rel_parts)} (id={record['id']}) -> {dest}")
    return str(dest)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Sync IM Master workbook(s) from Drive.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="verify access + list IM files")
    g.add_argument("--ensure", metavar="LOCAL_PATH", help="download workbook to this exact path")
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    args = ap.parse_args()

    if args.check:
        check()
    else:
        ensure_local(args.ensure, force=args.force)
