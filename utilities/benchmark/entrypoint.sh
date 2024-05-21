#!/bin/sh

READ_IOPS_LIMIT=5000 # neo4j requirements
WRITE_IOPS_LIMIT=5000
RAM_LIMIT=7000 # 8 GB
SINGLETHREAD_PERF_LIMIT=2000 # around 4000 on M2 Pro and CI runners https://www.cpubenchmark.net/singleThread.html

echo "Running Disk IOPS benchmark... hold on"

fio --randrepeat=1 --ioengine=libaio --direct=1 --gtod_reduce=1 --name=test --filename=randomrw.fio --bs=4k --iodepth=64 --size=128M --readwrite=randrw --rwmixread=75 --output=fio_results.json --output-format=json

READ_IOPS=$(printf "%.0f" $(jq '.jobs[0].read.iops' fio_results.json))
WRITE_IOPS=$(printf "%.0f" $(jq '.jobs[0].write.iops' fio_results.json))

echo "Running CPU/Memory benchmark... hold on"

TERM=dumb pt_linux -d 1 -r 1 -i 1 >/dev/null 2>/dev/null

TOTAL_RAM=$(yq .SystemInformation.Memory results_cpu.yml)
SINGLETHREAD_PERF=$(printf "%.0f" $(yq .Results.CPU_SINGLETHREAD results_cpu.yml))

NC='\033[0m'
RED='\033[0;31m'
GREEN='\033[0;32m'

echo ""
echo "Benchmark results:"
echo ""

[ $TOTAL_RAM -lt $RAM_LIMIT ] && echo -n $RED || echo -n $GREEN
echo -n "Memory: ${TOTAL_RAM} MB - Required: ${RAM_LIMIT} MB "
[ $TOTAL_RAM -lt $RAM_LIMIT ] && echo ": KO" || echo ": OK"

[ $SINGLETHREAD_PERF -lt $SINGLETHREAD_PERF_LIMIT ] && echo -n $RED || echo -n $GREEN
echo -n "CPU Perf: ${SINGLETHREAD_PERF} - Required: ${SINGLETHREAD_PERF_LIMIT} "
[ $SINGLETHREAD_PERF -lt $SINGLETHREAD_PERF_LIMIT ] && echo ": KO" || echo ": OK"

[ $READ_IOPS -lt $READ_IOPS_LIMIT ] && echo -n $RED || echo -n $GREEN
echo -n "Disk Read IOPS: ${READ_IOPS} - Required: ${READ_IOPS_LIMIT} "
[ $READ_IOPS -lt $READ_IOPS_LIMIT ] && echo ": KO" || echo ": OK"

[ $WRITE_IOPS -lt $WRITE_IOPS_LIMIT ] && echo -n $RED || echo -n $GREEN
echo -n "Disk Write IOPS: ${WRITE_IOPS} - Required: ${WRITE_IOPS_LIMIT} "
[ $WRITE_IOPS -lt $WRITE_IOPS_LIMIT ] && echo ": KO" || echo ": OK"

echo $NC
echo "Benchmark completed..."
