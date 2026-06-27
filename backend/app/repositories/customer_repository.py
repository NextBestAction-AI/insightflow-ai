from sqlalchemy.orm import Session
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate

class CustomerRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, customer: CustomerCreate) -> Customer:
        db_customer = Customer(**customer.model_dump())
        self.db.add(db_customer)
        self.db.commit()
        self.db.refresh(db_customer)
        return db_customer

    def get_by_id(self, customer_id: int) -> Customer | None:
        return self.db.query(Customer).filter(Customer.id == customer_id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Customer]:
        return self.db.query(Customer).offset(skip).limit(limit).all()

    def delete(self, customer_id: int) -> bool:
        db_customer = self.get_by_id(customer_id)
        if db_customer:
            self.db.delete(db_customer)
            self.db.commit()
            return True
        return False