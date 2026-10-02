# Deprecated Onboarding Command

`myteam onboard` is deprecated and will be removed in a future release.

For compatibility, it prints a warning to stderr directing the caller to use `myteam explain`, then returns exactly the same content as `myteam explain`. It no longer prints the governing-document tree.

The public `onboard()` Python API and the `myteam_onboard()` Jinja helper follow the same deprecated behavior. New integrations should use `explain_resources()` or `myteam_explain()` instead.
