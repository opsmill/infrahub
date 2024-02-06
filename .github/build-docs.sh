#!/bin/sh

if [ -f docs/docusaurus.config.ts ]; then
    (cd docs && npm run build)
else
    npx retypeapp build docs
fi

