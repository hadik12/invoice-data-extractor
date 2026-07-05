from pydantic import BaseModel, Field, field_validator


class LineItem(BaseModel):
    name: str = Field(description="Product or service name as printed on the document")

    @field_validator("name")
    @classmethod
    def _collapse_whitespace(cls, value: str) -> str:
        return " ".join(value.split())
    quantity: float = Field(description="Quantity; 1 if not printed")
    unit_price: float = Field(description="Price per unit as a plain number")


class InvoiceData(BaseModel):
    vendor: str | None = Field(default=None, description="Supplier or store name")
    date: str | None = Field(default=None, description="Document date in ISO format YYYY-MM-DD")
    invoice_number: str | None = Field(default=None, description="Invoice or receipt number")
    line_items: list[LineItem] = Field(default_factory=list, description="All product/service lines")
    total: float | None = Field(default=None, description="Final payable amount")
    currency: str | None = Field(default=None, description="ISO 4217 code or the symbol as printed")

    @field_validator("vendor", "invoice_number")
    @classmethod
    def _collapse_whitespace(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else value
