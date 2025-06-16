#!/bin/zsh
local EXTENSION_DIR="$HOME/.local/share/ulauncher/extensions/ulauncher-fw-fanctrl";

if [[ ! -e $EXTENSION_DIR ]]; then
    mkdir $EXTENSION_DIR;
fi

pnpm dlx chokidar-cli \
    '**.{py,json,png}' \
    --command "rm -rf $EXTENSION_DIR && mkdir $EXTENSION_DIR && cp -r ./* $EXTENSION_DIR && pkill -9 ulauncher";
