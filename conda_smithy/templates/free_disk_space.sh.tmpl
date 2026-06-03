#!/usr/bin/env bash

set -ex

FREE_DISK_SPACE=${1}

if [[ ${FREE_DISK_SPACE} == *,cache,* ]]; then
  DIRS_TO_REMOVE=(
    /opt/ghc
    /opt/hostedtoolcache
    /usr/lib/jvm
    /usr/local/.ghcup
    /usr/local/lib/android
    /usr/local/share/powershell
    /usr/share/dotnet
    /usr/share/swift
  )

  sudo rm -rf "${DIRS_TO_REMOVE[@]}"
fi

if [[ ${FREE_DISK_SPACE} == *,apt,* ]]; then
  BROWSERS="firefox google-chrome-stable microsoft-edge-stable"
  BROWSERS_TO_REMOVE=$(dpkg --get-selections $BROWSERS 2>/dev/null | awk '{print $1}')
  sudo apt-get remove --purge -y $BROWSERS_TO_REMOVE

  sudo apt-get autoremove -y >& /dev/null
  sudo apt-get autoclean -y >& /dev/null
fi

if [[ ${FREE_DISK_SPACE} == *,docker,* ]]; then
  sudo docker image prune --all --force
fi

df -h
