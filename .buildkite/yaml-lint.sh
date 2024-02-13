#!/bin/bash

set -e
set -x
trap 'date' DEBUG

pip install yamllint==1.33.0
yamllint .
