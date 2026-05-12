# Reports CLI Status

## Purpose

Report version and failures.

---

# Context

Callers observe CLI status through standard output, standard error, exit
status, and filesystem effects.

---

# Action

The caller asks for the installed version or runs a command that succeeds or
fails.

---

# Interaction

| Action | Outcome |
| --- | --- |
| `myteam --version` | Prints a version string in the form `myteam <version>`. |
| Successful command | Creates or removes files, prints instructions or listings, executes a workflow, downloads roster files, or returns a version string according to the command contract. |
| Failed command | Exits with an error and reports the failure on standard error. |

---

# Outcome

The caller can verify which installed version of `myteam` is running.

Errors are communicated as command failure plus an error message on standard
error. Command-specific scenario files define the failure conditions that matter
for each behavior.

---

# Related Scenarios

- [../README.md](../README.md)
