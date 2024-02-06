#!/bin/sh

if [ -f docs/docusaurus.config.ts ]; then
    (cd docs && npm run build)
else
    retype build docs
fi

