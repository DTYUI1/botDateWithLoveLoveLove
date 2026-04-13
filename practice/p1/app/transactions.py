from datetime import datetime

from sqlalchemy.orm import Session

from models import Customer, Order, OrderItem, Product


def place_order(session: Session, customer_id: int, items: list[dict]) -> Order:
    """
    Сценарий 1: Размещение заказа.

    Атомарно создаёт запись Order, добавляет OrderItems
    и обновляет TotalAmount на основе суммы Subtotal.

    items: [{"product_id": int, "quantity": int}, ...]
    """
    try:
        order = Order(CustomerID=customer_id, OrderDate=datetime.utcnow(), TotalAmount=0.0)
        session.add(order)
        session.flush()  # получаем OrderID до commit

        total = 0.0
        for item in items:
            product = session.get(Product, item["product_id"])
            if product is None:
                raise ValueError(f"Product with ID={item['product_id']} not found")

            subtotal = product.Price * item["quantity"]
            total += subtotal

            session.add(
                OrderItem(
                    OrderID=order.OrderID,
                    ProductID=product.ProductID,
                    Quantity=item["quantity"],
                    Subtotal=subtotal,
                )
            )

        order.TotalAmount = total  # обновляем итог заказа
        session.commit()
    except Exception:
        session.rollback()
        raise

    return order


def update_customer_email(session: Session, customer_id: int, new_email: str) -> Customer:
    """
    Сценарий 2: Атомарное обновление email клиента.

    Транзакция гарантирует, что либо email обновлён полностью,
    либо БД остаётся в исходном состоянии.
    """
    try:
        customer = session.get(Customer, customer_id)
        if customer is None:
            raise ValueError(f"Customer with ID={customer_id} not found")

        customer.Email = new_email
        session.commit()
    except Exception:
        session.rollback()
        raise

    return customer


def add_product(session: Session, product_name: str, price: float) -> Product:
    """
    Сценарий 3: Атомарное добавление нового продукта.

    Транзакция гарантирует, что продукт либо добавлен целиком,
    либо БД не изменена (нет частично вставленных записей).
    """
    try:
        product = Product(ProductName=product_name, Price=price)
        session.add(product)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return product
