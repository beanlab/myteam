# Jinja2 Template Rendering for Markdown Body

The body of a Markdown skill or workflow is rendered with Jinja2 before being passed as the prompt. Full Jinja2 syntax is supported.

The fields of the input dictionary (for workflows, if provided) are passed as variables to the rendering (for example, `render(**inputs)`).

The following `myteam` functions are included in the Jinja environment:

- `myteam_explain()` - injects the output of `myteam explain`.
- `myteam_onboard()` - injects the output of `myteam onboard`.
- `myteam_list(*paths, directory=False)` - injects the equivalent resource listing for one or more paths. Every path is relative to the Markdown document. With no paths, it lists the document's directory. `directory=True` selects the paths themselves, equivalent to `myteam list -d`.
- `myteam_load(skill)` - loads the specified skill content. The skill path is relative to the document.

See [Listing Skills and Workflows](listing.md) for the shared `myteam list` selection, sorting, ignored-resource, and filesystem-failure semantics.

The following utility function is also included:

- `read_file(file)` - injects the file's contents. The included file is Jinja-rendered in the same environment by default. To include raw contents, use `read_file(file, render=False)`.

Document-relative path helpers support `~` home-directory expansion. Absolute paths remain absolute.

Input field names take precedence over Jinja environment functions; avoid naming conflicts.

Errors in rendering propagate to the calling process. In particular, a filesystem error from `myteam_list` writes its diagnostic to stderr, raises `SystemExit(1)`, and aborts rendering.
