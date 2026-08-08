#!/usr/bin/env bash

set -ex

PAGEFILE_SIZE=${1}

SWAPFILE=/swapfile
if [[ ${GHA_RUNS_ON} == *namespace-profile-* ]]; then
    SWAPFILE=/namespace/scratch/swapfile
fi
# If there is already a swapfile, disable it and remove it
if swapon --show | grep -q "^${SWAPFILE}"; then
    sudo swapoff "${SWAPFILE}" || true
fi
[[ -f ${SWAPFILE} ]] && sudo rm -f "${SWAPFILE}"

sudo fallocate -l "${PAGEFILE_SIZE}GiB" "${SWAPFILE}"
sudo chmod 600 "${SWAPFILE}"
sudo mkswap "${SWAPFILE}"
sudo swapon "${SWAPFILE}"
