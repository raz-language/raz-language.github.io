# json

A strict, allocation-conscious JSON toolkit for Raz.

Version 0.1.0 exposes the standard library's validated streaming lexer and flat-arena DOM through a versioned package API, then adds an incremental state-checked writer and RFC 6901 JSON Pointer resolution.

## Highlights

- Strict RFC 8259 syntax, UTF-8 validation, depth limits, and trailing-data rejection.
- Borrowed or owned DOM parsing with reusable node capacity.
- Escaped-key-aware object lookup and typed number/bool access.
- A writer that prevents duplicate roots, missing object values, mismatched containers, and excessive nesting.
- JSON Pointer lookup with `~0`/`~1` decoding and canonical array-index validation.

The package depends on `serde` for ecosystem compatibility; its low-level parser and writer remain usable without deriving or allocating an intermediate value tree.
