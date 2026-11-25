"""one forecast per candle and model; store threshold and outcome

Revision ID: 0003
Revises: 0002

"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("predictions", sa.Column("threshold", sa.Float(), nullable=True))
    op.add_column("predictions", sa.Column("outcome_label", sa.String(10), nullable=True))
    op.add_column("predictions", sa.Column("outcome_return", sa.Float(), nullable=True))
    # Old rows: recover the threshold of the model version that made them.
    op.execute(
        """
        UPDATE predictions SET threshold = (
            SELECT MAX(m.threshold) FROM model_versions m
            WHERE m.model_version = predictions.model_version
              AND m.timeframe = predictions.timeframe
              AND m.symbol IN (predictions.symbol, 'ALL/USDT'))
        """
    )
    # Keep the newest forecast of each candle and model.
    op.execute(
        """
        DELETE FROM predictions WHERE id NOT IN (
            SELECT keep FROM (
                SELECT MAX(id) AS keep FROM predictions
                GROUP BY symbol, timeframe, latest_candle_utc, model_version) AS newest)
        """
    )
    op.create_index(
        "uq_predictions_candle_model",
        "predictions",
        ["symbol", "timeframe", "latest_candle_utc", "model_version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_predictions_candle_model", table_name="predictions")
    for column in ("outcome_return", "outcome_label", "threshold"):
        op.drop_column("predictions", column)
