# Grammar

`queryX` parses a controlled subset of SQL using a recursive-descent parser. Terminals in
`UPPER CASE` are keywords; quoted terminals are literal punctuation.

## EBNF

```ebnf
query          := select_stmt [ ";" ] EOF ;

select_stmt    := SELECT [ DISTINCT ] select_list
                  FROM table_ref { join_clause }
                  [ where_clause ]
                  [ group_by_clause ]
                  [ having_clause ]
                  [ order_by_clause ]
                  [ limit_clause ] ;

select_list    := select_item { "," select_item } ;
select_item    := "*"
                | expression [ [ AS ] alias ] ;

table_ref      := identifier [ [ AS ] alias ] ;

join_clause    := [ INNER ] JOIN table_ref ON expression
                | [ LEFT | RIGHT ] [ OUTER ] JOIN table_ref ON expression ;

where_clause   := WHERE expression ;

group_by_clause:= GROUP BY column_ref { "," column_ref } ;

having_clause  := HAVING expression ;

order_by_clause:= ORDER BY order_item { "," order_item } ;
order_item     := column_ref [ ASC | DESC ] ;

limit_clause   := LIMIT integer ;

expression     := or_expr ;
or_expr        := and_expr { OR and_expr } ;
and_expr       := not_expr { AND not_expr } ;
not_expr       := NOT not_expr | comparison ;
comparison     := additive [ ( "=" | "<>" | "!=" | "<" | "<=" | ">" | ">=" ) additive ] ;
additive       := multiplicative { ( "+" | "-" ) multiplicative } ;
multiplicative := primary { ( "*" | "/" | "%" ) primary } ;
primary        := literal
                | function_call
                | column_ref
                | "(" expression ")" ;

function_call  := identifier "(" [ DISTINCT ] ( "*" | expression { "," expression } ) ")" ;

column_ref     := identifier [ "." identifier ] ;

literal        := integer | float | string ;
```

## Precedence (lowest to highest)

| Level | Operators |
|---|---|
| 1 | `OR` |
| 2 | `AND` |
| 3 | `NOT` |
| 4 | `= <> != < <= > >=` |
| 5 | `+ -` |
| 6 | `* / %` |
| 7 | `( … )`, function calls, column refs, literals |

## Supported keywords

`SELECT, DISTINCT, FROM, WHERE, INNER, LEFT, RIGHT, OUTER, JOIN, ON, GROUP, BY, HAVING, ORDER,
ASC, DESC, LIMIT, AND, OR, NOT, AS`

## Supported functions

`COUNT`, `SUM`, `AVG`, `MIN`, `MAX` (with optional `DISTINCT`; `COUNT(*)` is supported).

## Supported operators

- Arithmetic: `+ - * / %`
- Comparison: `= <> != < <= > >=`
- Logical: `AND OR NOT`

## Notes and restrictions

- `JOIN` requires an `ON` condition (parser error `PAR004` otherwise).
- `SELECT DISTINCT` lowers to a `Distinct` (δ) relational operator placed between the
  projection and any `ORDER BY`/`LIMIT`; `COUNT(DISTINCT x)` is rendered and planned as a
  distinct-aware aggregate.
- Aggregates are not allowed in `WHERE` (semantic error `SEM015`).
- `HAVING` filters groups after aggregation and may use aggregate calls. It may be used without
  `GROUP BY`, which treats the whole input as one group. A plain column in `HAVING` must be a
  grouping column (`SEM018` otherwise).
- If any aggregate function appears in the select list, every non-aggregated column must
  appear in `GROUP BY` — this is enforced with or without a `GROUP BY` clause (`SEM016`), and
  `SELECT *` cannot be combined with aggregates.
- `LEFT JOIN` is supported. The optimizer keeps the left input as the preserved side: a
  predicate that references only the left input may move into it, but predicates on the right
  input or spanning both inputs stay above the join, and the `ON` condition is never changed by
  `WHERE` predicates.
- `INNER` joins are reordered freely. A `LEFT` join is kept intact as one relation in the join
  order search.
- `RIGHT JOIN` is **parsed** but **rejected during semantic analysis** with diagnostic `SEM017`;
  rewrite it as a `LEFT JOIN` with the tables swapped.
