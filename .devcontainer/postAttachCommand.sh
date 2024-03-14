#!/bin/bash
# Inspired by https://github.com/orgs/community/discussions/15351
gh codespace ports visibility 8000:org -c $CODESPACE_NAME
echo "gh codespace ports -c $CODESPACE_NAME" >> ~/.bashrc
cat $CODESPACE_VSCODE_FOLDER/.devcontainer/welcome
