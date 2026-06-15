# Manages Rosters

## Purpose

List, download, and update rosters.

---

# Context

A roster is downloadable content from a remote repository. A managed local
roster install records source provenance in a `.source.yml` file at the root of
the managed folder.

---

# Action

The caller lists available rosters, downloads a roster, or updates managed
downloaded roster content.

---

# Interaction

| Action | Outcome |
| --- | --- |
| `myteam list` | Connects to the configured roster repository and prints one available roster entry path per line. |
| `myteam download <roster>` without a destination | Installs the roster under the selected local root using the same relative folder path as the remote roster. |
| `myteam download <roster> [destination]` | Downloads the requested roster folder content into one managed local folder, writes `.source.yml`, preserves relative file paths from the roster, and prints progress. |
| `myteam update <path>` | Refreshes the managed folder rooted at the selected local root from its recorded source metadata. |
| `myteam update` without a path | Scans the selected local root recursively for managed download roots and updates each one independently. |

---

# Outcome

Downloaded content becomes available on disk as a managed folder, ready to be
loaded or edited. The managed folder records enough source information for
later provenance-aware updates.

During update, `myteam` reads `.source.yml` from each targeted managed folder,
re-downloads content from the recorded repository, roster path, and ref,
deletes existing content at the managed target before re-download, and then
performs the same managed install behavior as `download` using the recorded
source metadata.

The command exits with an error when roster listing cannot reach a valid remote
repository, when a requested roster does not exist, when a requested roster
resolves to a single file instead of a folder, when the destination already
contains the same managed source and should be updated instead, when unrelated
content already exists at the destination, when remote metadata or downloads
fail, when an update target lacks `.source.yml`, when no managed folders are
found for a root update, when source metadata is invalid or incomplete, or when
the recorded remote roster no longer exists, resolves to a file, or cannot be
fetched.

---

# Related Scenarios

- [../local_tree/uses_selected_local_root.md](../local_tree/uses_selected_local_root.md)
