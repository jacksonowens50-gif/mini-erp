import sqlite3
import shutil


def get_connection(db_path="orders.db"):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def create_tables(conn):
    conn.executescript(SCHEMA)

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id   INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    city          TEXT,
    signup_date   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id      INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL,
    order_date    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS order_items (
    item_id       INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL,
    product       TEXT NOT NULL,
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    unit_price    REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);
"""
def seed_data(conn):
    if conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] > 0:
        return

    customers = [
        (1, "Ridgeline Supply",   "Denver",   "2025-01-14"),
        (2, "Kepler Foods",       "Chicago",  "2025-02-03"),
        (3, "Basin Manufacturing","Houston",  "2025-02-27"),
        (4, "Nordic Outfitters",  "Seattle",  "2025-04-11"),
        (5, "Palmetto Freight",   "Atlanta",  "2025-06-02"),
    ]
    orders = [
        (101, 1, "2026-03-02", "shipped"),
        (102, 1, "2026-03-19", "shipped"),
        (103, 2, "2026-03-21", "pending"),
        (104, 3, "2026-04-05", "shipped"),
        (105, 3, "2026-04-18", "cancelled"),
        (106, 4, "2026-05-07", "shipped"),
        (107, 5, "2026-05-22", "pending"),
        (108, 1, "2026-06-01", "pending"),
    ]
    items = [
        (1,  101, "Steel bracket",   40,  12.50),
        (2,  101, "Hex bolt (box)",   6,  33.00),
        (3,  102, "Steel bracket",   15,  12.50),
        (4,  103, "Conveyor belt",    2, 480.00),
        (5,  103, "Roller bearing",  12,  27.75),
        (6,  104, "Hex bolt (box)",  20,  33.00),
        (7,  104, "Steel bracket",   60,  12.50),
        (8,  105, "Conveyor belt",    1, 480.00),
        (9,  106, "Roller bearing",   8,  27.75),
        (10, 106, "Drive motor",      1, 950.00),
        (11, 107, "Steel bracket",   25,  12.50),
        (12, 107, "Drive motor",      2, 950.00),
        (13, 108, "Hex bolt (box)",   4,  33.00),
        (14, 108, "Roller bearing",  30,  27.75),
        (15, 108, "Conveyor belt",    3, 480.00),
    ]

    conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", customers)
    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", orders)
    conn.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", items)
    conn.commit()

def get_customers(conn):
    return conn.execute(
        "SELECT customer_id, name, city, signup_date FROM customers ORDER BY customer_id"
    ).fetchall()

def get_customer_by_id(conn, customer_id):
    return conn.execute(
        "SELECT customer_id, name, city, signup_date FROM customers WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()

def create_order(conn, customer_id, order_date, items):
    with conn:
        cur = conn.execute(
            "INSERT INTO orders (customer_id, order_date, status) VALUES (?, ?, ?)",
            (customer_id, order_date, "pending"),
        )
        order_id = cur.lastrowid

        conn.executemany(
            "INSERT INTO order_items (order_id, product, quantity, unit_price)"
            " VALUES (?, ?, ?, ?)",
            [(order_id, i["product"], i["quantity"], i["unit_price"]) for i in items],
        )
    return order_id

def get_orders(conn, customer_id=None, status=None):
    sql = """
        SELECT order_id, customer_id, order_date, status
        FROM orders
    """
    conditions = []
    params = []

    if customer_id is not None:
        conditions.append("customer_id = ?")
        params.append(customer_id)

    if status is not None:
        conditions.append("status = ?")
        params.append(status)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY order_id"
    return conn.execute(sql, params).fetchall()

def revenue_by_customer(conn):
    sql = """
        SELECT c.name,
               COUNT(DISTINCT o.order_id)              AS order_count,
               ROUND(SUM(i.quantity * i.unit_price), 2) AS revenue
        FROM customers c
        JOIN orders o      ON o.customer_id = c.customer_id
        JOIN order_items i ON i.order_id = o.order_id
        WHERE o.status != 'cancelled'
        GROUP BY c.customer_id, c.name
        ORDER BY revenue DESC
    """
    return conn.execute(sql).fetchall()

def transaction_demo(db_path="orders.db"):
    a = get_connection(db_path)
    b = get_connection(db_path)
    a.execute("DELETE FROM customers WHERE customer_id IN (6, 7)")
    a.commit()

    a.execute(
        "INSERT INTO customers VALUES (?, ?, ?, ?)",
        (6, "Cascade Tooling", "Portland", "2026-08-04"),
    )

    print("A sees:", a.execute("SELECT COUNT(*) FROM customers").fetchone()[0])
    print("B sees:", b.execute("SELECT COUNT(*) FROM customers").fetchone()[0])

    a.commit()
    print("B after commit:", b.execute("SELECT COUNT(*) FROM customers").fetchone()[0])

    a.close()
    b.close()

def rollback_demo(db_path="orders.db"):
    conn = get_connection(db_path)
    before = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

    try:
        with conn:
            conn.execute(
                "INSERT INTO customers VALUES (?, ?, ?, ?)",
                (7, "Harbor Plastics", "Tampa", "2026-08-04"),
            )
            raise ValueError("something blew up mid-transaction")
    except ValueError as e:
        print("caught:", e)

    after = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    print(f"before: {before}   after: {after}")
    conn.close()

def update_status(conn, order_id, new_status):
    cur = conn.execute(
        "UPDATE orders SET status = ? WHERE order_id = ?",
        (new_status, order_id),
    )
    if cur.rowcount != 1:
        conn.rollback()
        raise ValueError(f"expected to change 1 row, changed {cur.rowcount}")
    conn.commit()


if __name__ == "__main__":
    conn = get_connection()
    create_tables(conn)
    seed_data(conn)

    for row in revenue_by_customer(conn):
        print(f"{row['name']:<24} {row['order_count']:>3} orders   ${row['revenue']:>9,.2f}")

    conn.close()

