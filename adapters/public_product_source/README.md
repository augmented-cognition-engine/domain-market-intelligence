# ACE Market public-product source adapter

This separately versioned package implements the public `ace.intelligence.SourceAdapter`
protocol for one narrow public-product JSON shape. It has no `ace.extensions` entry point and is
not part of the ACE Market extension wheel or Domain Pack.

The host must verify the installed adapter wheel SHA-256, bind that exact `sha256:<hex>` value into
the active capability binding, and pass the same value to `PublicProductSourceAdapter`. The adapter
does not attempt to embed or discover its own wheel hash because a wheel cannot reliably contain a
self-referential digest.

The package includes no network client. A host injects a reviewed `PublicProductTransport`
implementation. The P1C2 conformance proof injects a deterministic result for
`https://public.example.test/products/edge-x1`; `.test` is deliberately unreachable fixture
material and is not evidence of a public capture.

Actual public-evidence capture remains gated on both:

- an explicitly authorized, stable public HTTPS endpoint; and
- a reviewed transport that denies credentials and redirects, bounds the response, validates every
  resolved and connected address as globally routable throughout use, and applies DNS-rebinding
  protection.

The adapter only validates that retrieval result and extracts `product_name`, `listed_price`, and
`currency` as canonical inert JSON. The source-specific extraction locator is adapter-owned and
fixed at `json-pointer:/listed_price`; a transport-supplied different locator fails closed and can
never become acquisition provenance. The adapter does not authorize access, resolve actors or
governed state, mint receipts, map entities, persist records, convert currency, or infer motive or
impact.

## License

Apache-2.0 under the repository [`LICENSE`](../../LICENSE) and [`NOTICE`](../../NOTICE).
