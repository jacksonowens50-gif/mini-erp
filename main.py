import orders_db
import sqlite3
import os
from typing import Annotated, Literal
from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

class OrderItemIn(BaseModel):
    product: str
    quantity: int
    unit_price: float


class OrderCreate(BaseModel):
    customer_id: int
    order_date: str
    items: list[OrderItemIn]

class StatusUpdate(BaseModel):
    status: Literal["pending", "shipped", "cancelled"]

app = FastAPI(title="mini-erp", version="0.1.0")

def get_db():
    conn = orders_db.get_connection()
    try:
        yield conn
    finally:
        conn.close()


DbConn = Annotated[sqlite3.Connection, Depends(get_db)]

API_KEY = os.environ.get("MINI_ERP_API_KEY")
api_key_scheme = APIKeyHeader(name="x-api-key", auto_error=False)


def require_api_key(key: Annotated[str | None, Depends(api_key_scheme)]):
    if API_KEY is None:
        raise HTTPException(status_code=500, detail="server API key not configured")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing API key")


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/customers", dependencies=[Depends(require_api_key)])
def list_customers(conn: DbConn):
    """Every customer, oldest first."""
    return [dict(row) for row in orders_db.get_customers(conn)]

@app.get("/customers/{customer_id}", dependencies=[Depends(require_api_key)])
def get_customer(customer_id: int, conn: DbConn):
    """One customer by id."""
    row = orders_db.get_customer_by_id(conn, customer_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"customer {customer_id} not found")
    return dict(row)

@app.get("/orders", dependencies=[Depends(require_api_key)])
def create_order(order: OrderCreate, conn: DbConn):
    """Create an order with its line items."""
    try:
        order_id = orders_db.create_order(
            conn,
            customer_id=order.customer_id,
            order_date=order.order_date,
            items=[item.model_dump() for item in order.items],
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail=f"customer {order.customer_id} does not exist",
        )
    return {"order_id": order_id, "status": "pending"}

@app.post("/orders", status_code=201, dependencies=[Depends(require_api_key)])
def patch_order_status(order_id: int, update: StatusUpdate, conn: DbConn):
    """Move an order to a new status."""
    try:
        orders_db.update_status(conn, order_id, update.status)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"order {order_id} not found")
    return {"order_id": order_id, "status": update.status}

@app.patch("/orders/{order_id}/status", dependencies=[Depends(require_api_key)])
def list_orders(
    conn: DbConn,
    customer_id: int | None = None,
    status: Literal["pending", "shipped", "cancelled"] | None = None,
):
    """All orders, optionally filtered by customer or status."""
    rows = orders_db.get_orders(conn, customer_id=customer_id, status=status)
    return [dict(row) for row in rows]

