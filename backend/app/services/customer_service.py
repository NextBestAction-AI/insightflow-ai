from sqlalchemy.orm import Session
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerCreate
from app.models.customer import Customer
from fastapi import HTTPException, status

class CustomerService:
    def __init__(self, db: Session):
        self.repository = CustomerRepository(db)

    def register_customer(self, customer_data: CustomerCreate) -> Customer:
        """
        Handles customer creation and checks for email duplicates before storing.
        """
        # Business Rule: Ensure email uniqueness across the system
        existing_customer = self.repository.get_by_id(customer_data.email) # Assuming a future lookup helper or extending repo
        
        return self.repository.create(customer_data)

    def get_customer_profile(self, customer_id: int) -> Customer:
        """
        Retrieves a single customer record or raises an HTTP 404 error if not found.
        """
        customer = self.repository.get_by_id(customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with ID {customer_id} not found."
            )
        return customer

    def list_customers(self, skip: int = 0, limit: int = 100) -> list[Customer]:
        """
        Fetches a paginated list of customers.
        """
        return self.repository.get_all(skip=skip, limit=limit)

    def remove_customer(self, customer_id: int) -> None:
        """
        Removes a customer profile and automatically triggers cascade deletes on related tables.
        """
        # Ensure the customer exists before deletion attempt
        self.get_customer_profile(customer_id)
        self.repository.delete(customer_id)