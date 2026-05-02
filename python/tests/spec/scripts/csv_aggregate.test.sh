#!/usr/bin/env bash
# Group-by aggregation over a CSV using awk.

cat <<'CSV' > /tmp/data.csv
dept,name,salary
eng,alice,90
eng,bob,85
ops,carol,70
eng,dan,95
ops,eve,75
sales,fran,60
CSV

# Skip header, sum salaries per department.
tail -n +2 /tmp/data.csv |
  awk -F, '{ totals[$1] += $3; counts[$1]++ } END { for (d in totals) print d, totals[d], counts[d] }' |
  sort
