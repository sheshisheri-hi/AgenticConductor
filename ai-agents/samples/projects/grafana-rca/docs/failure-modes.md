# Failure modes (draft from sample triples)

| Pattern | Symptoms | Likely cause | Mitigation |
|---|---|---|---|
| Time-range freeze | Panels spin after changing time window | Query timeout / unbounded datapoints | Raise timeout, cap maxDataPoints, cancel in-flight |
| Refresh pile-up | Freeze with auto-refresh on | Overlapping queries | Abort prior requests |
| Alert flap | Alerts toggle every interval | Transient datasource errors | Grace period / last-known state |
| Datasource switch blank | Graphs empty after switching DS | Stale cached UID | Clear query cache |
