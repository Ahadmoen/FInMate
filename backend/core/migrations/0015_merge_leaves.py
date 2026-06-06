# Auto-generated merge to unify two leaf migrations:
#   - 0010_merge_20260510_1322 (orphan branch, empty operations)
#   - 0014_fix_indexes (latest in the main chain)
#
# Django was rejecting `migrate` with "Conflicting migrations detected;
# multiple leaf nodes in the migration graph", which broke
# finmate-warm-4-ingest. Adding this no-op merge collapses the graph
# to a single leaf again without touching the schema.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_merge_20260510_1322"),
        ("core", "0014_fix_indexes"),
    ]

    operations = []
