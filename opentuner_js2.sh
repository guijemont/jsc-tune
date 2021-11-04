#!/bin/sh

IMAGE=guij/opentuner

if ! docker image inspect $IMAGE > /dev/null 2>&1; then
  echo "Docker image not present, building it"
  make
fi

docker run -it --rm  -v ${PWD}:/work $IMAGE "$@"
