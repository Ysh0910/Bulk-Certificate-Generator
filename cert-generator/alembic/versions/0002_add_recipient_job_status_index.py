"""add recipient job status index and idempotency enhancements
 
Revision ID: 0002_indexes
Revises: 0001_initial
Create Date: 2026-10-08 07:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_indexes'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add payload_hash to certificate_jobs for idempotency payload verification
    op.add_column('certificate_jobs', sa.Column('payload_hash', sa.String(), nullable=True))
    
    # Enforce unique index on idempotency_key
    op.drop_index('ix_certificate_jobs_idempotency_key', table_name='certificate_jobs')
    op.create_index('ix_certificate_jobs_idempotency_key', 'certificate_jobs', ['idempotency_key'], unique=True)
    
    # Add indexes on certificate_recipients for fast job lookup and status aggregation
    op.create_index('ix_certificate_recipients_job_id', 'certificate_recipients', ['job_id'], unique=False)
    op.create_index('ix_certificate_recipients_job_id_status', 'certificate_recipients', ['job_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_certificate_recipients_job_id_status', table_name='certificate_recipients')
    op.drop_index('ix_certificate_recipients_job_id', table_name='certificate_recipients')
    op.drop_index('ix_certificate_jobs_idempotency_key', table_name='certificate_jobs')
    op.create_index('ix_certificate_jobs_idempotency_key', 'certificate_jobs', ['idempotency_key'], unique=False)
    op.drop_column('certificate_jobs', 'payload_hash')
