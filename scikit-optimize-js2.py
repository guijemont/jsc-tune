#!/usr/bin/env -S python3 -u

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
parser.add_argument('-i', '--ssh-id', required=True,
                    help="ssh identity file to use to connect to remote host")
parser.add_argument('-j', '--jsc-path', required=True,
                    help="path of jsc executable on remote host")
parser.add_argument('--initial-point-generator', default="random")
parser.add_argument('-n', '--n-calls', type=int, default=50,
                    help="how many times to run benchmark")
parser.add_argument('--initial-points', type=int, default=10,
                    help="how many random points to evaluate before using estimator")
parser.add_argument('-p', '--pre-run', type=int, default=5,
                    help="How many times to initially run benchmark to calculate variance")
parser.add_argument('-o', '--output-dir', type=str, default="./",
                    help="Where to output everything we generate")
parser.add_argument('-g', '--dump-graphs', action='store_true',
                    help="Save graphics")
parser.add_argument('--repeats', type=int, default=1,
                    help="How many times to run each config (apart from preruns)")
parser.add_argument('--previous-results', type=str, default=[], action='append',
                    help="PKL file containing previous results for this exact configuration to take into account")


class JSCBenchmark:
    def __init__(self, host, repeats, parameters, ssh_id=None, jscpath=None):
        self._host = host
        self._repeats = repeats
        self._parameters = parameters
        self._ssh_id = ssh_id
        if jscpath is None:
            self._jscpath = 'jsc'
        else:
            self._jscpath = jscpath

    def score(self, out, errs):
        raise RuntimeError("Not implemented")

    def benchmark_command(self, env_string):
        raise RuntimeError("Not implemented")

    def run(self, arguments):
        assert len(arguments) == len(self._parameters)
        env = dict((self._parameters[i].name, arg) for i, arg in enumerate(arguments))
        env_string = " ".join(f"JSC_{k}={v}" for k,v in env.items())

        ssh_opts = "-o StrictHostKeyChecking=no"
        if self._ssh_id:
            ssh_opts += f" -i {self._ssh_id}"

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
            logging.warning(f"error while running configuration {arguments}, returning arbitrary large value: {e}\n")
            # Note: using inf, nan or sys.float_info.max ends up failing
            # gp_minimize, 1e100 seems to work and should be "big enough" for most benchmarks
            return 1e100

    def preruns(self, n):
        default_arguments = dict((p.name, p.default) for p in self._parameters)
        scores = [self.run(default_arguments) for _ in range(n)]
        return (tmean(scores), tvar(scores))

class JetStream2(JSCBenchmark):
    def benchmark_command(self, env_string):
        return f'cd JetStream2; {env_string} {self._jscpath} watch-cli.js'

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


def save_results(options, output_dir, res, nowStr):
    if options.dump_graphs:
        fig = plot_convergence(res).get_figure()
        fig.savefig(output_dir / f"{nowStr}-convergence.png")
        fig = plot_objective(res, dimensions=[p.name for p in parameters])[0][0].get_figure()
        fig.savefig(output_dir / f"{nowStr}-objective.png")
    skopt.dump(res, output_dir / f"{nowStr}-dump.pkl", store_objective=False)


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


if __name__ == '__main__':
    nowStr = datetime.now().strftime('%Y-%m-%d-%H%M%S')
    options = parser.parse_args()
    output_dir = prepare_output(options)
    logging.basicConfig(level=logging.DEBUG,
                        handlers=[logging.FileHandler(output_dir / f"{nowStr}.log"),
                                  logging.StreamHandler()])
    logging.debug(f"options: {options}")
    benchmark = JetStream2(options.remote, options.repeats, parameters, options.ssh_id, options.jsc_path)
    gp_minimize_kargs = {}
    if options.pre_run >=3:
        y0, noise = benchmark.preruns(options.pre_run)
        logging.info(f"With defaults ({dict((p.name, p.default) for p in parameters)}): result: {y0}, variance: {noise}")
        gp_minimize_kargs['y0'] = y0
        gp_minimize_kargs['noise'] = noise
        gp_minimize_kargs['x0'] = [p.default for p in parameters]

    for k in ('x0', 'y0'):
        if k in gp_minimize_kargs:
            logging.info(f"initial {k}: {gp_minimize_kargs[k]}\n")
    if options.previous_results:
        for k in ('x0', 'y0'):
            if k in gp_minimize_kargs:
                #assert(type(gp_minimize_kargs[k]) is list)
                if k=='x0' and gp_minimize_kargs[k] and type(gp_minimize_kargs[k]) is list and type(gp_minimize_kargs[k][0]) is not list:
                    gp_minimize_kargs[k] = [gp_minimize_kargs[k]]
                    logging.info(f"Reworked {k} as: {gp_minimize_kargs[k]}")
                elif k=='y0' and k in gp_minimize_kargs:
                    gp_minimize_kargs[k] = [gp_minimize_kargs[k]]
                    logging.info(f"Reworked {k} as: {gp_minimize_kargs[k]}")
                else:
                    logging.info(f"{k} not reworked")
            else:
                gp_minimize_kargs[k] = []
        for f in options.previous_results:
            res = skopt.load(f)
            in_bounds = filter_in_bounds(res.x_iters, list(res.func_vals), parameters)
            logging.info(f"Adding {in_bounds.x} to x0\n")
            gp_minimize_kargs['x0'] += in_bounds.x
            logging.info(f"Adding {in_bounds.y} to y0\n")
            gp_minimize_kargs['y0'] += in_bounds.y
            logging.info(f"Using {len(in_bounds.x)} of {len(res.x_iters)} previous points from {f}\n")

    logging.info(f"Gonna pass as x0:\n{gp_minimize_kargs['x0']}\n")
    logging.info(f"Gonna pass as y0:\n{gp_minimize_kargs['y0']}\n")

    import time
    logging.info("Starting to minimize")
    before = time.monotonic()
    res = skopt.gp_minimize(benchmark.run,
                      [p.range for p in parameters],
                      n_calls=options.n_calls,
                      n_initial_points=options.initial_points,
                      initial_point_generator=options.initial_point_generator,
                      verbose=True,
                      **gp_minimize_kargs)
    logging.info(f"gp_minimize ran in {time.monotonic() - before}s")
    logging.info(f"best: {res.x} → {-res.fun}")
    save_results(options, output_dir, res, nowStr)
