SELECT
    child.audit_row_id,
    child.{key} AS record_ref,
    NOT EXISTS (
        SELECT 1
        FROM {parent} AS parent
        WHERE parent.{parent_key} = child.{child_key}
    ) AS failed
FROM {source} AS child
