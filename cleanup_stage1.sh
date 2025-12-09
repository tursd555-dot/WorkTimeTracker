#!/bin/bash
# Stage 1: Cleanup Script for WorkTimeTracker

echo "=== WorkTimeTracker Cleanup Stage 1 ==="
echo ""

# Backup count
BACKUP_COUNT=$(find . -name "*.bak*" -type f | wc -l)
PYCACHE_COUNT=$(find . -name "__pycache__" -type d | wc -l)

echo "📊 Current state:"
echo "  - Backup files (.bak*): $BACKUP_COUNT"
echo "  - Python cache dirs: $PYCACHE_COUNT"
echo ""

# === STEP 1: Remove all .bak files ===
echo "🗑️  Step 1: Removing backup files..."
find . -name "*.bak*" -type f -delete
echo "  ✓ Removed $BACKUP_COUNT backup files"

# === STEP 2: Remove __pycache__ ===
echo "🗑️  Step 2: Removing Python cache..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
echo "  ✓ Removed $PYCACHE_COUNT cache directories"

# === STEP 3: Remove temporary files ===
echo "🗑️  Step 3: Removing temporary files..."
rm -f temp_credentials.json
rm -f project_bundle_*.txt
rm -f diagnostics_report.json
echo "  ✓ Removed temporary files"

# === STEP 4: Move diagnostic scripts ===
echo "📦 Step 4: Moving diagnostic scripts to dev-tools..."
mv check_*.py dev-tools/diagnostic/ 2>/dev/null
mv diagnose_*.py dev-tools/diagnostic/ 2>/dev/null
mv show_*.py dev-tools/diagnostic/ 2>/dev/null
mv reset_*.py dev-tools/diagnostic/ 2>/dev/null
mv cleanup_*.py dev-tools/diagnostic/ 2>/dev/null
echo "  ✓ Moved diagnostic scripts"

# === STEP 5: Move fix scripts ===
echo "📦 Step 5: Moving fix scripts to dev-tools..."
mv fix_*.py dev-tools/fix/ 2>/dev/null
mv restore_*.py dev-tools/fix/ 2>/dev/null
echo "  ✓ Moved fix scripts"

# === STEP 6: Move test scripts ===
echo "📦 Step 6: Moving test scripts to dev-tools..."
mv test_*.py dev-tools/test/ 2>/dev/null
echo "  ✓ Moved test scripts"

# === STEP 7: Move build scripts ===
echo "📦 Step 7: Moving build scripts to dev-tools..."
mv build_*.py dev-tools/build/ 2>/dev/null
mv bundle_*.py dev-tools/build/ 2>/dev/null
mv create_project_bundle.py dev-tools/build/ 2>/dev/null
mv map_project.py dev-tools/build/ 2>/dev/null
mv archiver.py dev-tools/build/ 2>/dev/null
echo "  ✓ Moved build scripts"

# === STEP 8: Move misc scripts ===
echo "📦 Step 8: Moving miscellaneous scripts..."
mv 11.py dev-tools/ 2>/dev/null
mv quick_patch.py dev-tools/ 2>/dev/null
mv create_break_sheets.py dev-tools/ 2>/dev/null
echo "  ✓ Moved misc scripts"

echo ""
echo "✅ Cleanup Stage 1 completed!"
echo ""
echo "📊 Summary:"
find . -name "*.py" -type f ! -path "./dev-tools/*" ! -path "./tools/*" | wc -l | xargs echo "  - Production Python files:"
find ./dev-tools -name "*.py" -type f | wc -l | xargs echo "  - Dev-tools Python files:"
du -sh . | awk '{print "  - Total size: " $1}'
