#!/bin/sh

IMAGE=guij/jsc-tune

if ! docker image inspect $IMAGE > /dev/null 2>&1; then
  echo "Docker image not present, building it"
  make
fi

echo "START" `date` | tee -a optimizer.log

docker run -it --rm  -v ${PWD}:/work --network=host $IMAGE "$@" 2>&1 | tee -a jsc-tune.log

echo "END" `date` | tee -a jsc-tune.log
