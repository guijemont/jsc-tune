#!/bin/sh

IMAGE=guij/opentuner

if ! docker image inspect $IMAGE > /dev/null 2>&1; then
  echo "Docker image not present, building it"
  make
fi

echo "START" `date` | tee -a opentuner_js2.log

docker run -it --rm  -v ${PWD}:/work $IMAGE "$@" 2>&1 | tee -a opentuner_js2.log

echo "END" `date` | tee -a opentuner_js2.log
