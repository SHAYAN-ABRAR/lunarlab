# Contract reproductions

`reproduce_candidates.py` records what the audit layer does with each candidate input. It was run on the
unmodified `932cf1c` code (`candidates-before-932cf1c.json`) and on the fixed working tree
(`candidates-after-fix.json`). `old_api_probe_test.py` asserts the new contracts through the API that
already existed at `932cf1c`. Its outputs are `probe-unmodified-932cf1c.txt` (16 of 17 checks fail; the one
that passes is a valid-input control) and `probe-fixed-working-tree.txt` (17 of 17 pass). Local
user-directory names in recorded paths are redacted as `<user>`, and the session's temporary directory
as `<scratch>`. Nothing else in these outputs was edited.

## Reward-definition identity: a gap found on 28 October

The reproduction found two terms with identical descriptions, paying 1 and 1,000, that share a 16-hex
`terms_hash` (`reward_definition_identity` in the candidate files). The legacy hash keeps that meaning by
design. The versioned provenance record of 27 October (schema 1) added a full definition digest and each
defining file's digest and git status.

While the claims were checked on 28 October, `provenance_identity_check.py` showed that schema 1 still
could not tell this pair apart. The two lambdas share a description, a file and the qualified name
`Custom.<lambda>`. Two closures of one factory were equally indistinguishable.

| Pair with equal descriptions | `11145b3`, schema 1 (`provenance-identity-11145b3.txt`) | Fixed tree, schema 2 (`provenance-identity-fixed-working-tree.txt`) |
|---|---|---|
| Two lambdas in one class body (the reproduced candidate) | not told apart | told apart |
| Two closures of one factory | not told apart | told apart |
| Two named functions | told apart | told apart |

Schema 2 records, for each callable:

- its first line;
- a SHA-256 of its own source text;
- the JSON form of the values it captures and of its default arguments.

A captured value without a JSON form makes the identity `incomplete`. Two lambdas on one source line with
equal captured values remain indistinguishable, and module-level names a callable reads are covered only by
the file digest. The 11145b3 tree was taken with `git archive 11145b3 lunarlab` and imported through
`PYTHONPATH`; the first line of each output names the tree used.
