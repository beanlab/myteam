# Jinja2 Template Rendering

Myteam renders Markdown skill bodies, Markdown workflow prompts, direct `run_agent` prompts, and rendered `read_file` includes with Jinja2. Full Jinja2 syntax is supported.

The fields of the input dictionary, when provided, are passed as variables to the rendering (for example, `render(**inputs)`).

The following `myteam` functions are included in the Jinja environment:

- `myteam_explain()` - injects the output of `myteam explain`.
- `myteam_onboard()` - injects the output of `myteam onboard`.
- `myteam_list(*paths, directory=False)` - injects the equivalent resource listing for one or more paths. Every path is relative to the Markdown document. With no paths, it lists the document's directory. `directory=True` selects the paths themselves, equivalent to `myteam list -d`.
- `myteam_load(skill)` - loads the specified skill content. The skill path is relative to the document.

See [Listing Skills and Workflows](listing.md) for the shared `myteam list` selection, sorting, ignored-resource, and filesystem-failure semantics.

The following utility functions are also included:

- `read_file(file)` - injects the file's contents. The included file is Jinja-rendered by default. To include raw contents, use `read_file(file, render=False)`.
- `shell(command, timeout=None)` - synchronously runs the required string command through the platform-standard shell and injects its combined output. There is no default timeout; provide one to limit how long a command may run.
- `increase_headers(content, offset=1)` - increases ATX heading levels in Markdown content. It is also available as the `increase_headers` filter.

The same helper is publicly available in Python with `from myteam import increase_headers`. It composes with other helpers in either Jinja form:

```jinja2
{{ increase_headers(read_file('overview.md'), offset=1) }}
{{ read_file('overview.md') | increase_headers(1) }}
{{ shell('generate-markdown') | increase_headers(2) }}
```

`increase_headers` recognizes an opening run of one or more `#` characters after zero to three spaces when the run is followed by a space, tab, or end of line. It inserts exactly `offset` additional markers while preserving the indentation and all remaining source text. Heading runs and results are not limited to six markers. Four-space-indented lines, forms such as `#text`, and Setext headings are unchanged.

Headings inside standard backtick or tilde fenced code blocks are unchanged, including through end of input when a fence is unclosed. A fence opener uses at least three identical markers after zero to three spaces; a backtick opener's info string cannot contain a backtick. A closer must use the same marker, contain at least as many markers as the opener, and have only spaces or tabs afterward.

The default offset is `1`. An offset of `0` returns the content unchanged, a negative offset raises `ValueError`, and a non-integer offset (including a boolean) raises `TypeError`. Non-string content also raises `TypeError`. At the Python string boundary, the helper preserves LF and CRLF endings and every character other than the inserted `#` markers. Existing file reads, subprocess text capture, and Jinja template parsing may normalize input before it reaches the helper; their newline behavior is unchanged.

A shell command runs in the directory of the file containing its expression. A command in a rendered `read_file` include therefore runs in the included file's directory. A direct prompt with no source path uses the process's current working directory. Commands inherit myteam's environment and permissions, receive non-interactive stdin, and have stderr redirected into stdout. Successful output is returned exactly, including interleaved stderr, trailing newlines, or empty output.

A non-zero exit aborts rendering with a diagnostic containing the command, exit code, and combined output. A timeout likewise aborts rendering and identifies the command and timeout while including output captured before termination. No partial rendered template text is returned. Commands may still have side effects before a later command or rendering step fails; repeated expressions run the command repeatedly without caching or rollback.

`shell` executes arbitrary code without sandboxing, allowlists, or confirmation. Templates therefore have access to the same files, inherited environment (including secrets), and other resources as the myteam process. Platform-specific shell syntax and behavior apply.

Document-relative path helpers support `~` home-directory expansion. Absolute paths remain absolute.

Input field names take precedence over Jinja environment functions. An input named `shell`, for example, shadows the helper. Previously, an unshadowed `shell` name was undefined.

Errors in rendering propagate to the calling process. In particular, a filesystem error from `myteam_list` writes its diagnostic to stderr, raises `SystemExit(1)`, and aborts rendering.
