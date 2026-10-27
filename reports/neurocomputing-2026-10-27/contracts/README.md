# Contract reproductions

`reproduce_candidates.py` records what the audit layer does with each candidate input. It was run on the
unmodified `932cf1c` code (`candidates-before-932cf1c.json`) and on the fixed working tree
(`candidates-after-fix.json`). `old_api_probe_test.py` asserts the new contracts through the API that
already existed at `932cf1c`. Its outputs are `probe-unmodified-932cf1c.txt` (16 of 17 checks fail; the one
that passes is a valid-input control) and `probe-fixed-working-tree.txt` (17 of 17 pass). Local
user-directory names in recorded paths are redacted as `<user>`, and the session's temporary directory
as `<scratch>`. Nothing else in these outputs was edited.
