SELECT
    audit_row_id,
    {key} AS record_ref,
    {key} IS NULL OR btrim({key}) = ''
        OR count(*) OVER (PARTITION BY {key}) > 1 AS failed
FROM {source}
