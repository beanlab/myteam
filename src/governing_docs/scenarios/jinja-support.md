# Jinja2 Template Rendering for Markdown Body

The body of a Markdown skill or workflow will be rendered with jinja2 before being passed as the prompt. Full jinja2 syntax is supported.

The fields of the input dictionary (for workflows, if provided) are passed as variables to the rendering (e.g. `render(**inputs)`).

The following `myteam` functions are also included in the jinja environment:

- `myteam_explain()` - i.e. `myteam explain`, injects instructions to the agent for how to use `myteam` skills and workflows 
- `myteam_list(path)` - i.e. `myteam list <path>`; lists the `myteam` resources in the specified directory (you'll want to also use `explain` if you list resources)
- `myteam_onboard()` - i.e. `myteam onboard`, injects the governing docs for `myteam`; useful if you want your agent to help you develop a harness.

The following utility functions are also included in the jinja environment:

- `read_file(file)` - injects the contents of the file; useful for composing a skill/workflow from multiple documents; if the included file has `jinja` included in the suffix, it is also rendered in the same environment before inclusion.

Paths are relative to the Markdown document, not the current directory of whoever is invoking the document.

Input field names take precedent over jinja environment functions; avoid naming conflicts. 

Errors in rendering the document propagate to the calling process.
