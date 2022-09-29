# jsc-tune

jsc-tune is a tool based on
[scikit-optimize](https://scikit-optimize.github.io/stable/) to find optimal
compilation parameters for JavaScriptCore for a given device and benchmark.
Currently the only benchmark supported is JetStream2, but new benchmarks can be
added with a few lines of code.


## Installing

First you should check out this repository:

```sh
  git clone https://github.com/guijemont/jsc-tune.git
```

Also make sure You have the dependencies indicated below.

On development host:

 - [Docker](https://github.com/docker/cli)
 - [GNU bash](https://www.gnu.org/software/bash/)
 - [GNU coreutils](https://www.gnu.org/software/coreutils/) for `dirname` and
   `realpath`.

On remote target:

 - an ssh server to which you can connect with a passwordless ssh key.

## Setting up and launching

The first time you run `jsc-tune.sh`, it will pull the docker image with all
the dependencies, which can take a while depending on your internet connection.

If you want to do it manually, you can use the following command:

```sh
  docker pull ghcr.io/guijemont/jsc-tune
```

You can see the details of all the options by running:

```sh
  ./jsc-tune.sh --help
```

Which is encouraged, as this document does not list all the options.


The minimal options you can run it with are:
```sh
  /path/to/jsc-tune.sh -r user@device -i ssh/ssh_id
```

For this to work, you will need:
 - `jsc` to be on `device` and set up in `$PATH`. If it's not in `$PATH`, you
   can use the `-j` option to specify the path to the `jsc` interpreter on the
   remote device.
 - [JetStream2](https://github.com/WebKit/WebKit/tree/main/PerformanceTests/JetStream2)
   to be copied to the `JetStream2` subdirectory of the default directory you
   ssh into (usually the home of the user). If it's in a different directory on
   the remote device, you can specify it with `--benchmark-remote-path`, if it's
   not deployed on the remote device, you can have the script deploy it for you
   using `--benchmark-local-path` to point to a local deployment of it on your
   development host.
 - the ssh key you pass to `-i` needs to be passwordless, as we are running
   under docker and there is currently nothing set up to support sharing the
   host's ssh agent.

The results, including logs, and optionally graphs (if using `-g`) will be
output by default to a `jsc-tune-results` directory in your current directory.
You can optionally have them output to a different directory using the `-o`
option, but note that this directory currently needs to be a subdirectory of
where you launch `jsc-tune.sh` from.


## Interepreting results


The goal of jsc-tune is to find the optimal values for the following
JavaScriptCore compilation parameters:

 - `maximumFunctionForCallInlineCandidateBytecodeCost`
 - `maximumOptimizationCandidateBytecodeCost`
 - `maximumFunctionForClosureCallInlineCandidateBytecodeCost`
 - `maximumInliningCallerBytecodeCost`
 - `maximumInliningDepth`
 - `maximumInliningRecursion`

More information on these parameters can be found in the
[OptionsList.h](https://github.com/WebKit/WebKit/blob/main/Source/JavaScriptCore/runtime/OptionsList.h)
file in the WebKit sources.


After running `jsc-tune.sh`, the output directory (by default
`jsc-tune-results`) will contain the following files:
 - `<timestamp>-result.json` with the optimal values and the score obtained with them.
 - `<timestamp>.log`, the log file
 - `<timestamp>-dump.pkl, the full optimization result as generatd by
   scikit-optimize, which can be used in future runs using
   `--previous-results`.
 - if you used `-g`, you will also get `<timestamp>-convergence.png` and
   `<timestamp>-objective.png`.


The most important data in these file is in the json file which will look like this:
```json
{
  "parameters": {
    "maximumFunctionForCallInlineCandidateBytecodeCost": 77,
    "maximumOptimizationCandidateBytecodeCost": 42403,
    "maximumFunctionForClosureCallInlineCandidateBytecodeCost": 68,
    "maximumInliningCallerBytecodeCost": 9912,
    "maximumInliningDepth": 8,
    "maximumInliningRecursion": 3
  },
  "score": 8.35282617018331
}
```

To run JavaScriptCore or a WebKit-based browser with the seetings found, you want to set an environment variable for each parameter, with the name of the variable being `JSC_` prepended to each parameter name, and the values found. For the example above, that could be something like:

```sh
  JSC_maximumFunctionForCallInlineCandidateBytecodeCost=77 \
  JSC_maximumOptimizationCandidateBytecodeCost=42403 \
  JSC_maximumFunctionForClosureCallInlineCandidateBytecodeCost=68 \
  JSC_maximumInliningCallerBytecodeCost=9912 \
  JSC_maximumInliningDepth=8 \
  JSC_maximumInliningRecursion=3 \
  cog
```
