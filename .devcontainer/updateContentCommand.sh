#!/bin/bash

invoke demo.build demo.start
sleep 30
invoke demo.load-infra-schema
sleep 30
invoke demo.load-infra-data
invoke demo.stop