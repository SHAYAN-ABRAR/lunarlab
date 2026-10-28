# `lunarlab.audit.provenance`

Source: [`lunarlab/audit/provenance.py`](../../lunarlab/audit/provenance.py)

Versioned provenance records for reward definitions.

A reward definition has two identities, and they are recorded separately because they establish different
things:

* the **declared definition** -- the original-reward weight and every term's JSON description. Its digest,
  ``definition_sha256``, is a full SHA-256 of the canonical JSON. Two terms with equal descriptions and
  different code have equal digests, so this digest alone never establishes what a term computes;
* the **implementation** -- for each of a term's callables, the Python source file that defines it, with
  that file's SHA-256 and whether the file is tracked and unmodified in the git checkout at a known
  revision, and the callable itself: its first line, a digest of its own source text, and the values it
  captures (closure cells and default arguments). Two lambdas in one file, or two closures of one factory,
  can share a description and a file; their source text or captured values tell them apart.

``implementation_identity`` summarises the second: ``recorded`` (every file tracked and unmodified at a
known revision), ``file-digests-only`` (every file hashed, but at least one untracked or modified, or no
revision), ``incomplete`` (at least one callable's source could not be located, as for code typed into
an interactive session, or a captured value has no JSON form), or ``no-terms`` (the definition is the
original reward alone). A file digest covers that file's bytes only, not the modules it imports, data it
reads or the library versions it runs on. Module-level names a callable reads are covered only by the file
digest. Two lambdas on one source line with equal captured values remain indistinguishable.

Schema 1 (27 October 2026) recorded the file but not the callable's own source or captured values. The
16-character ``terms_hash`` of earlier records (schema 0) keeps its meaning and is carried as
``legacy_terms_hash`` so new records can be matched to old ones.

### class `UnrecordableValue`(ValueError)

A value a term's callable captures has no JSON form.

`UnrecordableValue(...)`


### `callable_records(fns: 'list[Callable]') -> 'list[dict[str, Any]]'`

For each callable: its file, that file's SHA-256 and git status, and the callable's own identity.

### `definition_document(terms: 'Mapping[str, RewardTerm]', original_weight: 'float') -> 'dict[str, Any]'`

The declared definition: the original-reward weight and every term's description (validated).

### `definition_sha256(terms: 'Mapping[str, RewardTerm]', original_weight: 'float') -> 'str'`

Full SHA-256 of the canonical JSON of the declared definition.

### `reward_provenance(terms: 'Mapping[str, RewardTerm] | None', original_weight: 'float', *, adapter: 'TaskAdapter | None' = None) -> 'dict[str, Any]'`

The versioned provenance record of a reward definition (see the module docstring for scopes).

## Constants

- `MAX_CAPTURE_DEPTH` = `3`
- `PROVENANCE_SCHEMA` = `'lunarlab.reward-provenance/2'`
- `SCOPES` = `{'definition_sha256': 'SHA-256 of the canonical JSON of the declared term descriptions and the original-reward weight. I…`
- `TYPE_CHECKING` = `False`
