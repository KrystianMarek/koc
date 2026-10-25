#!/bin/bash

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# ROBOT_IP comes from the git-ignored .local/env; shellcheck cannot follow it.
# shellcheck disable=SC1091
source "${script_dir}/.local/env"

# Explicit target: the robot deployment dir (NOT the local dir name).
ROBOT_DIR="rpi_lego_robot"

src_dir="${script_dir}/"
# shellcheck disable=SC2153  # ROBOT_IP assigned in .local/env
dst_dir="pi@${ROBOT_IP}:/home/pi/${ROBOT_DIR}"

rsync -ah --progress --delete \
    --exclude '.git' \
    --exclude '*.pyc' \
    --exclude '__pycache__' \
    --exclude '.venv' \
    --exclude '.local' \
    --exclude '.beads' \
    --exclude '.claude' \
    --exclude '.factory' \
    --exclude '.codegraph' \
    --exclude 'external' \
    --exclude 'testing' \
    --exclude 'doc' \
    --exclude 'pictures' \
    --exclude 'dependencies/ncappzoo' \
    --exclude 'dependencies/ncsdk/docs' \
    --exclude 'dependencies/ncsdk/examples' \
    "$src_dir" "$dst_dir"
