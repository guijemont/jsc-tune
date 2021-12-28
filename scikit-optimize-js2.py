#!/usr/bin/env -S python3 -u

# FIXME: logging
from skopt import gp_minimize, dump

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
parameters = (Parameter('maximumFunctionForCallInlineCandidateBytecodeCost', (0, 180), 120),
              Parameter('maximumOptimizationCandidateBytecodeCost', (0, 150000), 100000),
              Parameter('maximumFunctionForClosureCallInlineCandidateBytecodeCost', (0, 150), 100 ),
              Parameter('maximumInliningCallerBytecodeCost', (0, 15000), 10000),
              Parameter('maximumInliningDepth', (2,8), 5),
              Parameter('maximumInliningRecursion', (1,5), 2),
             )



parser = argparse.ArgumentParser()
parser.add_argument('-r', '--remote', required=True,
                    help='host or user@host to pass to ssh to access remote host')
parser.add_argument('-i', '--ssh-id', required=True,
                    help="ssh identity file to use to connect to remote host")
parser.add_argument('-j', '--jsc-path', required=True,
                    help="path of jsc executable on remote host")
parser.add_argument('--initial-point-generator', default="random",
                    help="path of jsc executable on remote host")
parser.add_argument('-n', '--n-calls', type=int, default=50,
                    help="how many times to run JetStream2")
parser.add_argument('--initial-points', type=int, default=10,
                    help="how many random points to evaluate before using estimator")
parser.add_argument('-p', '--pre-run', type=int, default=5,
                    help="How many times to initially run JetStream2 to calculate variance")
parser.add_argument('-o', '--output-dir', type=str, default="./",
                    help="Where to output everything we generate")
parser.add_argument('-g', '--dump-graphs', action='store_true',
                    help="Save graphics")


def score_from_json(res):
    l = [test['metrics']['Score']['current'][0] for test in res['JetStream2.0']['tests'].values()]
    return gmean(l)

def run_jetstream2(host, ssh_id=None, jscpath=None, env=None):
    """Assumes JetStream2 is in `JetStream2/` path on `host`."""

    def __parse(s, errs=None):
        for line in s.splitlines():
            if line.startswith('{'):
                return json.loads(line)
        raise RuntimeError(f"Could not parse JetStream2 output:\n{s}\nstderr:\n{errs}\n")

    if env is None:
        envs = ""
    else:
        envs = " ".join(f"JSC_{k}={v}" for k,v in env.items())
    if jscpath is None:
        jscpath = 'jsc'
    ssh_opts = "-o StrictHostKeyChecking=no"
    if ssh_id:
        ssh_opts += f" -i {ssh_id}"
    cmd = f'ssh {ssh_opts} {host} "cd JetStream2; {envs} {jscpath} watch-cli.js"'
    def __run():
        proc = subprocess.run(cmd, shell=True, text=True, capture_output=True, check=True)
        json_res = __parse(proc.stdout, proc.stderr)
        return score_from_json(json_res)
    return np.mean([__run() for _ in range(3)])

def get_optimization_func(options):
    def optimize_me(arguments):
        assert len(arguments) == len(parameters)
        env = dict((parameters[i].name, arg) for i, arg in enumerate(arguments))
        #print(f"running: {env}")
        score = run_jetstream2(options.remote, options.ssh_id, options.jsc_path, env=env)
        logging.debug(f"optimize_me({arguments}) → {score}")
        return -score

    return optimize_me


def default_preruns(options):
    env = dict((p.name, p.default) for p in parameters)
    scores = [run_jetstream2(options.remote, options.ssh_id, options.jsc_path, env=env) for _ in range(options.pre_run)]
    return (tmean(scores), tvar(scores))

def save_results(options, output_dir, res, nowStr):
    if options.dump_graphs:
        fig = plot_convergence(res).get_figure()
        fig.savefig(output_dir / f"{nowStr}-convergence.png")
        fig = plot_objective(res, dimensions=[p.name for p in parameters])[0][0].get_figure()
        fig.savefig(output_dir / f"{nowStr}-objective.png")
    dump(res, output_dir / f"{nowStr}-dump.pkl", store_objective=False)


def prepare_output(options):
    output_dir = Path(options.output_dir)
    output_dir.mkdir(exist_ok=True)
    return output_dir

if __name__ == '__main__':
    nowStr = datetime.now().strftime('%Y-%m-%d-%H%M%S')
    options = parser.parse_args()
    output_dir = prepare_output(options)
    logging.basicConfig(level=logging.DEBUG,
                        handlers=[logging.FileHandler(output_dir / f"{nowStr}.log"),
                                  logging.StreamHandler()])
    logging.debug(f"options: {options}")
    gp_minimize_kargs = {}
    if options.pre_run >=3:
        y0, noise = default_preruns(options)
        logging.info(f"With defaults ({dict((p.name, p.default) for p in parameters)}): result: {y0}, variance: {noise}")
        gp_minimize_kargs['y0'] = -y0
        gp_minimize_kargs['noise'] = noise
        gp_minimize_kargs['x0'] = [p.default for p in parameters]

    func = get_optimization_func(options)
    import time
    logging.info("Starting to minimize")
    before = time.monotonic()
    res = gp_minimize(func,
                      [p.range for p in parameters],
                      n_calls=options.n_calls,
                      n_initial_points=options.initial_points,
                      initial_point_generator=options.initial_point_generator,
                      verbose=True,
                      **gp_minimize_kargs)
    logging.info(f"gp_minimize ran in {time.monotonic() - before}s")
    logging.info(f"best: {res.x} → {-res.fun}")
    save_results(options, output_dir, res, nowStr)
