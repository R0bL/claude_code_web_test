# Data Pipeline Development Template
## Medallion Architecture Design Framework

A structured approach to building data pipelines following the Landing Zone → Bronze → Silver → Gold architecture pattern.

---

## Pre-Development Phase: Discovery & Requirements

### Critical Questions to Answer Before Coding

**Data Source Understanding**
- What is the data source? (API, database, files, stream)
- Authentication type and requirements?
- Rate limits and quotas?
- Total data volume?
- Update frequency?
- API documentation available?

**Schema Discovery**
- Is schema documented or must it be discovered?
- Are all fields documented or are there hidden fields?
- What are the nested structures (arrays, objects)?
- Which fields are required vs optional?
- What are the data types for each field?

**Data Characteristics**
- Expected data volume (rows/day, GB/month)?
- Historical data availability?
- Pull frequency needed?
- Updates incremental or full refresh?
- Natural partition key (date, region)?
- Data retention requirements?

**Business Requirements**
- Who are the end users?
- What questions do they need to answer?
- Required query performance?
- Compliance requirements (HIPAA, GDPR)?
- Acceptable data latency?
- Downstream consumers or integrations?

---

## LANDING ZONE: Raw Data Ingestion

**Purpose**: Store raw data exactly as received from source with minimal transformation.

### Extraction Strategy

**Key Decisions:**
- Full load or incremental?
- If incremental, what is the watermark field?
- Batch or streaming ingestion?
- Extraction frequency?
- Pagination method and limits?
- Backfill strategy for historical data?

**Template:**
```
Extraction Method: [API/Database/File/Stream]
Frequency: [Real-time/Hourly/Daily/Weekly/Monthly]
Incremental Strategy: [Watermark field/Full refresh/CDC]
Pagination: [Method and limits]
Backfill: [Strategy for historical data]
```

### File Format & Organization

**Key Decisions:**
- Raw format? (JSON, JSONL, CSV, Avro, Parquet)
- File organization in S3? (partitioning scheme)
- File naming convention?
- Compression? (gzip, snappy, zstd)
- Metadata to capture per file?

**Template:**
```
Format: JSONL (semi-structured) or CSV (structured)
Partitioning: s3://bucket/[source]/[entity]/[year]/[month]/[day]/
Naming: [entity]_[timestamp]_batch[number].[ext]
Compression: gzip or snappy
Metadata: source_system, extraction_time, record_count
```

### Error Handling & Reliability

**Key Decisions:**
- What happens if source is unavailable?
- How to handle partial failures?
- Retry strategy?
- How to track successful extractions?
- What alerts for failures?
- How to handle schema evolution at source?

**Template:**
```
Retry Logic: Exponential backoff, max 3 attempts
Failure Handling: Continue/Stop/Partial commit
Monitoring: CloudWatch metrics, SNS alerts
Idempotency: Track extraction progress, enable safe re-runs
State Management: DynamoDB or S3 state file
```

### Infrastructure Choices

**Key Decisions:**
- Lambda, Glue Python Shell, or other?
- Timeout and memory requirements?
- IAM permissions needed?
- VPC required?
- Cost optimization strategy?

**Lambda Template:**
```
Runtime: Python 3.11+
Timeout: Based on data volume (5-15 minutes typical)
Memory: 1024MB baseline
Concurrency: Reserved if time-sensitive
Environment Variables: API keys, bucket names, config
```

---

## BRONZE LAYER: Immutable Raw Storage

**Purpose**: Store complete, immutable raw data in queryable format. This is the audit trail.

### Storage Format

**Key Decisions:**
- Iceberg, Delta Lake, or plain Parquet?
- Compression codec? (Snappy for speed, ZSTD for size)
- Columnar format for nested data?

**Template:**
```
Format: Iceberg (ACID transactions, schema evolution, time travel)
Compression: Snappy (balance of speed/size)
File Size Target: 128-256 MB per file
Partitioning: BY (fiscal_year) or (date_partition)
```

### Schema Design - Critical Decision

**Store as JSON string OR fully parsed schema?**

| Approach | Pros | Cons | Use When |
|----------|------|------|----------|
| JSON String | Zero data loss, schema flexibility | Slower queries, larger size | Schema changes frequently |
| Parsed Schema | Fast queries, better compression | Must handle schema evolution | Schema is stable |
| Hybrid | Balance of both | More complex | Most enterprise use cases (recommended) |

**Recommended Hybrid Template:**
```sql
CREATE TABLE bronze_table (
    -- Metadata (always include)
    source_file STRING,
    ingestion_timestamp TIMESTAMP,
    processing_timestamp TIMESTAMP,
    pipeline_version STRING,

    -- Key fields for partitioning/filtering
    partition_key_1 TYPE,
    partition_key_2 TYPE,

    -- Complete raw record
    raw_json STRING
)
USING iceberg
PARTITIONED BY (partition_key_1)
```

### Data Quality at Bronze

**Philosophy:**
- DO: Preserve complete raw data
- DO: Add metadata (source, timestamps)
- DO: Partition for query performance
- DON'T: Drop fields
- DON'T: Transform data
- DON'T: Filter records (unless compliance requires)
- DON'T: Deduplicate

**Exception**: Remove PII if required by compliance

### Merge Strategy

**Key Decisions:**
- Append-only or upsert?
- If upsert, what are the merge keys?
- How to handle late-arriving data?
- Need SCD (Slowly Changing Dimensions)?

**Template:**
```sql
MERGE INTO bronze_table target
USING temp_data source
ON target.primary_key = source.primary_key
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

---

## SILVER LAYER: Cleaned & Conformed Data

**Purpose**: Business-ready, cleaned, conformed data with quality checks and normalization.

### Data Model Selection - Most Critical Decision

**Key Questions:**
- Star schema, snowflake, data vault, or flat tables?
- What are the natural dimensions vs facts?
- What is the grain of the fact table(s)?
- Many-to-many relationships requiring bridge tables?
- Need SCD Type 2 for any dimensions?

**Star Schema** (Recommended for analytics)
```
Use when:
- Clear facts and dimensions
- Analytics/BI use case
- Query performance is priority

Example:
- fact_sales (grain: one row per transaction)
- dim_customer, dim_product, dim_date
```

**Snowflake Schema**
```
Use when:
- Need to normalize dimensions further
- Storage optimization is critical
- Complex hierarchies exist
```

**Data Vault**
```
Use when:
- High rate of schema change
- Need complete audit trail
- Multiple source systems
- Enterprise data warehouse

Tables: Hubs, Links, Satellites
```

**Flat/Wide Tables**
```
Use when:
- Simple data model
- Single subject area
- Self-service analytics
- Machine learning features
```

### Dimension Table Design

**Key Questions:**
- What makes a good dimension?
- Natural keys vs surrogate keys?
- Which dimensions need SCD Type 2 tracking?
- Conformed dimensions (shared across facts)?
- Cardinality of each dimension?

**Template:**
```sql
CREATE TABLE dim_[entity_name] (
    -- Surrogate key
    [entity]_key STRING,

    -- Natural business keys
    [business_key_1] TYPE,
    [business_key_2] TYPE,

    -- Descriptive attributes
    [attribute_1] TYPE,
    [attribute_2] TYPE,

    -- SCD Type 2 columns (if needed)
    effective_from_date TIMESTAMP,
    effective_to_date TIMESTAMP,
    is_current BOOLEAN,

    -- Metadata
    processing_timestamp TIMESTAMP,
    pipeline_version STRING
)
USING iceberg
```

**SCD Type Decision:**
| Type | Use When | Example |
|------|----------|---------|
| Type 1 (Overwrite) | History not needed | Product color |
| Type 2 (Add row) | History required | Customer address, pricing |
| Type 3 (Add column) | Limited history | current_status, previous_status |

### Fact Table Design

**Key Questions:**
- What is the grain? (One row per what?)
- What are the measures (numeric metrics)?
- Foreign keys to dimensions?
- Fact type: accumulating snapshot, transaction, or periodic snapshot?
- Degenerate dimensions (dimensions in the fact)?

**Template:**
```sql
CREATE TABLE fact_[business_process] (
    -- Surrogate key (optional)
    fact_key STRING,

    -- Foreign keys to dimensions
    dim_[entity1]_key STRING,
    dim_[entity2]_key STRING,
    dim_date_key INT,

    -- Degenerate dimensions
    transaction_id STRING,

    -- Additive measures
    quantity DECIMAL(18,2),
    amount DECIMAL(18,2),
    cost DECIMAL(18,2),

    -- Semi-additive measures
    balance DECIMAL(18,2),

    -- Non-additive measures
    percentage DECIMAL(5,2),

    -- Metadata
    processing_timestamp TIMESTAMP,
    pipeline_version STRING
)
USING iceberg
PARTITIONED BY (date_partition)
```

**Fact Table Types:**
| Type | Grain | Use When |
|------|-------|----------|
| Transaction | One event | Sales, clicks, orders |
| Periodic Snapshot | One time period | Daily balances, monthly totals |
| Accumulating Snapshot | Process lifecycle | Order pipeline stages |

### Bridge Tables (Many-to-Many)

**Key Questions:**
- Which relationships are many-to-many?
- Bridge tables or arrays?
- Performance impact of joins vs nested arrays?

**Template:**
```sql
CREATE TABLE bridge_[entity1]_[entity2] (
    entity1_key STRING,
    entity2_key STRING,

    -- Optional relationship attributes
    relationship_type STRING,
    effective_date DATE,

    -- Metadata
    processing_timestamp TIMESTAMP
)
USING iceberg
PARTITIONED BY (entity1_key)
```

**Arrays vs Bridge Tables:**
| Approach | Pros | Cons | Use When |
|----------|------|------|----------|
| Arrays | Simpler schema, fewer joins | Harder to query | Small lists (< 100 items) |
| Bridge Tables | Standard SQL, easy filtering | More tables, joins | Large lists, need filtering |

### Data Quality & Transformations

**Key Decisions:**
- What quality checks to apply?
- How to handle nulls/missing values?
- What standardization needed?
- How to handle duplicates?
- What referential integrity checks?

**Template:**
```
Quality Checks:
- Null handling: Reject/Default/Flag
- Duplicate handling: Merge strategy/Keep latest/Flag
- Referential integrity: Validate FK exists
- Data type validation: Cast errors handling
- Business rule validation: Amount >= 0, date ranges valid
- Standardization: Trim strings, uppercase codes, date formats

Monitoring:
- Track null percentages per column
- Track duplicate counts
- Track failed validation counts
- Alert on anomalies (> X% failure rate)
```

### Slowly Changing Dimensions (SCD)

**Key Questions:**
- Which dimensions change over time?
- Need historical tracking?
- What triggers a new version?
- How to identify current version?

**SCD Type 2 Implementation:**
```sql
MERGE INTO dim_table target
USING (
    SELECT *,
           MD5(CONCAT(key_field1, key_field2)) as business_key,
           MD5(CONCAT(attr1, attr2, attr3)) as attribute_hash
    FROM source_data
) source
ON target.business_key = source.business_key
   AND target.is_current = true
WHEN MATCHED AND target.attribute_hash != source.attribute_hash THEN
    UPDATE SET
        effective_to_date = current_timestamp(),
        is_current = false
WHEN NOT MATCHED THEN
    INSERT (business_key, attribute_hash, effective_from_date,
            effective_to_date, is_current, ...)
    VALUES (source.business_key, source.attribute_hash, current_timestamp(),
            '9999-12-31', true, ...)
```

---

## GOLD LAYER: Business-Ready Aggregates

**Purpose**: Denormalized, pre-aggregated, use-case-specific tables optimized for consumption.

### Aggregation Strategy

**Key Questions:**
- Key business metrics/KPIs?
- What aggregation levels needed?
- Pre-compute or compute on-demand?
- Balance freshness vs performance?

**Decision Matrix:**

Pre-compute if:
- Query runs frequently (> 10x per day)
- Aggregation is expensive (> 1 minute)
- Data changes infrequently

On-demand if:
- Ad-hoc analysis
- Data changes constantly
- Storage cost > compute cost

**Aggregation Types:**
1. Time-based rollups (daily → weekly → monthly → yearly)
2. Dimensional rollups (product → category → department)
3. Metric calculations (running totals, moving averages, YoY growth)
4. Pre-joined wide tables for specific dashboards

### Gold Table Design

**Key Questions:**
- Who is the consumer?
- SLA for data freshness?
- Materialized view or physical table?
- Incremental refresh or full rebuild?

**Template:**
```sql
CREATE TABLE gold_[use_case]_[aggregation_level] (
    -- Dimension attributes (denormalized)
    dimension_attr_1 TYPE,
    dimension_attr_2 TYPE,

    -- Time dimensions
    date_key INT,
    year INT,
    month INT,
    quarter INT,

    -- Pre-calculated metrics
    total_amount DECIMAL(18,2),
    count_transactions BIGINT,
    average_value DECIMAL(18,2),
    running_total DECIMAL(18,2),
    year_over_year_growth DECIMAL(5,2),

    -- Metadata
    as_of_date TIMESTAMP,
    processing_timestamp TIMESTAMP
)
USING iceberg
PARTITIONED BY (year, month)
```

**Example Tables:**
- gold_sales_daily_by_product
- gold_customer_360_view
- gold_kpi_dashboard
- gold_ml_features

### Refresh Strategy

**Key Questions:**
- Full refresh or incremental?
- Refresh frequency?
- How to handle late-arriving data?
- Need point-in-time accuracy?

**Refresh Patterns:**

1. **Full Refresh** - TRUNCATE and reload
   - Use when: Small data, simplicity valued

2. **Incremental Append** - Only process new partitions
   - Use when: Time-series data, no updates

3. **Incremental Merge** - MERGE with time-based filter
   - Use when: Updates possible, large data

4. **Materialized View** - Automatic refresh by query engine
   - Use when: Supported by platform

---

## Cross-Cutting Concerns

### Partitioning Strategy

**Key Questions:**
- Most common filter in queries?
- Cardinality of partition columns?
- How to avoid small files problem?

**Best Practices:**

DO:
- Partition by time (date, year/month) for time-series
- Partition by high-cardinality categorical (region, category)
- Target 128MB - 1GB per partition
- Use date/int types for partition columns

DON'T:
- Partition by high-cardinality string (ID fields)
- Create > 10,000 partitions
- Partition columns with skewed distribution
- Use timestamp for partition (use date instead)

**Examples:**
- Good: `PARTITIONED BY (year, month, region)` -- ~144 partitions/year
- Bad: `PARTITIONED BY (customer_id)` -- millions of partitions

### Naming Conventions

**Tables:**
```
[layer]_[domain]_[entity]_[type]
Examples:
- bronze_finance_transactions
- silver_finance_transactions
- gold_finance_daily_sales
```

**Columns:**
- snake_case for all columns
- Suffix with _key for keys
- Suffix with _date, _timestamp for temporal
- Suffix with _amt, _qty, _pct for measures

**Files:**
```
[entity]_[timestamp]_[batch].[ext]
Example: transactions_20240101_120000_batch0001.jsonl
```

**Buckets:**
```
[company]-[layer]-[environment]
Examples:
- acme-bronze-prod
- acme-silver-dev
```

### Metadata Management

**Required Metadata Columns** (add to every table at every layer):
```sql
source_file STRING,              -- Tracking lineage
ingestion_timestamp TIMESTAMP,   -- When landed in landing zone
processing_timestamp TIMESTAMP,  -- When processed to this layer
pipeline_version STRING,         -- Code version for reproducibility
record_hash STRING               -- For change detection (optional)
```

### Error Handling Philosophy

**Landing Zone:**
- STOP if: Source unavailable, auth failure
- CONTINUE if: Individual record malformed (log & skip)

**Bronze Layer:**
- STOP if: Cannot write to storage, corruption detected
- CONTINUE if: Schema variation (store as-is)

**Silver Layer:**
- STOP if: Cannot read bronze, critical transformation fails
- CONTINUE if: Optional field missing, non-critical validation fails
- QUARANTINE: Records failing quality checks (separate table)

**Gold Layer:**
- STOP if: Cannot read silver, business logic error
- CONTINUE if: Metric calculation returns null (use default)

**Monitoring:**
- Alert on: Job failures, > 5% record failures, SLA breach
- Log only: Individual record issues, schema changes detected

### Testing Strategy

**Landing Zone Tests:**
- API connectivity and auth
- Pagination logic
- File format correctness
- Retry logic
- Idempotency

**Bronze Layer Tests:**
- All source fields preserved
- Metadata columns populated
- Partition creation
- Merge logic (upsert vs append)

**Silver Layer Tests:**
- Schema transformations correct
- Data quality rules applied
- Referential integrity
- No duplicate keys
- Row counts (source vs target)

**Gold Layer Tests:**
- Aggregations mathematically correct
- Metric definitions match business logic
- Historical data preserved correctly

**Data Quality Tests (SQL-based):**
- Row count checks
- Null checks on critical fields
- Referential integrity
- Duplicate checks
- Range/validity checks

---

## Complete Pipeline Specification Template

```markdown
# [PIPELINE NAME] Data Pipeline Specification

## 1. DATA SOURCE
- Type: [API/Database/File/Stream]
- URL/Connection: [URL or connection string]
- Authentication: [API key/OAuth/IAM/None]
- Rate Limits: [X requests/second]
- Documentation: [Link to API docs]

## 2. DATA CHARACTERISTICS
- Volume: [X records/day, Y GB/month]
- Update Frequency: [Real-time/Hourly/Daily/Weekly]
- Historical Data: [Available from YYYY-MM-DD]
- Schema Stability: [Stable/Changes frequently]
- Data Retention: [Keep for X years]

## 3. SCHEMA EXPLORATION (CRITICAL)
- [ ] API documentation reviewed
- [ ] Test API call made to discover complete response
- [ ] All nested structures documented
- [ ] Field data types identified
- [ ] Optional vs required fields noted
Action: Create docs/api_fields_mapping.md with ALL fields

## 4. LANDING ZONE DESIGN
- Extraction Method: [Lambda/Glue/Airflow/Other]
- Incremental Strategy: [Watermark field: XXX / Full refresh]
- Pagination: [Offset/limit, max XXX per request]
- File Format: [JSONL/CSV/Parquet]
- Partitioning: s3://bucket/[source]/[entity]/year=YYYY/month=MM/day=DD/
- Naming: [entity]_YYYYMMDD_HHmmss_batchNNNN.[ext]
- Schedule: [Cron expression]

## 5. BRONZE LAYER DESIGN
- Table Format: [Iceberg/Delta/Parquet] - Recommend Iceberg for ACID
- Schema Approach: [JSON string + key fields / Fully parsed]
- Partitioning: PARTITIONED BY ([partition_key])
- Merge Strategy: [Append / Upsert on (key1, key2)]
- Tables: bronze_[entity_name]

## 6. SILVER LAYER DESIGN
- Data Model: [Star Schema/Snowflake/Flat/Data Vault]
- Dimensions:
  - dim_[entity1] - Primary key: [XXX], SCD: [Type 1/2]
  - dim_[entity2] - Primary key: [XXX], SCD: [Type 1/2]
- Facts:
  - fact_[business_process] - Grain: [One row per XXX]
  - Measures: [amount, quantity, etc.]
- Bridge Tables:
  - bridge_[entity1]_[entity2] - For many-to-many relationships
- Data Quality:
  - Null handling: [Strategy]
  - Duplicate handling: [Strategy]
  - Validation rules: [List]

## 7. GOLD LAYER DESIGN (Optional)
- Use Cases:
  - gold_[use_case_1] - [Description, refresh frequency]
  - gold_[use_case_2] - [Description, refresh frequency]
- Aggregation Level: [Daily/Monthly/By dimension]
- Refresh Strategy: [Full/Incremental]

## 8. ORCHESTRATION
- Tool: [Step Functions/Airflow/Other]
- Workflow: Lambda → Bronze → Silver → Gold
- Schedule: [Cron expression]
- Error Handling: [Retry policy, alerts]

## 9. INFRASTRUCTURE
- Lambda: [Timeout, memory, concurrency]
- Glue: [Worker type, worker count, Glue version]
- S3 Buckets: [List buckets and purposes]
- IAM Roles: [List roles and permissions]
- Monitoring: [CloudWatch metrics, SNS alerts]

## 10. DELIVERABLES CHECKLIST
- [ ] Lambda function for data extraction
- [ ] Glue job for bronze layer
- [ ] Glue job for silver layer
- [ ] Glue job for gold layer (if needed)
- [ ] CDK/Terraform infrastructure code
- [ ] Unit tests for Lambda
- [ ] Integration tests for data quality
- [ ] README with deployment instructions
- [ ] API field mapping documentation
- [ ] Query examples for end users
- [ ] Monitoring dashboard/alerts
```

---

## Example Prompts for Claude Code

### Initial Exploration Prompt
```
I need to build a data pipeline for [DATA SOURCE]. Before building, help me:

1. Explore the API at [URL] and document ALL available fields
2. Make test API calls to understand the complete response schema
3. Identify nested structures, arrays, and data types
4. Create a comprehensive field mapping document
5. Recommend a silver layer schema design (star schema with specific tables)

API Details:
- Endpoint: [URL]
- Authentication: [TYPE]
- Rate Limits: [X/second]
- Pagination: [METHOD]

Create an exploration notebook showing your discovery process.
```

### Full Pipeline Build Prompt
```
Create a complete AWS CDK data pipeline following the medallion architecture
(Landing → Bronze → Silver → Gold) for [DATA SOURCE].

CRITICAL REQUIREMENTS:
1. ZERO DATA LOSS - Capture ALL fields from the API
2. Follow the pattern from [reference pipeline if exists]
3. Use Iceberg table format for bronze/silver/gold layers
4. Implement comprehensive error handling and retry logic

DATA SOURCE:
[Use the specification template above]

DELIVERABLES:
- Lambda function for API ingestion with pagination
- Glue job for bronze layer (raw to Iceberg)
- Glue job for silver layer (normalized star schema)
- Glue job for gold layer (if needed)
- CDK Stack with all infrastructure
- Step Functions orchestration
- EventBridge scheduling
- Unit tests
- Comprehensive README with query examples
- API field mapping documentation

Ensure every field from the API is preserved and accessible in the silver layer.
```

---

## Key Principles

### The Golden Rules
1. **Landing Zone**: Never transform, only extract
2. **Bronze Layer**: Never drop fields, preserve everything
3. **Silver Layer**: Apply business logic, ensure quality
4. **Gold Layer**: Optimize for specific use cases

### Common Pitfalls to Avoid
- Assuming field documentation is complete (always explore the API)
- Dropping fields in bronze "because we don't need them now"
- Not planning for schema evolution
- Over-engineering gold layer before understanding use cases
- Forgetting to add metadata columns
- Creating too many small partitions
- Not testing with real data volumes

### Success Criteria
- All source fields are accessible in silver layer
- Data lineage can be traced from gold → silver → bronze → landing
- Pipeline can be re-run without duplicating data (idempotent)
- Clear documentation for end users
- Automated testing covers critical paths
- Monitoring and alerts configured
- Query performance meets SLA

---

**Customize this template based on:**
- Organization standards and tools
- Specific data source characteristics
- Business requirements and use cases
- Team expertise and preferences
- Budget and performance constraints
