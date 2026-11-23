from typing import Literal
from pydantic import BaseModel, Field

Category = Literal["billing", "teknis", "akun", "pengiriman", "saran", "lainnya"]
Priority = Literal["rendah", "sedang", "tinggi", "kritis"]
Sentiment = Literal["positif", "netral", "negatif"]


class TicketIn(BaseModel):
    text: str = Field(min_length=5, max_length=4000, description="Isi tiket dari pelanggan")


class Classification(BaseModel):
    category: Category
    priority: Priority
    sentiment: Sentiment
    summary: str = Field(description="Ringkasan 1 kalimat")
    suggested_reply: str = Field(description="Draf balasan sopan untuk pelanggan")


class TicketOut(Classification):
    id: int
    text: str
    created_at: str
