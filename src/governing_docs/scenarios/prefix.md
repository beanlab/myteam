# Prefix argument for all `myteam` commands

All `myteam` commands that work with the `.myteam` folder should accept a `--prefix <prefix>` option.

The default is `.myteam`.

Running `myteam --prefix .foobar ...` will perform the myteam command against the `.foobar/` folder instead of the `.myteam/` folder. 
