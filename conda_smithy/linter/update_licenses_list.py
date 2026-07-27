from pathlib import Path

import requests

HERE = Path(__file__).parent
LICENSES_URL = "https://raw.githubusercontent.com/spdx/license-list-data/refs/heads/main/json/licenses.json"
LICENSE_EXCEPTIONS_URL = "https://raw.githubusercontent.com/spdx/license-list-data/refs/heads/main/json/exceptions.json"
LICENSES_TXT_PATH = HERE / "licenses.txt"
LICENSE_EXCEPTIONS_TXT_PATH = HERE / "license_exceptions.txt"


def update_licenses(write: bool = True) -> list[str]:
    r = requests.get(LICENSES_URL)
    r.raise_for_status()
    ids = sorted(
        [license["licenseId"] for license in r.json()["licenses"]], key=str.lower
    )
    if write:
        LICENSES_TXT_PATH.write_text("\n".join([*ids, ""]))
    return ids


def update_license_exceptions(write: bool = True) -> list[str]:
    r = requests.get(LICENSE_EXCEPTIONS_URL)
    r.raise_for_status()
    ids = sorted(
        [license["licenseExceptionId"] for license in r.json()["exceptions"]],
        key=str.lower,
    )
    if write:
        LICENSE_EXCEPTIONS_TXT_PATH.write_text("\n".join([*ids, ""]))
    return ids


if __name__ == "__main__":
    update_licenses()
    update_license_exceptions()
