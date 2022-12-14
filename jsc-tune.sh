#!/bin/bash
#
# Copyright (C) 2022 Igalia S.L.
#
# This file is part of jsc-tune.
#
# Jsc-tune is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# Jsc-tune is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# jsc-tune. If not, see <https://www.gnu.org/licenses/>.

IMAGE=guijemont/jsc-tune
CONTAINER=jsc-tune
VOLUME=jsc-tune-`id -un`
JSC_TUNE_DIR=$(realpath $(dirname ${BASH_SOURCE[0]}))

eval "OPTIONS=(`getopt -q -o i:,o:,h --long ssh-id:,output-dir:,benchmark-local-path:,help -- "$@"`)"
optidx=0

ssh_id=
help=no
benchmark_from=
output_dir="./jsc-tune-results"
while [ "${OPTIONS[optidx]}" != "--" ]; do
  case "${OPTIONS[optidx]}" in
    -i|--ssh-id) ssh_id=${OPTIONS[++optidx]} ;;
    -o|--output-dir) output_dir=${OPTIONS[++optidx]} ;;
    --benchmark-local-path) benchmark_from="${OPTIONS[++optidx]}" ;;
    -h|--help) help=yes ;;
    --) break ;;
    *) echo "Problem when parsing options!"; exit 1 ;;
  esac
  optidx=$((optidx+1))
done

ssh_id_file=${ssh_id##*/}
if [ "${ssh_id}" ]; then
  ssh_id=$(realpath "${ssh_id}")
fi


output_dir=$(realpath "${output_dir}")
mkdir -p "${output_dir}"

DOCKER_RUN_ARGS=" -v ${JSC_TUNE_DIR}:/jsc-tune"
APP_ARGS=

# $ssh_id can be empty if we're just calling with --help
if [ "${ssh_id}" ]; then
  DOCKER_RUN_ARGS+=" -v ${ssh_id}:/jsc-tune-data/ssh/${ssh_id_file}"
  APP_ARGS+=" -i /jsc-tune-data/ssh/${ssh_id_file}"
fi
DOCKER_RUN_ARGS+=" -v ${output_dir}:/jsc-tune-data/output"
if [ -f ${HOME}/.ssh/known_hosts ]; then
  DOCKER_RUN_ARGS+=" -v ${HOME}/.ssh/known_hosts:/work/.ssh/known_hosts"
else
  DOCKER_RUN_ARGS+=" -v ${VOLUME}:/work"
fi
if [ "${SSH_AUTH_SOCK}" ]; then
  sock_dir=$(dirname ${SSH_AUTH_SOCK})
  DOCKER_RUN_ARGS+=" -v ${sock_dir}:${sock_dir}"
  DOCKER_RUN_ARGS+=" -e SSH_AUTH_SOCK=${SSH_AUTH_SOCK}"
fi
DOCKER_RUN_ARGS+=" --user `id -u`:`id -g`"
APP_ARGS+=" -o /jsc-tune-data/output"


## manage fake /etc/passwd

passwd_file=`mktemp`
echo "`id -un`:x:`id -u`:`id -g`:`id -un`:/work:/bin/sh" > $passwd_file
DOCKER_RUN_ARGS+=" -v $passwd_file:/etc/passwd"

check_and_create_volume() {
  if [ ! -f ${HOME}/.ssh/known_hosts ]; then
    if ! docker volume inspect "${VOLUME}" > /dev/null 2>&1; then
      echo "Docker volume not present, creating it"
      docker volume create "${VOLUME}"
    fi
  fi
}

if  [ "${benchmark_from}" ]; then
  benchmark_from=$(realpath "${benchmark_from}")
  DOCKER_RUN_ARGS+=" -v ${benchmark_from}:/jsc-tune-data/benchmark"
  APP_ARGS+=" --benchmark-local-path /jsc-tune-data/benchmark"
fi

get_help() {
  docker run --rm ${DOCKER_RUN_ARGS} $IMAGE --help
}

if [ "$help" == "yes" ]; then
  get_help
  exit
fi

check_and_create_volume

docker run --rm -it ${DOCKER_RUN_ARGS} --network=host ${IMAGE} "$@" ${APP_ARGS}

rm -f $passwd_file
