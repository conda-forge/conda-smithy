#!/bin/bash

# Hit https://spdx.org/licenses/
# Capture first table
# Extract code entries from table
wget -q -O - https://spdx.org/licenses/ |  sed '/<table/,/<\/table>/!d;/<\/table>/q' | awk -- 'BEGIN{FS=">";RS="</code"};/<code/{print $NF}'

