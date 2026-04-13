import os
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from models import Base, Customer, Product
from transactions import add_product, place_order, update_customer_email

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/store")


def wait_for_db(engine, retries: int = 15, delay: int = 3) -> None:
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("Database is ready.")
            return
        except Exception:
            print(f"Database not ready, retrying ({attempt}/{retries})...")
            time.sleep(delay)
    raise RuntimeError("Could not connect to the database after multiple attempts.")


def seed_data(session) -> tuple[Customer, list[Product]]:
    customer = Customer(FirstName="Ivan", LastName="Petrov", Email="ivan@example.com")
    session.add(customer)

    products = [
        Product(ProductName="Laptop", Price=999.99),
        Product(ProductName="Mouse", Price=29.99),
        Product(ProductName="Keyboard", Price=59.99),
    ]
    session.add_all(products)
    session.commit()
    return customer, products


def main() -> None:
    engine = create_engine(DATABASE_URL)
    wait_for_db(engine)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        print("\n=== Seeding initial data ===")
        customer, products = seed_data(session)
        print(f"Customer : {customer.FirstName} {customer.LastName}  (ID={customer.CustomerID})")
        for p in products:
            print(f"Product  : {p.ProductName:<12} ${p.Price:<8}  (ID={p.ProductID})")

        # ── Сценарий 1 ──────────────────────────────────────────────────────────
        print("\n=== Scenario 1: Place Order ===")
        order = place_order(
            session,
            customer_id=customer.CustomerID,
            items=[
                {"product_id": products[0].ProductID, "quantity": 1},
                {"product_id": products[1].ProductID, "quantity": 2},
            ],
        )
        # 1×Laptop(999.99) + 2×Mouse(29.99) = 1059.97
        print(f"Order placed : ID={order.OrderID}, TotalAmount=${order.TotalAmount:.2f}")

        # ── Сценарий 2 ──────────────────────────────────────────────────────────
        print("\n=== Scenario 2: Update Customer Email ===")
        updated_customer = update_customer_email(
            session,
            customer_id=customer.CustomerID,
            new_email="ivan.new@example.com",
        )
        print(f"Email updated: {updated_customer.Email}")

        # ── Сценарий 3 ──────────────────────────────────────────────────────────
        print("\n=== Scenario 3: Add New Product ===")
        new_product = add_product(session, product_name="Monitor", price=349.99)
        print(f"Product added: {new_product.ProductName} — ${new_product.Price}  (ID={new_product.ProductID})")

        print("\nAll scenarios completed successfully!")


if __name__ == "__main__":
    main()
