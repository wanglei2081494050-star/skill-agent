# Plan checklist

- [ ] Is the largest table scanned with `Seq Scan` / `type=ALL` while a
      selective predicate exists?
- [ ] Do `rows=` estimates differ from `actual rows=` by more than 10x? (stale
      statistics or correlated columns)
- [ ] Is there a `Sort` with `Sort Method: external merge`? (work_mem too small)
- [ ] Is a join on a mismatched column type (int vs text, varchar vs uuid)?
- [ ] Is `LIMIT` pushed before the expensive join?
- [ ] For loop-heavy application code: is the same prepared statement executed
      per row (N+1)?
- [ ] Are there redundant indexes covering the same leading column?
