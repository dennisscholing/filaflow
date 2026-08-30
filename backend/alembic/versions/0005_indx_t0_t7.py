"""Align eight-tool printer layouts with G-code tool indexes T0-T7.

Revision ID: 0005_indx_t0_t7
Revises: 0004_v030_ui_labels
"""

from alembic import op


revision = "0005_indx_t0_t7"
down_revision = "0004_v030_ui_labels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TEMPORARY TABLE filaflow_indx_tool_migration ON COMMIT DROP AS
        SELECT printer_id
        FROM printer_tools
        GROUP BY printer_id
        HAVING COUNT(*) = 8
           AND MIN(slicer_index) = 1
           AND MAX(slicer_index) = 8
        """
    )
    op.execute(
        """
        UPDATE printer_tools
        SET slicer_index = slicer_index + 100
        WHERE printer_id IN (SELECT printer_id FROM filaflow_indx_tool_migration)
        """
    )
    op.execute(
        """
        UPDATE printer_tools
        SET slicer_index = slicer_index - 101
        WHERE printer_id IN (SELECT printer_id FROM filaflow_indx_tool_migration)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE TEMPORARY TABLE filaflow_indx_tool_migration ON COMMIT DROP AS
        SELECT printer_id
        FROM printer_tools
        GROUP BY printer_id
        HAVING COUNT(*) = 8
           AND MIN(slicer_index) = 0
           AND MAX(slicer_index) = 7
        """
    )
    op.execute(
        """
        UPDATE printer_tools
        SET slicer_index = slicer_index + 100
        WHERE printer_id IN (SELECT printer_id FROM filaflow_indx_tool_migration)
        """
    )
    op.execute(
        """
        UPDATE printer_tools
        SET slicer_index = slicer_index - 99
        WHERE printer_id IN (SELECT printer_id FROM filaflow_indx_tool_migration)
        """
    )
