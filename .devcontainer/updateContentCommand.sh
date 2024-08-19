#!/bin/bash

invoke demo.build demo.start
sleep 30
invoke demo.load-infra-schema demo.load-infra-data
invoke demo.stop