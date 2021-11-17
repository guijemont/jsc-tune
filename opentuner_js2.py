#!/usr/bin/env python

import subprocess, sys
import json
import random
import argparse
from collections import namedtuple

import opentuner
from opentuner import ConfigurationManipulator, IntegerParameter, MeasurementInterface, Result
from opentuner.search.objective import MaximizeAccuracy
from functools import reduce
from scipy.stats import gmean, tmean

# FIXME maybe also a json file with options to test for?
# FIXME fix parallelism


parser = argparse.ArgumentParser(parents=opentuner.argparsers())
parser.add_argument('-r', '--remote', required=True,
                    help='host or user@host to pass to ssh to access remote host')
parser.add_argument('-i', '--ssh-id', required=True,
                    help="ssh identity file to use to connect to remote host")
parser.add_argument('-j', '--jsc-path', required=True,
                    help="path of jsc executable on remote host")
parser.add_argument('-n', '--iteration-per-config', type=int, default=5,
                    help="how many times to run JetStream2 for each tested configuration")


def score_from_json(res):
    l = [test['metrics']['Score']['current'][0] for test in res['JetStream2.0']['tests'].values()]
    return gmean(l)

def run_jetstream2(host, ssh_id=None, jscpath=None, mock=False, env=None):
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
    if mock:
        cmd = "sleep 0; cat js2-sample-output.txt"

    proc = subprocess.run(cmd, shell=True, text=True, capture_output=True, check=True)
    json_res = __parse(proc.stdout, proc.stderr)
    return json_res

    
def run_n_times(host, n=5, *args, mock=False, env=None, **kwargs):
    def randomize(json_res):
        tests = json_res['JetStream2.0']['tests']
        for key in tests.keys():
            tests[key]['metrics']['Score']['current'][0] += random.random() - 0.5
        return json_res

    def __run(cb):
        # run cb n times and yield results, allows one CalledProcessError and no more
        has_failed = False
        for _ in range(n):
            try:
                yield cb()
            except subprocess.CalledProcessError as e:
                if has_failed:
                    raise
                else:
                    has_failed=True
                    print(f"Info: process failure for {env}: {e}\n{e.stdout}\n{e.stderr}")
                    yield cb()
    
    return list(__run(lambda: run_jetstream2(host, *args, mock=mock, env=env, **kwargs)))

    if mock:
        return [randomize(res) for res in json_results]
    else:
        return json_results

Parameter = namedtuple('Parameter', ('name', 'min', 'max', 'resolution'))

class JetStream2Tuner(MeasurementInterface):
    __integerParameters = (#Parameter('maximumFunctionForCallInlineCandidateBytecodeCost', 0, 200, 10),
                          Parameter('maximumOptimizationCandidateBytecodeCost', 0, 200000, 10000),)
    
    def objective(self):
        return MaximizeAccuracy()
    
    def manipulator(self):
        manipulator = ConfigurationManipulator()
        for param in self.__integerParameters:
            assert param.min % param.resolution == 0
            assert param.max % param.resolution == 0
            manipulator.add_parameter(IntegerParameter(param.name, int(param.min / param.resolution),
                                                       int(param.max / param.resolution)))
        return manipulator
        
    def run(self, desired_result, input_, limit):
        cfg = desired_result.configuration.data
        env = dict((param.name, cfg[param.name] * param.resolution) for param in self.__integerParameters)
        
        n = self.args.iteration_per_config
        try:
            json_res_l = run_n_times(self.args.remote, n, ssh_id=self.args.ssh_id,
                                     jscpath=self.args.jsc_path, env=env)
        except subprocess.CalledProcessError:
            print(f"Warning: Too many failures for {env}", file=sys.stderr)
            return Result(state='ERROR', time=float('inf'), accuracy=0)

        assert len(json_res_l) == n
        score = float(tmean([score_from_json(r) for r in json_res_l]))
        
        print(f"Ran JetStream2 {n} times on {self.args.remote} with {env}: {score}", file=sys.stderr)
        # FIXME actually measure and return time, as it might be used for some
        # decisions on how many tests to run? (wishful thinking?)
        return Result(accuracy=score, time=1)
    
    def save_final_config(self, configuration):
        out_data = configuration.data.copy()
        for param in self.__integerParameters:
            out_data[param.name] *= param.resolution
        print("Optimal configuration written to jetstream2-opt.json:", out_data)
        self.manipulator().save_to_file(out_data, 'jetstream2-opt.json')


if __name__ == '__main__':
    JetStream2Tuner.main(parser.parse_args())
