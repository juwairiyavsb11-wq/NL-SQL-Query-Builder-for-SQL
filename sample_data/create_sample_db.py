"""
AskDB — Sample Database Generator
Creates a realistic e-commerce SQLite database for demo purposes.
"""

import sqlite3
import random
import os
from datetime import datetime, timedelta

# Output path
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "ecommerce_sample.db")

# ── Data pools ──

FIRST_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Edward", "Fiona", "George", "Hannah",
    "Ivan", "Julia", "Kevin", "Laura", "Michael", "Nina", "Oliver", "Patricia",
    "Quincy", "Rachel", "Samuel", "Tina", "Ulysses", "Vera", "William", "Xena",
    "Yusuf", "Zara", "Aaron", "Beatrice", "Carlos", "Donna", "Erik", "Francesca",
    "Gabriel", "Helen", "Igor", "Janet", "Kyle", "Lily", "Marcus", "Natalie",
    "Oscar", "Priya", "Rafael", "Sophia", "Thomas", "Uma", "Victor", "Wendy",
    "Xavier", "Yvonne"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen",
    "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera",
    "Campbell", "Mitchell", "Carter", "Roberts"
]

CITIES = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
    "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville",
    "Fort Worth", "Columbus", "Charlotte", "San Francisco", "Indianapolis",
    "Seattle", "Denver", "Washington", "Nashville", "Oklahoma City", "El Paso",
    "Boston", "Portland", "Las Vegas", "Memphis", "Louisville", "Baltimore",
    "Milwaukee", "Albuquerque", "Tucson", "Fresno", "Sacramento", "Mesa",
    "Kansas City", "Atlanta", "Omaha", "Colorado Springs", "Raleigh"
]

PRODUCT_CATEGORIES = ["Electronics", "Clothing", "Books", "Home & Garden", "Sports", "Toys", "Beauty", "Food"]

PRODUCTS = {
    "Electronics": [
        ("Wireless Headphones", 79.99), ("Bluetooth Speaker", 49.99), ("USB-C Hub", 34.99),
        ("Webcam HD", 59.99), ("Mechanical Keyboard", 129.99), ("Mouse Pad XL", 19.99),
        ("Phone Charger", 24.99), ("Smart Watch", 199.99), ("Tablet Stand", 29.99),
        ("Power Bank", 39.99)
    ],
    "Clothing": [
        ("Cotton T-Shirt", 24.99), ("Denim Jeans", 59.99), ("Running Shoes", 89.99),
        ("Winter Jacket", 149.99), ("Silk Scarf", 34.99), ("Wool Sweater", 69.99),
        ("Baseball Cap", 19.99), ("Leather Belt", 44.99)
    ],
    "Books": [
        ("Python Programming", 39.99), ("Data Science Handbook", 49.99), ("AI Fundamentals", 44.99),
        ("Web Development Guide", 34.99), ("SQL Mastery", 29.99), ("Cloud Architecture", 54.99)
    ],
    "Home & Garden": [
        ("Desk Lamp", 39.99), ("Plant Pot Set", 24.99), ("Wall Clock", 29.99),
        ("Throw Pillow", 19.99), ("Kitchen Scale", 34.99), ("Air Purifier", 129.99)
    ],
    "Sports": [
        ("Yoga Mat", 29.99), ("Dumbbells Set", 79.99), ("Jump Rope", 14.99),
        ("Water Bottle", 19.99), ("Resistance Bands", 24.99), ("Fitness Tracker", 49.99)
    ],
    "Toys": [
        ("Building Blocks", 29.99), ("Board Game", 34.99), ("Puzzle 1000pc", 19.99),
        ("RC Car", 49.99), ("Art Supply Kit", 24.99)
    ],
    "Beauty": [
        ("Face Cream", 29.99), ("Sunscreen SPF50", 14.99), ("Hair Dryer", 59.99),
        ("Makeup Brush Set", 34.99), ("Essential Oils", 24.99)
    ],
    "Food": [
        ("Organic Coffee", 14.99), ("Protein Bars Box", 24.99), ("Herbal Tea Set", 19.99),
        ("Dark Chocolate", 9.99), ("Mixed Nuts Pack", 12.99)
    ]
}

ORDER_STATUSES = ["completed", "pending", "shipped", "cancelled", "refunded"]


def create_database():
    """Create the sample e-commerce database."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── Create tables ──
    cursor.executescript("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            city TEXT NOT NULL,
            join_date DATE NOT NULL,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER DEFAULT 0,
            rating REAL DEFAULT 0.0,
            created_date DATE NOT NULL
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            order_date DATE NOT NULL,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
    """)

    # ── Insert customers ──
    customers = []
    used_emails = set()
    base_date = datetime(2023, 1, 1)
    for i in range(120):
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        email = f"{fname.lower()}.{lname.lower()}{random.randint(1, 999)}@example.com"
        while email in used_emails:
            email = f"{fname.lower()}.{lname.lower()}{random.randint(1, 9999)}@example.com"
        used_emails.add(email)
        city = random.choice(CITIES)
        join_date = base_date + timedelta(days=random.randint(0, 900))
        is_active = 1 if random.random() > 0.15 else 0
        customers.append((fname, lname, email, city, join_date.strftime("%Y-%m-%d"), is_active))

    cursor.executemany(
        "INSERT INTO customers (first_name, last_name, email, city, join_date, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        customers
    )

    # ── Insert products ──
    products = []
    for category, items in PRODUCTS.items():
        for name, price in items:
            stock = random.randint(0, 500)
            rating = round(random.uniform(2.5, 5.0), 1)
            created = base_date + timedelta(days=random.randint(0, 365))
            products.append((name, category, price, stock, rating, created.strftime("%Y-%m-%d")))

    cursor.executemany(
        "INSERT INTO products (name, category, price, stock, rating, created_date) VALUES (?, ?, ?, ?, ?, ?)",
        products
    )

    product_count = len(products)
    customer_count = len(customers)

    # ── Insert orders & order items ──
    order_id = 0
    for _ in range(600):
        customer_id = random.randint(1, customer_count)
        order_date = base_date + timedelta(days=random.randint(30, 1000))
        status = random.choices(ORDER_STATUSES, weights=[50, 15, 20, 10, 5])[0]

        # Generate order items
        num_items = random.choices([1, 2, 3, 4, 5], weights=[40, 30, 15, 10, 5])[0]
        total = 0
        items = []
        for _ in range(num_items):
            prod_id = random.randint(1, product_count)
            qty = random.randint(1, 5)
            price = products[prod_id - 1][2]  # Get product price
            total += price * qty
            items.append((prod_id, qty, price))

        total = round(total, 2)
        cursor.execute(
            "INSERT INTO orders (customer_id, order_date, total_amount, status) VALUES (?, ?, ?, ?)",
            (customer_id, order_date.strftime("%Y-%m-%d"), total, status)
        )
        order_id = cursor.lastrowid

        for prod_id, qty, price in items:
            cursor.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (order_id, prod_id, qty, price)
            )

    conn.commit()
    conn.close()
    print(f"[OK] Sample database created at: {DB_PATH}")
    print(f"     Customers: {customer_count}")
    print(f"     Products:  {product_count}")
    print(f"     Orders:    600")


if __name__ == "__main__":
    create_database()
