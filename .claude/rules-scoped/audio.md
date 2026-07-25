# Audio pipeline — read before editing `app/audio/**`

## Pipeline order matters

`AudioProcessor.process_audio()` runs: **convert to WAV 16 kHz (ffmpeg) → normalize (sox) →
add silence (sox)**. Each step writes a new temp file and returns its path.

The order is not cosmetic:

* normalization before resampling operates on different sample statistics;
* silence padding before normalization gets normalized *with* the padding;
* the model expects 16 kHz mono — conversion cannot move later.

Reordering or inserting a step means re-verifying every audio format end to end, not just
the one you were working on.

## External binaries

`ffmpeg` and `sox` are external processes, not libraries. Both are invoked via
`subprocess.run(cmd, check=True, capture_output=True)`.

* **Always check return codes.** `check=True` raises `CalledProcessError`; catch it and
  surface `e.stderr` — a bare "conversion failed" with the actual ffmpeg message discarded
  is the single most common way to lose an hour here.
* Their absence is an environment failure, not a request failure: crash loudly rather than
  degrading.
* A working local ffmpeg does not imply the same version/codecs on orange. Format bugs are
  reproduced on the server.

## Temp files

**Always** `create_temp_file()` from `app/infrastructure/storage.py` — never raw
`tempfile.mktemp` / `NamedTemporaryFile`. Every intermediate path must end up in the cleanup
list; a leaked temp file per request fills the disk slowly enough that nobody notices until
the service dies.

Each pipeline step creates a file. If you add a step, you add a cleanup entry.

## The format trap

3gp and opus each shipped as their own patch. Before writing per-format branch #3, apply the
"name the class" rule (`workflow.md`): if the class of inputs that breaks has more than two
members, the fix is a normalization at the conversion boundary, not another `if`.

New format support = a validator entry (`app/infrastructure/validation.py`, extension + MIME)
AND a real transcription test of that format against the running service. Extension checks
pass trivially; MIME detection via python-magic is where reality intervenes.

## Sources

New input method → a `get_*_file()` function in `app/audio/sources.py` returning the
`(temp_path, filename, error)` triple. Keep the triple: routes branch on `error` being
non-None. Enforce the size limit inside the source function (`_check_size`) — for URL
downloads that means checking *while* streaming, not after.
