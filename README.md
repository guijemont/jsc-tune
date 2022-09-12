
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
 - copy benchmark (option to set where to copy it)
 - jsc-tune.sh set current uid/gid as uid/gid for optimizer user when creating image
 - README.md!
