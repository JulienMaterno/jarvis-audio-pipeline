# Claude API Setup (Architecture Update)

The audio pipeline no longer talks to Claude directly.
All transcript analysis now happens inside the
[`jarvis-intelligence-service`](https://github.com/JulienMaterno/jarvis-intelligence-service).

## What changed?

- The audio pipeline only downloads audio, transcribes it, stores the raw
  transcript in Supabase, and calls the intelligence service.
- All Anthropic/Claude keys, model configuration, and analyzer logic now live in
  the intelligence service (the "brain" of the ecosystem).

## Do I still need a Claude key?

Yes, but you only configure it in the intelligence service:

1. Follow the instructions in that repository (`README.md`) to set
	`ANTHROPIC_API_KEY` (or `CLAUDE_API_KEY`).
2. Deploy the intelligence service so it can process `/api/v1/process/{transcript_id}`
	calls from the audio pipeline.

## How do I test the flow now?

1. Run the intelligence service locally (`uvicorn main:app --reload`).
2. Start the audio pipeline and use `/process/upload` (or the Telegram bot) to
	upload a sample audio file.
3. Check the Supabase tables (transcripts, meetings, reflections, journals,
	tasks) to confirm that the analyzer output landed correctly.

If you need to debug the analyzer itself, run the debug scripts inside the
intelligence service repository (e.g. `scripts/debug/test_claude_multi.py`).

## Why the change?

- Keeps all LLM logic in a single service (simpler auditing + cheaper tokens).
- Audio pipeline remains a lightweight ingestion/transcription worker.
- Matches the architecture contract documented in the ecosystem README.

If you still see references to Claude in this repo, open an issue—they're
legacy leftovers that should be removed.
