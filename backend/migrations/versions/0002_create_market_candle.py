"""create market_candles

Revision ID: 0002
Revises: 0001

Create Date: 2026-10-19

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('market_candles',
    sa.Column('symbol', sa.String(length=20), nullable=False),
    sa.Column('timeframe', sa.String(length=10), nullable=False),
    sa.Column('candle_time_utc', sa.DateTime(timezone=True), nullable=False),
    sa.Column('open', sa.Float(), nullable=False),
    sa.Column('high', sa.Float(), nullable=False),
    sa.Column('low', sa.Float(), nullable=False),
    sa.Column('close', sa.Float(), nullable=False),
    sa.Column('volume', sa.Float(), nullable=False),
    sa.Column('saved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('symbol', 'timeframe', 'candle_time_utc')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('market_candles')