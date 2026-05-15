---
name: Development Workflow Review
description: Review implementation work against scenarios and design.
---

As the development workflow review step, you evaluate whether the implementation
matches the issue's stated behavior and design.

Review the implementation against the issue body's Scenarios and Design
sections as well as framework-oriented-design principles.

Issue context: `gh issue view <number-or-url> --json number,title,body,comments`; body is durable state, comments are context.

Before reviewing framework-oriented design, run:

```sh
myteam get skill development-workflow/shared/framework-oriented-design
```

Before editing workflow sections in the issue body, run:

```sh
myteam get skill development-workflow/shared/workflow-issue
```

## Check the following:

### Code duplication

Is there any code duplication? This might include direct copy-paste, but also logic.
Trival duplications are fine: what we want to catch is conceptual duplication.

Is there opportunity for a generic function to be made?

Was there an existing function that could have been used instead of writing another version?
Maybe the existing function isn't a perfect match, but with a reasonable adjustment
it could serve both the existing and new needs.

### Naming

Are variables and functions named well?

### Decomposition

Are functions too large or too complicated? How could they be broken down reasonably?

Are modules too large? Should additional modules be created?

Are packages too large? Should sub-packages be created?

## Conclusion

Edit the issue body's Review section with findings and readiness. Return `next_step`
as `scenarios`, `design`, `implement`, `review`, or `wrap_up`, using the output
schema supplied by the caller.
