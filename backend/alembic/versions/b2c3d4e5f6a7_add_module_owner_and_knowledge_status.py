"""add module owner and knowledge status

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-24 16:00:00.000000

新增：
- project_modules.module_owner_user_id（模块责任人，可为空）
- project_modules.knowledge_status（pending / confirmed / needs_review）
- project_modules.review_due_at（下次复核时间）
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('project_modules', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'module_owner_user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL', name='fk_project_modules_owner_user'),
            nullable=True,
        ))
        batch_op.add_column(sa.Column(
            'knowledge_status',
            sa.String(length=20),
            nullable=False,
            server_default='pending',
        ))
        batch_op.add_column(sa.Column('review_due_at', sa.DateTime(), nullable=True))
        batch_op.create_index(
            'ix_project_modules_module_owner_user_id',
            ['module_owner_user_id'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('project_modules', schema=None) as batch_op:
        batch_op.drop_index('ix_project_modules_module_owner_user_id')
        batch_op.drop_column('review_due_at')
        batch_op.drop_column('knowledge_status')
        batch_op.drop_column('module_owner_user_id')
