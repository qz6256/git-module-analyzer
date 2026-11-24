"""add git credentials and identity

Revision ID: a1b2c3d4e5f6
Revises: ce273ccac910
Create Date: 2026-11-24 15:30:00.000000

新增：
- repositories.auth_type / credential_enc（加密的 Git 凭据）
- commit_analyses.author_email（提交作者邮箱）
- git_identities 表（Git 身份，与用户绑定）
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'ce273ccac910'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('repositories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auth_type', sa.String(length=20), nullable=False, server_default='none'))
        batch_op.add_column(sa.Column('credential_enc', sa.Text(), nullable=False, server_default=''))

    with op.batch_alter_table('commit_analyses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('author_email', sa.String(length=200), nullable=False, server_default=''))

    op.create_table(
        'git_identities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='auto'),
        sa.Column('commit_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'email', name='uq_git_identity_name_email'),
    )
    with op.batch_alter_table('git_identities', schema=None) as batch_op:
        batch_op.create_index('ix_git_identities_user_id', ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('git_identities', schema=None) as batch_op:
        batch_op.drop_index('ix_git_identities_user_id')
    op.drop_table('git_identities')
    with op.batch_alter_table('commit_analyses', schema=None) as batch_op:
        batch_op.drop_column('author_email')
    with op.batch_alter_table('repositories', schema=None) as batch_op:
        batch_op.drop_column('credential_enc')
        batch_op.drop_column('auth_type')
