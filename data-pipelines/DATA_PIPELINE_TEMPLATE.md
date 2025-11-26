# Data Pipeline Development Template
## Medallion Architecture Design Framework

This document provides a structured approach to building data pipelines following the Landing Zone → Bronze → Silver → Gold architecture pattern. Use this as a template when prompting Claude Code to build data pipelines.

---

## 🎯 Pre-Development Phase: Discovery & Requirements

### Critical Questions to Answer BEFORE Coding

#### 1. **Data Source Understanding**
- [ ] What is the data source? (API, database, files, stream, etc.)
- [ ] Is authentication required? What type?
- [ ] What are the rate limits/quotas?
- [ ] What is the total data volume?
- [ ] How frequently does the data update?
- [ ] Are there multiple endpoints or just one?
- [ ] Is there API documentation available?

#### 2. **Schema Discovery**
- [ ] Is the schema documented or must it be discovered?
- [ ] Are all fields documented or are there hidden fields?
- [ ] What are the nested structures (arrays, objects)?
- [ ] Which fields are required vs optional?
- [ ] What are the data types for each field?
- [ ] Are there field naming inconsistencies?

#### 3. **Data Characteristics**
- [ ] What is the expected data volume (rows/day, GB/month)?
- [ ] What is the historical data availability?
- [ ] How frequently should we pull data?
- [ ] Are updates incremental or full refresh?
- [ ] Is there a natural partition key (date, region, etc.)?
- [ ] What is the data retention requirement?

#### 4. **Business Requirements**
- [ ] Who are the end users?
- [ ] What questions do they need to answer?
- [ ] What is the required query performance?
- [ ] Are there specific compliance requirements (HIPAA, GDPR, etc.)?
- [ ] What is the acceptable data latency?
- [ ] Are there downstream consumers or integrations?

---

## 📥 LANDING ZONE: Raw Data Ingestion

### Purpose
Store raw data EXACTLY as received from the source with minimal transformation. This is your "source of truth" backup.

### Key Design Decisions

#### 1. **Extraction Strategy**
**Questions:**
- [ ] Full load or incremental?
- [ ] If incremental, what is the watermark field? (created_date, updated_date, id)
- [ ] Batch or streaming ingestion?
- [ ] What is the extraction frequency? (hourly, daily, weekly, real-time)
- [ ] How do we handle pagination? (offset/limit, cursor, page tokens)
- [ ] What is the backfill strategy for historical data?

**Template Considerations:**
```
Extraction Method: [API/Database/File/Stream]
Frequency: [Real-time/Hourly/Daily/Weekly/Monthly]
Incremental Strategy: [Watermark field/Full refresh/CDC]
Pagination: [Method and limits]
Backfill: [How to load historical data]
```

#### 2. **File Format & Organization**
**Questions:**
- [ ] What raw format to use? (JSON, JSONL, CSV, Avro, Parquet)
- [ ] How should files be organized in S3? (partitioning scheme)
- [ ] What is the file naming convention?
- [ ] Should files be compressed? (gzip, snappy, zstd)
- [ ] What metadata should be captured per file?

**Template Considerations:**
```
Format: [JSONL for semi-structured, CSV for structured, etc.]
Partitioning: s3://bucket/[source]/[entity]/[year]/[month]/[day]/
Naming: [entity]_[timestamp]_batch[number].[ext]
Compression: [gzip/snappy/none]
Metadata: [source_system, extraction_time, record_count, etc.]
```

#### 3. **Error Handling & Reliability**
**Questions:**
- [ ] What happens if the source is unavailable?
- [ ] How do we handle partial failures?
- [ ] What retry strategy should we use?
- [ ] How do we track what was successfully extracted?
- [ ] What alerts are needed for failures?
- [ ] How do we handle schema evolution at source?

**Template Considerations:**
```
Retry Logic: [Exponential backoff, max attempts]
Failure Handling: [Continue/Stop/Partial commit]
Monitoring: [CloudWatch metrics, SNS alerts]
Idempotency: [How to safely re-run]
State Management: [Track extraction progress]
```

#### 4. **Infrastructure Choices**
**Questions:**
- [ ] Lambda, Glue Python Shell, or something else?
- [ ] What timeout/memory requirements?
- [ ] What IAM permissions are needed?
- [ ] Should it run in VPC?
- [ ] What is the cost optimization strategy?

**Template for Lambda:**
```python
- Runtime: Python 3.11+
- Timeout: [Based on data volume]
- Memory: [1024MB baseline, increase if needed]
- Concurrency: [Reserved if time-sensitive]
- Environment Variables: [API keys, bucket names, config]
```

---

## 🥉 BRONZE LAYER: Immutable Raw Storage

### Purpose
Store complete, immutable raw data in a queryable format. This is the "audit trail" - preserve EVERYTHING.

### Key Design Decisions

#### 1. **Storage Format**
**Questions:**
- [ ] Iceberg, Delta Lake, or plain Parquet?
- [ ] Why Iceberg? (ACID transactions, schema evolution, time travel)
- [ ] What compression codec? (Snappy for speed, ZSTD for size)
- [ ] Should we use columnar format even for nested data?

**Template Considerations:**
```
Format: Iceberg (recommended for ACID + time travel)
Compression: Snappy (good balance of speed/size)
File Size Target: 128-256 MB per file
Partitioning: BY (fiscal_year) or (date_partition)
```

#### 2. **Schema Design - CRITICAL DECISION**
**Questions:**
- [ ] Store as single JSON string column OR fully parsed schema?
- [ ] Pros of JSON string: Schema-agnostic, zero data loss
- [ ] Pros of parsed schema: Better query performance, compression
- [ ] Hybrid approach: JSON string + extracted key fields for partitioning?

**Recommended Template:**
```sql
CREATE TABLE bronze_table (
    -- Metadata (ALWAYS include these)
    source_file STRING,
    ingestion_timestamp TIMESTAMP,
    processing_timestamp TIMESTAMP,
    pipeline_version STRING,

    -- Key fields for partitioning/filtering (extracted)
    partition_key_1 TYPE,  -- e.g., fiscal_year INT
    partition_key_2 TYPE,  -- e.g., entity_id STRING

    -- Complete raw record
    raw_json STRING  -- OR fully parsed schema
)
USING iceberg
PARTITIONED BY (partition_key_1)
```

**Decision Matrix:**
| Approach | Pros | Cons | Use When |
|----------|------|------|----------|
| JSON String | Zero data loss, schema flexibility | Slower queries, larger size | Schema changes frequently |
| Parsed Schema | Fast queries, better compression | Must handle schema evolution | Schema is stable |
| Hybrid | Balance of both | More complex | Most enterprise use cases |

#### 3. **Data Quality at Bronze**
**Questions:**
- [ ] Do we validate anything at bronze? (Generally: NO)
- [ ] Do we deduplicate? (Generally: NO, preserve everything)
- [ ] Do we filter any records? (Generally: NO)
- [ ] Exception: Remove PII if required by compliance

**Bronze Layer Philosophy:**
```
✅ DO: Preserve complete raw data
✅ DO: Add metadata (source, timestamps)
✅ DO: Partition for query performance
❌ DON'T: Drop fields
❌ DON'T: Transform data
❌ DON'T: Filter records (unless compliance requires)
❌ DON'T: Deduplicate
```

#### 4. **Merge Strategy**
**Questions:**
- [ ] Append-only or upsert?
- [ ] If upsert, what are the merge keys?
- [ ] How do we handle late-arriving data?
- [ ] Do we need SCD (Slowly Changing Dimensions)?

**Template:**
```sql
MERGE INTO bronze_table target
USING temp_data source
ON target.primary_key = source.primary_key
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

---

## 🥈 SILVER LAYER: Cleaned & Conformed Data

### Purpose
Business-ready, cleaned, conformed data with quality checks and normalization applied.

### Key Design Decisions

#### 1. **Data Model Selection - MOST CRITICAL DECISION**
**Questions:**
- [ ] Star schema, snowflake, data vault, or flat/wide tables?
- [ ] What are the natural dimensions vs facts?
- [ ] What is the grain of the fact table(s)?
- [ ] Are there many-to-many relationships requiring bridge tables?
- [ ] Do we need SCD Type 2 for any dimensions?

**Decision Framework:**

**Star Schema** (Recommended for most analytics)
```
When to use:
✅ Clear facts and dimensions
✅ Analytics/BI use case
✅ Query performance is priority
✅ End users understand dimensional modeling

Example:
- fact_sales (grain: one row per transaction)
- dim_customer
- dim_product
- dim_date
```

**Snowflake Schema**
```
When to use:
✅ Need to normalize dimensions further
✅ Storage optimization is critical
✅ Complex hierarchies exist

Example:
- dim_customer → dim_city → dim_state → dim_country
```

**Data Vault**
```
When to use:
✅ High rate of schema change
✅ Need complete audit trail
✅ Multiple source systems
✅ Enterprise data warehouse

Tables:
- Hubs (business keys)
- Links (relationships)
- Satellites (descriptive attributes)
```

**Flat/Wide Tables**
```
When to use:
✅ Simple data model
✅ Single subject area
✅ Self-service analytics
✅ Machine learning features

Example:
- One wide table with all project attributes
```

#### 2. **Dimension Table Design**
**Questions:**
- [ ] What makes a good dimension?
- [ ] What are the natural keys vs surrogate keys?
- [ ] Which dimensions need SCD Type 2 tracking?
- [ ] Are there conformed dimensions (shared across facts)?
- [ ] What is the cardinality of each dimension?

**Dimension Table Template:**
```sql
CREATE TABLE dim_[entity_name] (
    -- Surrogate key (recommended)
    [entity]_key STRING,  -- MD5 hash or auto-increment

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
| SCD Type | Use When | Example |
|----------|----------|---------|
| Type 1 (Overwrite) | History not needed | Product color |
| Type 2 (Add row) | History required | Customer address, pricing |
| Type 3 (Add column) | Limited history | current_status, previous_status |

#### 3. **Fact Table Design**
**Questions:**
- [ ] What is the grain? (One row per what?)
- [ ] What are the measures (numeric metrics)?
- [ ] What are the foreign keys to dimensions?
- [ ] Is this an accumulating snapshot, transaction, or periodic snapshot?
- [ ] Are there degenerate dimensions (dimensions in the fact)?

**Fact Table Template:**
```sql
CREATE TABLE fact_[business_process] (
    -- Surrogate key (optional for fact tables)
    fact_key STRING,

    -- Foreign keys to dimensions
    dim_[entity1]_key STRING,
    dim_[entity2]_key STRING,
    dim_date_key INT,  -- YYYYMMDD format often used

    -- Degenerate dimensions (if any)
    transaction_id STRING,

    -- Measures (numeric, additive if possible)
    quantity DECIMAL(18,2),
    amount DECIMAL(18,2),
    cost DECIMAL(18,2),

    -- Semi-additive measures (snapshot balances)
    balance DECIMAL(18,2),

    -- Non-additive measures (ratios, percentages)
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
| Accumulating Snapshot | Process lifecycle | Order pipeline (ordered → shipped → delivered) |

#### 4. **Bridge Tables (Many-to-Many)**
**Questions:**
- [ ] Which relationships are many-to-many?
- [ ] Do we need bridge tables or can we use arrays?
- [ ] What is the performance impact of joins vs nested arrays?

**Bridge Table Template:**
```sql
CREATE TABLE bridge_[entity1]_[entity2] (
    entity1_key STRING,
    entity2_key STRING,

    -- Optional: Attributes of the relationship
    relationship_type STRING,
    effective_date DATE,

    -- Metadata
    processing_timestamp TIMESTAMP
)
USING iceberg
PARTITIONED BY (entity1_key)  -- Partition by most commonly filtered
```

**Arrays vs Bridge Tables:**
| Approach | Pros | Cons | Use When |
|----------|------|------|----------|
| Arrays | Simpler schema, fewer joins | Harder to query, limited SQL support | Small lists (< 100 items) |
| Bridge Tables | Standard SQL, easy filtering | More tables, more joins | Large lists, need to filter on items |

#### 5. **Data Quality & Transformations**
**Questions:**
- [ ] What quality checks should we apply?
- [ ] How do we handle nulls/missing values?
- [ ] What standardization is needed? (dates, names, addresses)
- [ ] How do we handle duplicates?
- [ ] What referential integrity checks are needed?

**Data Quality Template:**
```python
Quality Checks:
✅ Null handling: [Reject/Default/Flag]
✅ Duplicate handling: [Merge strategy/Keep latest/Flag]
✅ Referential integrity: [Validate FK exists]
✅ Data type validation: [Cast errors → null or reject]
✅ Business rule validation: [Amount >= 0, date ranges valid]
✅ Standardization: [Trim strings, uppercase codes, date formats]

Monitoring:
- Track null percentages per column
- Track duplicate counts
- Track failed validation counts
- Alert on anomalies (> X% failure rate)
```

#### 6. **Slowly Changing Dimensions (SCD)**
**Questions:**
- [ ] Which dimensions change over time?
- [ ] Do we need historical tracking?
- [ ] What triggers a new version? (Any field change or specific fields?)
- [ ] How do we identify the current version?

**SCD Type 2 Implementation Template:**
```sql
-- Merge with SCD Type 2 logic
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
    INSERT (
        business_key,
        attribute_hash,
        effective_from_date,
        effective_to_date,
        is_current,
        ...
    ) VALUES (
        source.business_key,
        source.attribute_hash,
        current_timestamp(),
        '9999-12-31',
        true,
        ...
    )
```

---

## 🥇 GOLD LAYER: Business-Ready Aggregates

### Purpose
Denormalized, pre-aggregated, use-case-specific tables optimized for consumption.

### Key Design Decisions

#### 1. **Aggregation Strategy**
**Questions:**
- [ ] What are the key business metrics/KPIs?
- [ ] What aggregation levels are needed? (daily, monthly, by product, etc.)
- [ ] Should we pre-compute or compute on-demand?
- [ ] How do we balance freshness vs performance?

**Template Considerations:**
```
Aggregation Types:
1. Time-based rollups (daily → weekly → monthly → yearly)
2. Dimensional rollups (product → category → department)
3. Metric calculations (running totals, moving averages, YoY growth)
4. Pre-joined wide tables for specific dashboards

Decision Matrix:
Pre-compute if:
✅ Query runs frequently (> 10x per day)
✅ Aggregation is expensive (> 1 minute)
✅ Data changes infrequently

On-demand if:
✅ Ad-hoc analysis
✅ Data changes constantly
✅ Storage cost > compute cost
```

#### 2. **Gold Table Design**
**Questions:**
- [ ] Who is the consumer? (Dashboard, ML model, API, report)
- [ ] What is the SLA for data freshness?
- [ ] Should this be a materialized view or physical table?
- [ ] Do we need incremental refresh or full rebuild?

**Gold Table Template:**
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

**Example Gold Tables:**
```
gold_sales_daily_by_product
gold_customer_360_view  -- Wide denormalized customer table
gold_kpi_dashboard  -- Pre-joined for specific dashboard
gold_ml_features  -- Feature engineering for ML models
```

#### 3. **Refresh Strategy**
**Questions:**
- [ ] Full refresh or incremental?
- [ ] What is the refresh frequency?
- [ ] How do we handle late-arriving data?
- [ ] Do we need point-in-time accuracy?

**Refresh Patterns:**
```
1. Full Refresh (Simple but expensive)
   - TRUNCATE and reload
   - Use when: Small data, simplicity valued

2. Incremental Append (Efficient for immutable data)
   - Only process new partitions
   - Use when: Time-series data, no updates

3. Incremental Merge (Complex but optimal)
   - MERGE with time-based filter
   - Use when: Updates possible, large data

4. Materialized View (Database-managed)
   - Automatic refresh by query engine
   - Use when: Supported by platform
```

---

## 🔧 Cross-Cutting Concerns

### 1. **Partitioning Strategy**
**Questions:**
- [ ] What is the most common filter in queries?
- [ ] What is the cardinality of partition columns?
- [ ] How do we avoid small files problem?

**Partitioning Best Practices:**
```
✅ DO:
- Partition by time (date, year/month) for time-series
- Partition by high-cardinality categorical (region, category)
- Target 128MB - 1GB per partition
- Use date/int types for partition columns (better performance)

❌ DON'T:
- Partition by high-cardinality string (ID fields)
- Create > 10,000 partitions
- Partition columns with skewed distribution
- Use timestamp for partition (use date instead)

Example Good:
PARTITIONED BY (year, month, region)  -- ~144 partitions/year

Example Bad:
PARTITIONED BY (customer_id)  -- millions of partitions
```

### 2. **Naming Conventions**
**Questions:**
- [ ] What naming standard to use?
- [ ] How to distinguish layers?
- [ ] How to version schemas?

**Recommended Naming Convention:**
```
Tables:
[layer]_[domain]_[entity]_[type]
  └─ bronze_finance_transactions
  └─ silver_finance_transactions
  └─ gold_finance_daily_sales

Columns:
- snake_case for all columns
- Suffix with _key for keys
- Suffix with _date, _timestamp for temporal
- Suffix with _amt, _qty, _pct for measures

Files:
[entity]_[timestamp]_[batch].[ext]
  └─ transactions_20240101_120000_batch0001.jsonl

Buckets:
[company]-[layer]-[environment]
  └─ acme-bronze-prod
  └─ acme-silver-dev
```

### 3. **Metadata Management**
**Questions:**
- [ ] How do we track lineage?
- [ ] What metadata should every table have?
- [ ] How do we document the schema?

**Required Metadata Columns:**
```sql
-- Add to EVERY table at EVERY layer
source_file STRING,              -- Tracking lineage
ingestion_timestamp TIMESTAMP,   -- When landed in landing zone
processing_timestamp TIMESTAMP,  -- When processed to this layer
pipeline_version STRING,         -- Code version for reproducibility
record_hash STRING               -- For change detection (optional)
```

### 4. **Error Handling Philosophy**
**Questions:**
- [ ] Fail fast or continue processing?
- [ ] How do we handle bad records?
- [ ] What needs to be alerted vs logged?

**Error Handling Template:**
```
Landing Zone:
❌ STOP if: Source unavailable, auth failure
✅ CONTINUE if: Individual record malformed (log & skip)

Bronze Layer:
❌ STOP if: Cannot write to storage, corruption detected
✅ CONTINUE if: Schema variation (store as-is)

Silver Layer:
❌ STOP if: Cannot read bronze, critical transformation fails
✅ CONTINUE if: Optional field missing, non-critical validation fails
⚠️  QUARANTINE: Records failing quality checks (separate table)

Gold Layer:
❌ STOP if: Cannot read silver, business logic error
✅ CONTINUE if: Metric calculation returns null (use default)

Monitoring:
- Alert on: Job failures, > 5% record failures, SLA breach
- Log only: Individual record issues, schema changes detected
```

### 5. **Testing Strategy**
**Questions:**
- [ ] What to test at each layer?
- [ ] Unit tests vs integration tests?
- [ ] How to test data quality?

**Testing Template:**
```python
Landing Zone Tests:
✅ API connectivity and auth
✅ Pagination logic
✅ File format correctness
✅ Retry logic
✅ Idempotency

Bronze Layer Tests:
✅ All source fields preserved
✅ Metadata columns populated
✅ Partition creation
✅ Merge logic (upsert vs append)

Silver Layer Tests:
✅ Schema transformations correct
✅ Data quality rules applied
✅ Referential integrity
✅ No duplicate keys
✅ Row counts (source vs target)

Gold Layer Tests:
✅ Aggregations mathematically correct
✅ Metric definitions match business logic
✅ Historical data preserved correctly

Data Quality Tests (SQL-based):
-- Row count checks
-- Null checks on critical fields
-- Referential integrity
-- Duplicate checks
-- Range/validity checks
```

---

## 📋 TEMPLATE: Complete Pipeline Specification

Use this template when prompting Claude Code to build a pipeline:

```markdown
# [PIPELINE NAME] Data Pipeline Specification

## 1. DATA SOURCE
- **Type**: [API/Database/File/Stream]
- **URL/Connection**: [URL or connection string]
- **Authentication**: [API key/OAuth/IAM/None]
- **Rate Limits**: [X requests/second]
- **Documentation**: [Link to API docs]

## 2. DATA CHARACTERISTICS
- **Volume**: [X records/day, Y GB/month]
- **Update Frequency**: [Real-time/Hourly/Daily/Weekly]
- **Historical Data**: [Available from YYYY-MM-DD]
- **Schema Stability**: [Stable/Changes frequently]
- **Data Retention**: [Keep for X years]

## 3. SCHEMA EXPLORATION (CRITICAL!)
- [ ] API documentation reviewed
- [ ] Test API call made to discover complete response
- [ ] All nested structures documented
- [ ] Field data types identified
- [ ] Optional vs required fields noted
- **Action**: Create `docs/api_fields_mapping.md` with ALL fields

## 4. LANDING ZONE DESIGN
- **Extraction Method**: [Lambda/Glue/Airflow/Other]
- **Incremental Strategy**: [Watermark field: XXX / Full refresh]
- **Pagination**: [Offset/limit, max XXX per request]
- **File Format**: [JSONL/CSV/Parquet]
- **Partitioning**: `s3://bucket/[source]/[entity]/year=YYYY/month=MM/day=DD/`
- **Naming**: `[entity]_YYYYMMDD_HHmmss_batchNNNN.[ext]`
- **Schedule**: [Cron expression]

## 5. BRONZE LAYER DESIGN
- **Table Format**: [Iceberg/Delta/Parquet] - Recommend Iceberg for ACID
- **Schema Approach**: [JSON string + key fields / Fully parsed]
- **Partitioning**: `PARTITIONED BY ([partition_key])`
- **Merge Strategy**: [Append / Upsert on (key1, key2)]
- **Tables**:
  - `bronze_[entity_name]`

## 6. SILVER LAYER DESIGN
- **Data Model**: [Star Schema/Snowflake/Flat/Data Vault]
- **Dimensions**:
  - `dim_[entity1]` - Primary key: [XXX], SCD: [Type 1/2]
  - `dim_[entity2]` - Primary key: [XXX], SCD: [Type 1/2]
- **Facts**:
  - `fact_[business_process]` - Grain: [One row per XXX]
  - Measures: [amount, quantity, etc.]
- **Bridge Tables**:
  - `bridge_[entity1]_[entity2]` - For many-to-many relationships
- **Data Quality**:
  - Null handling: [Strategy]
  - Duplicate handling: [Strategy]
  - Validation rules: [List]

## 7. GOLD LAYER DESIGN (Optional)
- **Use Cases**:
  - `gold_[use_case_1]` - [Description, refresh frequency]
  - `gold_[use_case_2]` - [Description, refresh frequency]
- **Aggregation Level**: [Daily/Monthly/By dimension]
- **Refresh Strategy**: [Full/Incremental]

## 8. ORCHESTRATION
- **Tool**: [Step Functions/Airflow/Other]
- **Workflow**: Lambda → Bronze → Silver → Gold
- **Schedule**: [Cron expression]
- **Error Handling**: [Retry policy, alerts]

## 9. INFRASTRUCTURE
- **Lambda**: [Timeout, memory, concurrency]
- **Glue**: [Worker type, worker count, Glue version]
- **S3 Buckets**: [List buckets and purposes]
- **IAM Roles**: [List roles and permissions]
- **Monitoring**: [CloudWatch metrics, SNS alerts]

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

## 🎯 Example Prompts for Claude Code

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

Please create an exploration notebook showing your discovery process.
```

### Full Pipeline Build Prompt
```
Create a complete AWS CDK data pipeline following the medallion architecture
(Landing → Bronze → Silver → Gold) for [DATA SOURCE].

CRITICAL REQUIREMENTS:
1. ZERO DATA LOSS - Capture ALL fields from the API (not just a subset)
2. Follow the pattern from [reference pipeline if exists]
3. Use Iceberg table format for bronze/silver/gold layers
4. Implement comprehensive error handling and retry logic

DATA SOURCE:
[Use the template specification above]

DELIVERABLES:
- Lambda function for API ingestion with pagination
- Glue job for bronze layer (raw to Iceberg)
- Glue job for silver layer (normalized star schema)
- Glue job for gold layer (if needed for specific use cases)
- CDK Stack with all infrastructure
- Step Functions orchestration
- EventBridge scheduling
- Unit tests
- Comprehensive README with query examples
- API field mapping documentation

Please create the complete pipeline ensuring every field from the API
is preserved and accessible in the silver layer.
```

---

## 💡 Key Principles to Remember

### The Golden Rules
1. **Landing Zone**: Never transform, only extract
2. **Bronze Layer**: Never drop fields, preserve everything
3. **Silver Layer**: Apply business logic, ensure quality
4. **Gold Layer**: Optimize for specific use cases

### Common Pitfalls to Avoid
❌ Assuming field documentation is complete (always explore the API)
❌ Dropping fields in bronze "because we don't need them now"
❌ Not planning for schema evolution
❌ Over-engineering gold layer before understanding use cases
❌ Forgetting to add metadata columns
❌ Creating too many small partitions
❌ Not testing with real data volumes

### Success Criteria
✅ All source fields are accessible in silver layer
✅ Data lineage can be traced from gold → silver → bronze → landing
✅ Pipeline can be re-run without duplicating data (idempotent)
✅ Clear documentation for end users
✅ Automated testing covers critical paths
✅ Monitoring and alerts configured
✅ Query performance meets SLA

---

This template should be customized based on:
- Organization's standards and tools
- Specific data source characteristics
- Business requirements and use cases
- Team expertise and preferences
- Budget and performance constraints
