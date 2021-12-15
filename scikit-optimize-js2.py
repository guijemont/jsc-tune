#!/usr/bin/env -S python3 -u

# FIXME: logging
# FIXME: output log/graphs in output dir (default pwd, with command-line option)
from skopt import gp_minimize

from scipy.stats import gmean, tmean, tvar
import numpy as np
import subprocess
import json
import argparse
from collections import namedtuple
from skopt.plots import plot_convergence, plot_objective
from datetime import datetime

Parameter = namedtuple('Parameter', ('name', 'range', 'default'))
parameters = (Parameter('maximumFunctionForCallInlineCandidateBytecodeCost', (0, 200), 120),
              Parameter('maximumOptimizationCandidateBytecodeCost', (0, 200000), 100000))



parser = argparse.ArgumentParser()
parser.add_argument('-r', '--remote', required=True,
                    help='host or user@host to pass to ssh to access remote host')
parser.add_argument('-i', '--ssh-id', required=True,
                    help="ssh identity file to use to connect to remote host")
parser.add_argument('-j', '--jsc-path', required=True,
                    help="path of jsc executable on remote host")
parser.add_argument('--initial-point-generator', default="random",
                    help="path of jsc executable on remote host")
#parser.add_argument('-n', '--iteration-per-config', type=int, default=1,
#                    help="how many times to run JetStream2 for each tested configuration")

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
        print(f"optimize_me({arguments}) → {score}")
        return -score
    
    return optimize_me


def default_preruns(options):
    env = dict((p.name, p.default) for p in parameters)
    scores = [run_jetstream2(options.remote, options.ssh_id, options.jsc_path, env=env) for _ in range(5)]
    return (tmean(scores), tvar(scores))

def saveGraphs(res):
    nowStr = datetime.now().strftime('%Y-%m-%d-%H%M%S')
    fig = plot_convergence(res).get_figure()
    fig.savefig(f"{nowStr}-convergence.png")
    fig = plot_objective(res, dimensions=[p.name for p in parameters])[0][0].get_figure()
    fig.savefig(f"{nowStr}-objective.png")

if __name__ == '__main__':
    options = parser.parse_args()
    print(f"options: {options}")
    y0, noise = default_preruns(options)
    print(f"With defaults ({dict((p.name, p.default) for p in parameters)}): result: {y0}, variance: {noise}")
    func = get_optimization_func(options)
    import time
    print ("Starting to minimize")
    before = time.monotonic()
    res = gp_minimize(func,
                      [p.range for p in parameters],
                      n_calls=50,
                      x0=[p.default for p in parameters],
                      y0=-y0,
                      noise=noise,
                      initial_point_generator=options.initial_point_generator,
                      verbose=True)
    print(f"gp_minimize ran in {time.monotonic() - before}s")
    print(f"best: {res.x} → {-res.fun}")
    saveGraphs(res)
    axes = plot_convergence(res)
    