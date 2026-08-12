from pydantic import BaseModel, Field
from typing import Optional


class TransactionRequest(BaseModel):
    sender_private_key: Optional[str] = None
    recipient: str = Field(min_length=1, max_length=128)
    amount: float = Field(gt=0)
    fee: float = Field(default=0.0, ge=0)
    lock_until_block: int = Field(default=0, ge=0)


class TransactionResponse(BaseModel):
    tx_hash: str
    sender: str
    recipient: str
    amount: float
    fee: float
    timestamp: float


class BlockResponse(BaseModel):
    block_index: int
    block_hash: str
    previous_hash: str
    timestamp: float
    nonce: int
    difficulty: int
    miner_address: str
    tx_count: int


class BlockDetailResponse(BaseModel):
    block_index: int
    block_hash: str
    previous_hash: str
    timestamp: float
    nonce: int
    difficulty: int
    miner_address: str
    miner_public_key: str
    miner_signature: str
    merkle_root: str
    transactions: list[dict]


class StatsResponse(BaseModel):
    height: int
    difficulty: int
    mempool_size: int
    peer_count: int
    last_block_hash: Optional[str] = None
    last_block_time: Optional[float] = None
    total_transactions: int


class PeerRegisterRequest(BaseModel):
    address: str = Field(min_length=1)


class MessageResponse(BaseModel):
    message: str


class BalanceResponse(BaseModel):
    address: str
    balance: float


class WalletResponse(BaseModel):
    address: str
    public_key: str
    balance: float
