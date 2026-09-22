#!/usr/bin/env bash

set -ex

PAGEFILE_SIZE=${1}

warn() {
    if [[ -n ${GITHUB_ACTIONS} ]]; then
        echo "::warning::${1}"
    else
        echo "WARNING: ${1}"
    fi
}

# swapon(2) needs a filesystem that can map the swap file to disk blocks.
# overlayfs (the root filesystem of containerized runners, e.g. the RISE
# riscv64 runners) and tmpfs cannot, and fail with "Invalid argument".
fs_cant_swap() {
    local fstype
    fstype=$(stat -f -c %T "$(dirname "${1}")")
    [[ ${fstype} == overlay* || ${fstype} == tmpfs ]]
}

SWAPFILE=/swapfile
if [[ ${GHA_RUNS_ON} == *namespace-profile-* ]]; then
    SWAPFILE=/namespace/scratch/swapfile
fi
# Swap is a host-wide resource; don't try to find another writable volume
# in a container, as the file may be deleted with the container while the
# kernel still uses it as swap.
if fs_cant_swap "${SWAPFILE}"; then
    warn "The path ${SWAPFILE} is on a filesystem of type $(stat -f -c %T "$(dirname "${SWAPFILE}")"), which cannot hold a swap file; skipping pagefile_size=${PAGEFILE_SIZE}"
    exit 0
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
