# `lunarlab.audit.provenance`

Source: [`lunarlab/audit/provenance.py`](../../lunarlab/audit/provenance.py)

Versioned provenance records for reward definitions.

A reward definition has two identities, and they are recorded separately because they establish different
things:

* the **declared definition** -- the original-reward weight and every term's JSON description. Its digest,
  ``definition_sha256``, is a full SHA-256 of the canonical JSON. Two terms with equal descriptions and
  different code have equal digests, so this digest alone never establishes what a term computes;
* the **implementation** -- the Python source file that defines each term's callables, with that file's
  SHA-256, and whether the file is tracked and unmodified in the git checkout at a known revision.

``implementation_identity`` summarises the second: ``recorded`` (every file tracked and unmodified at a
known revision), ``file-digests-only`` (every file hashed, but at least one untracked or modified, or no
revision), ``incomplete`` (at least one callable's source could not be located, as for code typed into
an interactive session), or ``no-terms`` (the definition is the original reward alone). A file digest covers that file's bytes only, not the modules it imports, data it
reads or the library versions it runs on.

The 16-character ``terms_hash`` of earlier records (schema 0) keeps its meaning and is carried as
``legacy_terms_hash`` so new records can be matched to old ones.

### `callable_records(fns: 'list[Callable]') -> 'list[dict[str, Any]]'`

Where each callable is defined, that file's SHA-256, and its git status (tracked, modified).

### `definition_document(terms: 'Mapping[str, RewardTerm]', original_weight: 'float') -> 'dict[str, Any]'`

The declared definition: the original-reward weight and every term's description (validated).

### `definition_sha256(terms: 'Mapping[str, RewardTerm]', original_weight: 'float') -> 'str'`

Full SHA-256 of the canonical JSON of the declared definition.

### `reward_provenance(terms: 'Mapping[str, RewardTerm] | None', original_weight: 'float', *, adapter: 'TaskAdapter | None' = None) -> 'dict[str, Any]'`

The versioned provenance record of a reward definition (see the module docstring for scopes).

## Constants

- `PROVENANCE_SCHEMA` = `'lunarlab.reward-provenance/1'`
- `SCOPES` = `{'definition_sha256': 'SHA-256 of the canonical JSON of the declared term descriptions and the original-reward weight. I…`
- `TYPE_CHECKING` = `False`
