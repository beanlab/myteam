# Meeting Minutes Speaker-Identified Transcription Workflow

Created on: 2026-04-22
Created by: Codex

## Details

Add a meeting-minutes workflow that can produce a local raw transcript using a transcription model
with speaker tracking / diarization, then use that transcript to generate minutes that preserve
speaker identity where it is useful.

This backlog item is intended to improve the current meeting-minutes flow in two places:

- raw transcript generation should support a local model that distinguishes speakers instead of
  producing an undifferentiated transcript
- minute-generation prompting should explicitly identify who said what when recording decisions,
  action items, and notable discussion points

The workflow should capture enough structure that minutes can attribute statements to the correct
speaker when the transcript makes that possible. Prompting for minute generation should therefore
include guidance such as:

- identify the speaker for key decisions, requests, follow-up items, and commitments
- preserve uncertainty when speaker identity is ambiguous instead of inventing an attribution
- keep speaker attribution in the minutes concise and useful rather than turning the minutes into a
  full transcript

Relevant design questions for later planning include:

- which local transcription model or tool should be used for speaker-aware transcription
- what transcript format should represent diarization output for downstream prompting
- how minutes should display speaker attribution consistently
- whether the workflow should support optional speaker-name mapping after diarization

## Out-of-scope

- selecting and integrating a specific transcription model in this backlog item
- broader meeting-minutes format changes unrelated to speaker attribution
- any hosted or cloud-only transcription dependency

## Dependencies

No explicit backlog dependencies yet.
