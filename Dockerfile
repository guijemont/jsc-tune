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

FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update  && apt-get upgrade -y && apt-get install -y \
        openssh-client \
        && apt-get clean && rm -rf /var/lib/apt/lists/*


ENV PIP_ROOT_USER_ACTION=ignore

RUN pip install --no-cache-dir --no-warn-script-location --upgrade pip

RUN pip install --no-cache-dir --no-warn-script-location scikit-optimize==0.9.0

RUN pip install --no-cache-dir --no-warn-script-location matplotlib==3.5.3

RUN mkdir /matplotlib-tmp && chmod 777 /matplotlib-tmp
ENV MPLCONFIGDIR=/matplotlib-tmp

WORKDIR /work

ENTRYPOINT [ "python", "-u", "/jsc-tune/jsc-tune.py" ]
