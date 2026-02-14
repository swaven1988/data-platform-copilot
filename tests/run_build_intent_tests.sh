#!/usr/bin/env bash

API="http://127.0.0.1:8001"
REPORT="tests/reports/latest_report.json"

mkdir -p tests/reports

echo "Running Build Intelligence Test Suite..."
echo ""

echo "Test 1: Dry run with minimal input (expect warnings)"
T1=$(curl -s -X POST "$API/build/intent" \
  -H "Content-Type: application/json" \
  -d '{"requirement":"read raw_db.t1","dry_run": true}')

echo "Test 2: Dry run with full input (expect high confidence)"
T2=$(curl -s -X POST "$API/build/intent" \
  -H "Content-Type: application/json" \
  -d '{"requirement":"job name: test_job env=qa read from raw_db.t1 write to curated_db.t2 partition by data_dt merge schedule: 0 6 * * * timezone: UTC pyspark","dry_run": true}')

echo "Test 3: Full build from requirement"
T3=$(curl -s -X POST "$API/build/intent" \
  -H "Content-Type: application/json" \
  -d '{"requirement":"job name: test_job_build env=dev read from raw_db.t1 write to curated_db.t2 partition by data_dt merge schedule: 0 6 * * * timezone: UTC pyspark","dry_run": false}')

echo "Generating consolidated report..."

cat <<EOF > $REPORT
{
  "test1_dryrun_defaults": $T1,
  "test2_dryrun_clean": $T2,
  "test3_full_build": $T3
}
EOF

echo "Test suite completed."
echo "Report saved at: $REPORT"
