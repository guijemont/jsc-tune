#!/usr/bin/env -S python3 -u
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

import skopt

from scipy.stats import gmean, tmean, tvar
import numpy as np
import subprocess
import json
import argparse
from collections import namedtuple
from skopt.plots import plot_convergence, plot_objective
from datetime import datetime
from pathlib import Path
import logging
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from random import random
import shlex


Parameter = namedtuple('Parameter', ('name', 'range', 'default'))
parameters = (Parameter('maximumFunctionForCallInlineCandidateBytecodeCost', (50, 180), 77),
              Parameter('maximumOptimizationCandidateBytecodeCost', (65, 150000), 42403),
              Parameter('maximumFunctionForClosureCallInlineCandidateBytecodeCost', (50, 150), 68),
              Parameter('maximumInliningCallerBytecodeCost', (500, 15000), 9912),
              Parameter('maximumInliningDepth', (2,8), 8),
              Parameter('maximumInliningRecursion', (1,5), 3),
             )



parser = argparse.ArgumentParser()
parser.add_argument('-r', '--remote', required=True,
                    help='host or user@host to pass to ssh to access remote host')
parser.add_argument('-i', '--ssh-id', required=False, default=None,
                    help="ssh identity file to use to connect to remote host (needs to be passwordless)")
parser.add_argument('-e', '--exec-path', type=str,
                    help="path of the executable with which to run the benchmark on the remote host (default: typically either \"jsc\" or \"cog\" depending on the benchmark (assuming it is in $PATH)")
parser.add_argument('-n', '--n-calls', type=int, default=75,
                    help="how many times to run benchmark")
parser.add_argument('-p', '--pre-run', type=int, default=5,
                    help="How many times to initially run benchmark to calculate variance")
parser.add_argument('-o', '--output-dir', type=str, default="./jsc-tune-results",
                    help="Where to output everything we generate")
parser.add_argument('-g', '--dump-graphs', action='store_true',
                    help="Save graphics")
parser.add_argument('--repeats', type=int, default=5,
                    help="How many times to run each config (apart from preruns)")
parser.add_argument('--previous-results', type=str, default=[], action='append',
                    help="PKL file containing previous results for this exact configuration to take into account")
parser.add_argument('--initial-point-generator', default="random")
parser.add_argument('--initial-points', type=int, default=10,
                    help="how many random points to evaluate before using estimator")
parser.add_argument('--benchmark-local-path', type=str, default=None,
                    help="Path where the benchmark can be found locally to copy it to the remote host. If not provided, we're assuming that the benchmark is already deployed on the remote host.")
parser.add_argument('--benchmark-remote-path', type=str, default="JetStream2",
        help="Path where the benchmark is installed on the remote host. If `--benchmark-local-path` is also specified, copy the benchmark to that directory on the remote host.")
# Note -b / --benchmark option added after benchmark definitions


class __is_dropbear():
    is_dropbear = None
    def __init__(self):
        if self.is_dropbear is None:
            res = subprocess.run(["ssh", "-V"], capture_output=True, check=True, text=True)
            self.is_dropbear = "Dropbear" in res.stderr

def is_dropbear():
    res = __is_dropbear().is_dropbear
    return  res

class prepare_ssh_key():
    has_run = False
    def __init__(self, logger, ssh_id):
        if self.has_run:
            return
        if is_dropbear():
            # we need to convert ssh key to dropbear format
            id_path = Path(ssh_id)
            dropbear_id_path = Path(f"{id_path}.dropbear")
            cmd =  f"dropbearconvert openssh dropbear {id_path} {dropbear_id_path}"
            subprocess.run(shlex.split(cmd), check=True)

        self.has_run = True


class JSCBenchmark:
    benchmarks = {}
    def __init__(self, host, repeats, parameters, benchmark_path, ssh_id=None, exec_path=None):
        self._host = host
        self._repeats = repeats
        self._parameters = parameters
        self._ssh_id = ssh_id
        self._benchmark_path = benchmark_path
        self.logger = logging.getLogger(f"jsc-tune/{self.name}")
        if exec_path is None:
            self._exec_path = self.default_exec
        else:
            self._exec_path = exec_path

    @classmethod
    def register(klass, benchmark_class):
        klass.benchmarks[benchmark_class.name] = benchmark_class

    def score(self, out, errs):
        raise RuntimeError("Not implemented")

    def benchmark_command(self, env_string):
        raise RuntimeError("Not implemented")

    def run(self, arguments):
        assert len(arguments) == len(self._parameters)
        env = dict((self._parameters[i].name, arg) for i, arg in enumerate(arguments))
        env_string = " ".join(f"JSC_{k}={v}" for k,v in env.items())

        ssh_opts = f"-i {self._ssh_id}" if self._ssh_id else ""

        cmd = f'ssh {ssh_opts} {self._host} "{self.benchmark_command(env_string)}"'

        def __run():
            for i in range(3):
                proc = subprocess.run(cmd, shell=True, text=True, capture_output=True)
                if proc.returncode == 0:
                    return self.score(proc.stdout, proc.stderr)

            raise RuntimeError(f"Command \"{cmd}\" failed 3 times.\nreturn value: {proc.returncode}\nstderr:\n{proc.stderr}\nstdout:\n{proc.stdout}\n")

        try:
            return np.mean([__run() for _ in range(self._repeats)])
        except RuntimeError as e:
            self.logger.warning(f"error while running configuration {arguments}, returning arbitrary large value: {e}\n")
            # Note: using inf, nan or sys.float_info.max ends up failing
            # gp_minimize, 1e100 seems to work and should be "big enough" for most benchmarks
            return 1e100

    def preruns(self, n):
        default_arguments =  [p.default for p in self._parameters]
        scores = [self.run(default_arguments) for _ in range(n)]
        return (tmean(scores), tvar(scores))

class JetStream2(JSCBenchmark):
    name = 'JetStream2'
    default_exec = 'jsc'
    def benchmark_command(self, env_string):
        return f'cd {self._benchmark_path}; {env_string} {self._exec_path} watch-cli.js'

    def score(self, out, errs):
        def __parse(s, errs=None):
            for line in s.splitlines():
                if line.startswith('{'):
                    return json.loads(line)
            raise RuntimeError(f"Could not parse JetStream2 output:\n{s}\nstderr:\n{errs}\n")
        json_res = __parse(out, errs)
        l = [test['metrics']['Score']['current'][0] for test in json_res['JetStream2.0']['tests'].values()]
        # we're minimizing, but interested in highest score, hence the '-'
        return -gmean(l)

JSCBenchmark.register(JetStream2)

class MockBenchmark(JSCBenchmark):
    name = 'MockBenchmark'
    default_exec = 'jsc'
    def run(self, arguments):
        def addnoise(val):
            if val == 0:
                return .6 * random() - .3
            margin = .03 * val
            return val + random() * margin * 2 - margin

        assert type(arguments) is list, f"arguments of unexpected type {type(arguments)}: {arguments}"
        scores = [abs(addnoise(p.default - arguments[i])) for i, p in enumerate(self._parameters)]
        ret = gmean(scores) + random() * 6 - 3
        return ret

JSCBenchmark.register(MockBenchmark)

parser.add_argument('-b', '--benchmark', type=str, default="JetStream2",
                    help=f"Which benchmark to use ({list(JSCBenchmark.benchmarks.keys())}). Default is JetStream2")

def save_results(logger, options, output_dir, res, nowStr):
    if options.dump_graphs:
        logger.info(f"Dumping graphs in {output_dir / nowStr}-convergence.png and {output_dir / nowStr}-objective.png.")
        fig = plot_convergence(res).get_figure()
        fig.savefig(output_dir / f"{nowStr}-convergence.png")
        fig = plot_objective(res, dimensions=[p.name for p in parameters])[0][0].get_figure()
        fig.savefig(output_dir / f"{nowStr}-objective.png")
    logger.info(f"Saving optimization data to {output_dir / nowStr}-dump.pkl")
    skopt.dump(res, output_dir / f"{nowStr}-dump.pkl", store_objective=False)
    result = { "parameters": dict(((p.name, int(res.x[i])) for i, p in enumerate(parameters))),
               "score": abs(float(res.fun)) }
    result_path = output_dir / f"{nowStr}-result.json"
    logger.info(f"Saving results to {result_path}")
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)


def prepare_output(options):
    output_dir = Path(options.output_dir)
    output_dir.mkdir(exist_ok=True)
    return output_dir

Coordinates = namedtuple('Coordinates', ('x', 'y'))
def filter_in_bounds(xvals, yvals, parameters):
    assert(len(xvals) == len(yvals))
    res_x = []
    res_y = []
    def in_range(x, range_):
        return x >= range_[0] and x <= range_[1]
    def in_bounds(x):
        assert(len(x) == len(parameters))
        for t, p in zip(x, parameters):
            if not in_range(t, p.range):
                return False
        return True

    for x,y in zip(xvals, yvals):
        if in_bounds(x):
            res_x.append(x)
            res_y.append(y)
    return Coordinates(res_x, res_y)


class LogRedirect(object):
    def __init__(self, name, level):
        self.logger = logging.getLogger(name)
        self.level = level

    def write(self, buf):
        lines = (l.rstrip() for l in buf.rstrip().splitlines())
        for line in lines:
            self.logger.log(self.level, line)

    def flush(self):
        pass

if __name__ == '__main__':
    nowStr = datetime.now().strftime('%Y-%m-%d-%H%M%S')
    options = parser.parse_args()
    output_dir = prepare_output(options)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
                        handlers=[logging.FileHandler(output_dir / f"{nowStr}.log"),
                                  logging.StreamHandler()])

    logger = logging.getLogger("jsc-tune")
    logger.debug(f"options: {options}")

    if options.ssh_id:
        prepare_ssh_key(logger, options.ssh_id)
        if is_dropbear():
            options.ssh_id = f"{options.ssh_id}.dropbear"
    # Ensure we add the remote host key to known_hosts if needed, before we run ssh in an uninteractive way.
    ssh_opts = f"-i {options.ssh_id}" if options.ssh_id else ""
    cmd = f"ssh {ssh_opts} {options.remote} true"
    subprocess.run(shlex.split(cmd), check=True)

    if options.benchmark_local_path:
        logger.info(f"Copying benchmark from {options.benchmark_local_path} to {options.benchmark_remote_path} on {options.remote}")
        cmd = f"scp {ssh_opts} -r {options.benchmark_local_path} {options.remote}:{options.benchmark_remote_path}"
        subprocess.run(shlex.split(cmd), check=True)
    BenchClass = JSCBenchmark.benchmarks[options.benchmark]
    benchmark = BenchClass(options.remote, options.repeats, parameters, options.benchmark_remote_path, options.ssh_id, options.exec_path)
    gp_minimize_kargs = {}
    if options.pre_run >=3:
        y0, noise = benchmark.preruns(options.pre_run)
        logger.info(f"With defaults ({dict((p.name, p.default) for p in parameters)}): result: {y0}, variance: {noise}")
        gp_minimize_kargs['y0'] = y0
        gp_minimize_kargs['noise'] = noise
        gp_minimize_kargs['x0'] = [p.default for p in parameters]

    for k in ('x0', 'y0'):
        if k in gp_minimize_kargs:
            logger.info(f"initial {k}: {gp_minimize_kargs[k]}\n")
    if options.previous_results:
        for k in ('x0', 'y0'):
            if k in gp_minimize_kargs:
                #assert(type(gp_minimize_kargs[k]) is list)
                if k=='x0' and gp_minimize_kargs[k] and type(gp_minimize_kargs[k]) is list and type(gp_minimize_kargs[k][0]) is not list:
                    gp_minimize_kargs[k] = [gp_minimize_kargs[k]]
                    logger.info(f"Reworked {k} as: {gp_minimize_kargs[k]}")
                elif k=='y0' and k in gp_minimize_kargs:
                    gp_minimize_kargs[k] = [gp_minimize_kargs[k]]
                    logger.info(f"Reworked {k} as: {gp_minimize_kargs[k]}")
                else:
                    logger.info(f"{k} not reworked")
            else:
                gp_minimize_kargs[k] = []
        for f in options.previous_results:
            res = skopt.load(f)
            in_bounds = filter_in_bounds(res.x_iters, list(res.func_vals), parameters)
            logger.info(f"Adding {in_bounds.x} to x0\n")
            gp_minimize_kargs['x0'] += in_bounds.x
            logger.info(f"Adding {in_bounds.y} to y0\n")
            gp_minimize_kargs['y0'] += in_bounds.y
            logger.info(f"Using {len(in_bounds.x)} of {len(res.x_iters)} previous points from {f}\n")

    logger.info(f"Gonna pass as x0:\n{gp_minimize_kargs.get('x0')}\n")
    logger.info(f"Gonna pass as y0:\n{gp_minimize_kargs.get('y0')}\n")

    import time
    logger.info("Starting to minimize")
    before = time.monotonic()
    with ExitStack() as stack:
        # We need this stuff because gp_minimize() does a lot of prints that we want in our log file
        stack.enter_context(redirect_stdout(LogRedirect("gp_minimize", logging.INFO)))
        stack.enter_context(redirect_stderr(LogRedirect("gp_minimize", logging.WARNING)))
        res = skopt.gp_minimize(benchmark.run,
                          [p.range for p in parameters],
                          n_calls=options.n_calls,
                          n_initial_points=options.initial_points,
                          initial_point_generator=options.initial_point_generator,
                          verbose=True,
                          **gp_minimize_kargs)
    logger.info(f"gp_minimize ran in {time.monotonic() - before}s")
    logger.info(f"best: {res.x} ??? {abs(res.fun)}")
    save_results(logger, options, output_dir, res, nowStr)
