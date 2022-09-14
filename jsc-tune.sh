#!/bin/bash

IMAGE=guij/jsc-tune
CONTAINER=jsc-tune
JSC_TUNE_DIR=$(realpath $(dirname ${BASH_SOURCE[0]}))

eval "OPTIONS=(`getopt -q -o i: --long ssh-id:,benchmark-local-path:,help -- "$@"`)"
optidx=0

ssh_id=
help=no
benchmark_from=
while [ "${OPTIONS[optidx]}" != "--" ]; do
  case "${OPTIONS[optidx]}" in
    -i|--ssh-id) ssh_id=${OPTIONS[++optidx]} ;;
    --benchmark-local-path) benchmark_from="${OPTIONS[++optidx]}" ;;
    --help) help=yes ;;
    --) break ;;
    *) echo "Problem when parsing options!"; exit 1 ;;
  esac
  optidx=$((optidx+1))
done

ssh_id_file=${ssh_id##*/}
ssh_id_path=$(realpath $(dirname "${ssh_id}"))

DOCKER_RUN_ARGS=" -v ${JSC_TUNE_DIR}:/jsc-tune -v ${PWD}:/work -v ${ssh_id_path}:/jsc-tune-data/ssh"
APP_ARGS=

check_and_build_image() {
  if ! docker image inspect $IMAGE > /dev/null 2>&1; then
    echo "Docker image not present, building it"
    docker build --build-arg uid=`id -u` --build-arg gid=`id -g` --tag guij/jsc-tune "${JSC_TUNE_DIR}" || exit 1
  fi
}

if  [ "${benchmark_from}" ]; then
  benchmark_from=$(realpath "${benchmark_from}")
  DOCKER_RUN_ARGS+=" -v ${benchmark_from}:/jsc-tune-data/benchmark"
  APP_ARGS+=" --benchmark-local-path /jsc-tune-data/benchmark"
fi

get_help() {
  check_and_build_image
  docker run --rm ${DOCKER_RUN_ARGS} $IMAGE --help
}

if [ "$help" == "yes" ]; then
  get_help
  exit
fi

if [ x"$ssh_id" == x"" ]; then
  echo "Invalid command line parameters: missing ssh key"
  get_help
  exit 1
fi

check_and_build_image

docker run --rm  ${DOCKER_RUN_ARGS} --network=host ${IMAGE} "$@" -i "/jsc-tune-data/ssh/${ssh_id_file}" ${APP_ARGS}
