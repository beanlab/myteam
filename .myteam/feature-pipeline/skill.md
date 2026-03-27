---
name: Feature Pipeline
description: |
    This skill defines the process to follow for developing new features.
    Load this skill if you are tasked with changing anything in the `src/myteam/` directory.
---

## Feature Pipeline

Carefully follow each of these steps in order. 
Create a plan that has checkboxes for each of these steps.

When using the term "feature", we mean any change to the code or assets,
not just new additions to the codebase.

### Create the git branch

Check the current branch. 
If you are on `main`, create a new branch for the feature.
The branch name should be simple but descriptive.

If you are on a different branch (not `main`), 
confirm with the user whether this branch should be used for the feature,
or whether a new branch should be created.

If the user's description of the feature is too vague
to name the branch, get enough details to select a reasonable name.

The name does NOT need to be perfect; as long as it 
is loosely relevant, it will work great.

### Understand the feature and update the interface document

The goal of this step is to thoroughly understand the requested feature
and document how the primary interface of the application should be changed.

First read `src/governing_docs/application_interface.md` to understand
the current design and intent of the project.
This document describes what this app should do, how it behaves, etc.
It is the black-box description of the user's experience with the application.

Then seek to understand what the user wants to change. 
Is it a new behavior? Modifying an existing behavior? A bugfix?

Questions that might be relevant:

- What change in behavior does the user hope for?
  - What behaviors should NOT change?
- How might this change be implemented?
  - If there are multiple reasonable strategies, what distinguishes them?
  - Are there dependencies that may change? 
  - Is there documentation via skills or in the repo that suggests a strategy?
  - Does the user have an opinion on which strategy is used?

Based on the details in the feature plan document, determine how the 
user interface of the application will change.

Update the `application_interface.md` document to reflect the new feature.

Review these changes with the user. Make sure you are both on the same page
before you continue.

When this step is complete, commit your changes before moving on.

### Design the feature

Prepare a document in `src/governing_docs/feature_plans/<branch_name>.md`
that describes the specific details and strategies decided on for the feature.

Get approval from the user on this document before continuing.

When this step is complete, commit your changes before moving on.

### Refactor the framework

Load the `framework-oriented-design` skill.

Following its guidance, make any necessary changes to the application framework.

The existing tests should all still pass.

When this step is complete, commit your changes before moving on.

### Update the test suite

Load the `testing` skill.

Review the existing tests. Identify changes that need to be made to test suite
to bring it in line with the updated interface document.

Make these changes to the test suite.

Review the changes one more time: do they faithfully capture the new interface design?
Make changes as needed.

When this step is complete, commit your changes before moving on.

### Implement the feature

Now that the framework has been updated (if necessary) and the tests are in place,
implement the feature.

The tests should pass. 

When this step is complete, commit your changes before moving on.

### Concluding the feature

Follow the instructions in the `conclusion` subskill to verify everything is ready
for the pull request to be created and merged.

### Notify the user

Notify the user that the feature is ready to push to github and merge.
