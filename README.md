
## Dependencies

### On development host

 - [GNU coreutils](https://www.gnu.org/software/coreutils/) for `dirname` and
   `realpath`.
 - [GNU bash](https://www.gnu.org/software/bash/)
 - Docker

### On remote target

 - an ssh server to which you can connect with a passwordless ssh key.

# Important points

 - ssh key needs to be passwordless
 - output dir has to be subdir of current working directory or current working directory, and expressed relatively



# TODO:
 - rename everything to "jsc-tune" [x]
 - copy script instead of relying on being launched from project directory [x]
 - can we copy ssh key to container? If not, document it has to be in subdir [x]
 - can we get `gp_minimize` logging to the right stream? [x]
 - logging to output dir,getting rid of optimizer.log [x]
 - log with timestamps [x]
 - mock benchmark [x]
 - copy benchmark (option to set where to copy it) [x]
 - jsc-tune.sh set current uid/gid as uid/gid for optimizer user when creating image [x]
 - fix deps versions (pip)
 - switch to python:3.x-alpine? (-slim: 552 MB)
 - switch to python 3.10?
 - change image name?
 - README.md!
