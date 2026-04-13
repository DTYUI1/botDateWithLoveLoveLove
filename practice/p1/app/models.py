from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    CustomerID = Column(Integer, primary_key=True, autoincrement=True)
    FirstName = Column(String(50), nullable=False)
    LastName = Column(String(50), nullable=False)
    Email = Column(String(100), nullable=False, unique=True)

    orders = relationship("Order", back_populates="customer")


class Product(Base):
    __tablename__ = "products"

    ProductID = Column(Integer, primary_key=True, autoincrement=True)
    ProductName = Column(String(100), nullable=False)
    Price = Column(Float, nullable=False)

    order_items = relationship("OrderItem", back_populates="product")


class Order(Base):
    __tablename__ = "orders"

    OrderID = Column(Integer, primary_key=True, autoincrement=True)
    CustomerID = Column(Integer, ForeignKey("customers.CustomerID"), nullable=False)
    OrderDate = Column(DateTime, default=datetime.utcnow)
    TotalAmount = Column(Float, default=0.0)

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "orderitems"

    OrderItemID = Column(Integer, primary_key=True, autoincrement=True)
    OrderID = Column(Integer, ForeignKey("orders.OrderID"), nullable=False)
    ProductID = Column(Integer, ForeignKey("products.ProductID"), nullable=False)
    Quantity = Column(Integer, nullable=False)
    Subtotal = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
