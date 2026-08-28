"""Migrate existing eight-tool INDX-style layouts from T0-T7 to T1-T8.

Revision ID: 0002_indx_t1_t8
Revises: 0001_initial
"""

from alembic import op

revision = "0002_indx_t1_t8"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE printer_tools
        SET slicer_index = slicer_index + 100
        WHERE printer_id IN (
            SELECT printer_id
            FROM printer_tools
            WHERE archived = false
            GROUP BY printer_id
            HAVING COUNT(*) = 8
               AND MIN(slicer_index) = 0
               AND MAX(slicer_index) = 7
        )
        """
    )
    op.execute(
        """
        UPDATE printer_tools
        SET slicer_index = slicer_index - 99,
            label = 'T' || CAST(slicer_index - 99 AS VARCHAR)
        WHERE slicer_index BETWEEN 100 AND 107
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE printer_tools
        SET slicer_index = slicer_index + 100
        WHERE printer_id IN (
            SELECT printer_id
            FROM printer_tools
            WHERE archived = false
            GROUP BY printer_id
            HAVING COUNT(*) = 8
               AND MIN(slicer_index) = 1
               AND MAX(slicer_index) = 8
        )
        """
    )
    op.execute(
        """
        UPDATE printer_tools
        SET slicer_index = slicer_index - 101,
            label = 'T' || CAST(slicer_index - 101 AS VARCHAR)
        WHERE slicer_index BETWEEN 101 AND 108
        """
    )
