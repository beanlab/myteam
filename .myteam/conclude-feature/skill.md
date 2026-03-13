---
name: Conclude Feature
description: |
    Work instruction for concluding a feature.
    If you helping with development in ANY way, you MUST load this skill.
---

## Concluding a Feature

Before a feature branch is ready to merge, the following must be complete.

### Git commit

Please review all untracked files. 
Confirm with the user whether these files should be committed.

Please make sure all current work has been committed. 
If it hasn't, please alert the user and wait for their approval before proceeding.

Commit the files with a descriptive commit message.

When asking for approval for `git` commands, 
make sure the approval prefix is just `git add` or `git commit`;
if these approval requests include more than that 
(i.e. they include the files being added or the commit message used)
then the approval is too narrow in scope to be useful.

### Version bump

If any code or templates have changed, then the version in `project.toml` needs to change.

Because we are still in *preview*, the leading version will stay at 0.
If the public interface has changed, the minor version should increase.
If the public interface has not changed, just the patch version should increase.

Please describe the scope of the changes in the current branch and determine what version bump is needed.
Then inspect the version:

- if it has been updated incorrectly, check with the user about what version they want
- if it has not been udpated at all, update the version and inform the user

Only one version bump in a branch is needed. If the version in the branch has already been bumped,
do not bump it again.

### Changelog

Please update the changelog to include a helpful description of the changes made.

### Readme and Documentation

The Readme and other documentation (if relevant) must be up-to-date.
Inspect the code changes and update the documentation accordingly.