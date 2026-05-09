"""site_meta.icp_beian — owner-editable ICP filing number for the public footer.

Required by 中国 工信部《非经营性互联网信息服务备案管理办法》— filed sites
must surface the ICP number at the bottom of the homepage with a link to
http://beian.miit.gov.cn/. Storing it in site_meta keeps it editable from
the admin without redeploying when the number changes (filing renewal,
domain transfer, etc.).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "0020_site_icp_beian"
down_revision: str | None = "0019_account_notify_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "site_meta",
        sa.Column(
            "icp_beian", sa.String(length=64), nullable=False, server_default=""
        ),
    )


def downgrade() -> None:
    op.drop_column("site_meta", "icp_beian")
