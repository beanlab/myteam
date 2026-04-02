---
name: transcription
description: |
  Transcribe an audio recording into a cleaned raw transcript and a
  meeting summary for this repository.
  Load this skill if you are tasked with transcribing audio files.
---

# Transcription

This skill outlines the process and format for transcribing audio files
into markdown outputs.

## Outputs

Given a recording, use the file creation timestamp to create:

- `../raw-transcripts/<repo name>/YYYY-MM-DD-HHMM.raw.md`
- `meetings/YYYY-MM-DD-HHMM.md`

Use the file creation timestamp, not the current time, for the
filename.

e.g `2026-04-02-1430.md`

## Dependencies

This workflow depends on `faster-whisper` for audio transcription.
If this package is not installed in the current environment,
offer to install it.

## Workflow

1. Read the file creation timestamp from the source audio file.
   On macOS, `stat -f '%SB' -t '%Y-%m-%d-%H%M' <file>` works.
2. Check that `meetings/` and `meetings/raw/` exist; create them if needed.
3. Run transcription locally and save an intermediate raw output if
   needed.
4. Clean the transcript before saving it:
   - fix obvious punctuation and capitalization
   - merge sentence fragments into readable paragraphs
   - correct obvious recognition mistakes
   - do not invent missing content
   - if a phrase is too garbled to recover, mark it as `[unclear]`
5. Save the cleaned raw transcript to
   `meetings/raw/YYYY-MM-DD-HHMM.raw.md`.
6. Write a separate summary to `meetings/YYYY-MM-DD-HHMM.md`.

When writing markdown files, keep the line length to 70 characters max. 

## Summary Format

Default summary structure:

- title
- date
- summary
- main points
- decisions
- tasks
- open questions

Keep the summary document concise and action-oriented. Do not dump the full
transcript into the summary file.

Also, keep the summary document focused on the business of the project.
Omit side conversations, personal details, tangents, etc.

If you are unsure whether something is relevant to the project,
ask the user.

## Local Transcription Notes

- Use repository-local caches when practical so downloaded model
  artifacts stay in the workspace.
- If `faster-whisper` is used, a workable pattern is:
  `HF_HOME=<repo>/.cache/huggingface`
  `XDG_CACHE_HOME=<repo>/.cache`
- CPU transcription is acceptable for one-off meeting recordings.

## Validation

Before finishing:

- verify both output files exist
- confirm the filenames match the source file creation timestamp
- confirm the raw transcript has the `.raw.md` suffix
- confirm the summary points to the raw transcript
