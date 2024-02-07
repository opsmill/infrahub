#!/bin/sh

if [ -f docs/docusaurus.config.ts ]; then
    (cd docs && npm install && npm run build)
else
    npx retypeapp build docs
fi

