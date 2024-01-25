#!/bin/bash

set -e
set -x
trap 'date' DEBUG

cd frontend
npm install
npm run eslint
