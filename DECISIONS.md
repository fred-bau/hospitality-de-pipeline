# Design decisions

Why the pipeline is built the way it is. Each entry covers the decision, the reason and the trade-off.

## Architecture

### ELT, not ETL
Raw files are loaded into Snowflake unchanged, and every transformation happens in the warehouse with dbt.
- **Why:** the raw data stays available for reprocessing, transformations are version-controlled SQL with tests and lineage, and Snowflake does the heavy lifting.
- **Trade-off:** raw data, including fields that are never used, is stored in the warehouse.

### S3 as the landing zone, not a Snowflake internal stage
Files are uploaded to S3 first, then loaded with `COPY INTO`.
- **Why:** S3 decouples storage from the warehouse. The raw files can be reloaded, read by other tools, and kept cheaply. Versioning protects against accidental overwrites, and lifecycle rules clean up old versions.
- **Trade-off:** one more system with its own credentials. An internal stage (`PUT`) would have been simpler for a single-warehouse project.

### Airflow with LocalExecutor
The DAG runs in Docker Compose with the LocalExecutor instead of the CeleryExecutor from the official template.
- **Why:** one machine and a handful of sequential tasks. Celery adds a worker, Redis and more failure points without any benefit at this scale.
- **Trade-off:** no distributed workers. Moving to Celery or Kubernetes would be the step up for a larger pipeline.

### `dbt build` as a single task
The DAG has three tasks: extract, load and `dbt build`. It started with separate `dbt snapshot`, `dbt run` and `dbt test` tasks.
- **Why:** `dbt build` runs snapshots, models and tests in dependency order and tests each model right after building it. If a test fails, the models downstream of it are skipped and keep their last tested version, so faulty data doesn't reach the reporting tables, the dashboard or the RAG index. With `run` followed by `test`, every table is rebuilt first and problems are only found afterwards.
- **Trade-off:** less detail in the Airflow UI (one task instead of one per step). The dbt log shows which model or test failed. One Airflow task per model (for example with Astronomer Cosmos) would be the next step for a larger project.
- **Limit:** the failing model itself has already been rebuilt, and views always show the current raw data. Fully seamless protection would need write-audit-publish (build and test in a separate schema, then swap).

### Pinned dbt versions
The Dockerfile installs `dbt-core==1.12.5` and `dbt-snowflake==1.12.1`.
- **Why:** reproducible builds. Without a pin, every rebuild of the image installs the newest version, which can change behaviour without any change to the code. Updates are made deliberately: raise the version, run the DAG, commit.

## Ingestion

### One raw table per city and file type
`RAW.raw_<type>_<city>`, 9 tables for 3 cities × 3 file types.
- **Why:** each load is independent, so a failed city doesn't affect the others, and each table can be reconciled against exactly one file.
- **Trade-off:** more tables. The union happens in dbt (see below).

### Explicit file lists that fail loudly
The extract script builds the list of every expected file and fails before uploading anything if one is missing. It also compares each file's size in S3 with the local size.
- **Why:** an early version silently loaded 0 files when paths didn't match. A pipeline that "succeeds" with no data is worse than one that fails.

### Full refresh with reconciliation
Each run truncates the table and reloads it with `COPY INTO ... force = true` and `on_error = 'ABORT_STATEMENT'`. Afterwards, the row count in the table must equal the rows `COPY` reported.
- **Why:** Inside Airbnb publishes complete snapshots, not increments. A full refresh is simple, idempotent (rerunning never creates duplicates), and the reconciliation catches partial loads.
- **Trade-off:** every run reloads everything. Fine at this size (a few million rows). Incremental loading would be the next step for larger data.

### `escape_unenclosed_field = none`
- **Why:** one review consisted of a single backslash, which Snowflake treated as an escape character and which broke the row's parsing. Inside Airbnb's CSVs don't use backslash escaping, so turning it off is correct for this source.

## Security

### Key-pair authentication for Snowflake
- **Why:** password logins are blocked once MFA is enforced, and an automated pipeline can't answer an MFA prompt. Key pairs are the standard for service connections.

### A dedicated least-privilege role for the pipeline
The loader and dbt run as `PIPELINE_ROLE`, not `ACCOUNTADMIN`. The role can use the warehouse, load RAW (`select`, `insert`, `truncate`) and owns the TRANSFORM and SNAPSHOTS schemas, because dbt replaces tables there and only an owner may do that. It sits under `SYSADMIN` in the role hierarchy, so admins still see everything it owns.
- **Why:** least privilege. The pipeline can't create or drop databases, manage users or change account settings, so a leaked key or a faulty statement can only affect the pipeline's own data. `ACCOUNTADMIN` is reserved for manual admin work.
- **Verified:** as `PIPELINE_ROLE`, reading RAW and TRANSFORM works, and `create database` fails with "insufficient privileges".

### Secrets only in `.env` and `~/.snowflake`
`docker-compose.yaml` only references `${VARIABLES}`. The real values live in an untracked `.env` file, and the private key lives outside the repo.
- **Why:** GitHub push protection once blocked a commit that contained hardcoded AWS keys. The fix was to move every credential into `.env` and rewrite the unpushed commits.
- **Verified:** the pushed git history contains no credentials (no AWS key IDs anywhere, no hardcoded passwords in `docker-compose.yaml`, and `.env` was never committed), so no keys had to be rotated.

### Reviewer names are dropped
`stg_airbnb__reviews` doesn't select `reviewer_name`.
- **Why:** the names add nothing to the analysis, and personal data that isn't needed shouldn't be carried through the models, the RAG index or a public dashboard (data minimisation).

## Modelling

### One set of models for all cities
The city list lives in a dbt variable, and the macro `union_city_sources` unions the per-city raw tables and adds a `city` column.
- **Why:** adding a city means changing one list instead of copying models. City is the anchor dimension for every downstream model.

### Reviews grain: review × listing
`review_id` is not unique: hotels attach the same review to several room listings.
- **Why:** the natural grain of the source is review × listing, so the test is `unique_combination_of_columns [review_id, listing_id]`. Totals of reviews use `count(distinct review_id)` to avoid counting shared reviews twice.

### A separate reporting layer, one model per grain
`rpt_city_summary` (city), `rpt_neighbourhood_summary` (city × neighbourhood), `rpt_city_monthly` (city × month).
- **Why:** medians and percentiles can't be rolled up from a finer grain (a median of medians is not the median), and averages of averages are wrong when group sizes differ. Each figure is computed directly at the grain it's shown at. Tableau uses one data source per grain for the same reason.

### Snapshot of listings (SCD type 2)
`scd_raw_listings` tracks changes in 17 listing attributes such as price, availability and host.
- **Why:** Inside Airbnb only provides the current state, so price history can only be built by snapshotting every run.
- **Trade-off:** a snapshot can't be backfilled. The history starts at the first run.

### Missing prices are null, not 0
In `dim_listings`, `price_eur` uses `try_to_number(..., 10, 2)`. A missing price stays null.
- **Why:** a missing price means "unknown" (usually a listing that isn't actively offered), not "free". With 0, averages were pulled down and the cheapest listing "cost" €0. With null, averages and medians only use known prices. `try_to_number` also keeps the cents and returns null instead of failing on unexpected values.
- **Scale:** 44% of Paris listings, 17% of Barcelona's and 10% of Florence's show no price. This also explains the low occupancy in Paris: almost half of its listings aren't actively offered.
- **Test:** the old `not_null` test was replaced by `dbt_utils.accepted_range` (every known price must be > 0), because null is now a valid value.
- **Rule of thumb:** `coalesce(..., 0)` only where "nothing" really means zero (review counts), never where it means "unknown" (prices, ratings).

### Materialisations
Staging and intermediate models are views, and marts and reporting models are tables.
- **Why:** views are cheap and always current for light transformations. Tables keep queries from Tableau and the RAG loader fast.

### Tests
The test suite combines generic tests (keys, accepted values, composite uniqueness) and singular tests (all cities present; the city summary reconciles with staging).
- **Why:** tests catch the kind of silent errors that happened during development, such as missing cities and duplicate grains.

## Dashboard

- **Separate data sources per grain,** connected by a filter action on `City`, instead of one wide table that would force aggregations at the wrong grain.
- **The last month of reviews is excluded**, because the snapshot was taken partway through it.
- **The number of decimal places follows the range of the data:** ratings show 2 decimals because almost all of them fall between 4.5 and 4.9.
- **Trend lines** in the price-vs-demand chart show a correlation across neighbourhoods, not the effect of a host changing their price. Location drives both price and demand.

## RAG layer

- **Integrated embedding in Pinecone** (`llama-text-embed-v2`): Pinecone embeds the text itself, so no separate embedding model or API key is needed.
- **A balanced sample:** 1,500 reviews per city, using a fixed random seed for reproducibility and deduplicated on `review_id`. This keeps Paris from dominating every search.
- **`city` as metadata:** searches and answers can be filtered to one city.
- **Full refresh of the namespace** on every load, so the index never mixes old and new samples.
- **Grounded answers:** Claude answers only from the retrieved reviews, cites them by number, and says when the reviews don't contain the answer.

## Known limitations

- **Survivorship bias in reviews:** the reviews file only covers listings that still existed at the time of the snapshot. Deleted listings take their reviews with them (for example, Parisians who rented out their home only for the 2024 Olympics), so older months are undercounted, and the time series should be read for seasonality, not growth.
- **Reviews are a proxy for stays:** not every guest leaves a review.
- **Booked nights and revenue are estimates:** they come from Inside Airbnb's occupancy model, not from actual booking data.
- **Inactive listings are included in city totals:** listing counts and the median booked nights include listings that show no price and aren't actively offered (44% in Paris), which pulls the Paris median down.


