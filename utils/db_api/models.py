from datetime import datetime

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from data.constants import PROJECT_SHORT_NAME


class Base(DeclarativeBase):
    pass


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_data: Mapped[str] = mapped_column(unique=True, default=None, nullable=True)
    private_key: Mapped[str] = mapped_column(unique=True, default=None, nullable=True)
    evm_private_key: Mapped[str] = mapped_column(unique=True, default=None, nullable=True)
    proxy_status: Mapped[str] = mapped_column(default="OK", nullable=True)
    proxy: Mapped[str] = mapped_column(default=None, nullable=True)
    twitter_token: Mapped[str] = mapped_column(default=None, nullable=True)
    twitter_status: Mapped[str] = mapped_column(default="OK", nullable=True)
    discord_token: Mapped[str] = mapped_column(default=None, nullable=True)
    discord_proxy: Mapped[str] = mapped_column(default=None, nullable=True)
    discord_status: Mapped[str] = mapped_column(default="OK", nullable=True)
    discord_connected: Mapped[bool] = mapped_column(default=False)
    points: Mapped[int] = mapped_column(default=0)
    top: Mapped[int] = mapped_column(default=0)
    invite_code: Mapped[str] = mapped_column(default="")
    completed: Mapped[bool] = mapped_column(default=False)
    bearer_token: Mapped[str] = mapped_column(default=None, nullable=True)
    refresh_token: Mapped[str] = mapped_column(default=None, nullable=True)
    hs_form_status: Mapped[str] = mapped_column(default=None, nullable=True)
    next_faucet_time: Mapped[datetime] = mapped_column(default=datetime.now)

    def __repr__(self):
        return f"[{PROJECT_SHORT_NAME} | {self.id}]"
