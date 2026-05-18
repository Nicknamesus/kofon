# Seed data

Source of truth for content the chatbot reads. Domain experts edit YAML/CSV
here; the loader (`python -m app.seed.load`) upserts into Postgres.

## Files

| File                                | What it seeds                  | Natural key                              |
| ----------------------------------- | ------------------------------ | ---------------------------------------- |
| `main_conversation_types.yaml`      | Router branches                | `code`                                   |
| `use_cases.yaml`                    | Industry × application pairs   | `(industry, application)`                |
| `product_types/<code>.yaml`         | One product family per file    | `code`                                   |
| `products/<family_code>.yaml`       | SKUs in one family per file    | `sku`                                    |
| `problems/<family_code>.yaml`       | Problems + nested solutions    | `(product_type_code, problem code)`      |
| `use_case_fits.csv`                 | Many-to-many fits + scores     | `(industry, application, product_type_code)` |

The loader is idempotent — running it twice does nothing on the second run.
Update a row by editing its YAML/CSV entry; the loader will upsert by
natural key.

## Demo scope (Phase 1)

Only one family — **CaesarPlanetary** (planetary gearboxes) — is seeded
end-to-end. Other families (Rollsate, Elitewave, Servolux, KGV, SpiralBevel)
get added by the content team in later phases. Phase 1's smoke test just
needs `search_products` to return real SKUs for at least one family.
