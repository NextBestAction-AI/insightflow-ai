from sqlalchemy.orm import Session
from sqlalchemy import select, func
from models.customer import Customer
from schemas.customer import CustomerCreate, CustomerUpdate
from config.logging import get_logger
from fastapi import HTTPException

logger = get_logger(__name__)


class CustomerService:
    """Service layer for customer operations."""

    @staticmethod
    def create_customer(session: Session, customer_data: CustomerCreate) -> Customer:
        """Create a new customer."""
        try:
            # Check if email already exists
            existing = session.execute(
                select(Customer).where(Customer.email == customer_data.email)
            ).scalar_one_or_none()

            if existing:
                logger.warning(f"Customer with email {customer_data.email} already exists")
                raise HTTPException(status_code=400, detail="Email already registered")

            customer = Customer(
                name=customer_data.name,
                company=customer_data.company,
                industry=customer_data.industry,
                email=customer_data.email,
            )
            session.add(customer)
            session.commit()
            session.refresh(customer)
            logger.info(f"Customer created: {customer.id}")
            return customer
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create customer: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create customer")

    @staticmethod
    def get_customer_by_id(session: Session, customer_id: int) -> Customer:
        """Get a customer by ID."""
        customer = session.execute(
            select(Customer).where(Customer.id == customer_id)
        ).scalar_one_or_none()

        if not customer:
            logger.warning(f"Customer {customer_id} not found")
            raise HTTPException(status_code=404, detail="Customer not found")

        return customer

    @staticmethod
    def get_customer_by_email(session: Session, email: str) -> Customer:
        """Get a customer by email."""
        customer = session.execute(
            select(Customer).where(Customer.email == email)
        ).scalar_one_or_none()

        if not customer:
            logger.warning(f"Customer with email {email} not found")
            raise HTTPException(status_code=404, detail="Customer not found")

        return customer

    @staticmethod
    def get_all_customers(session: Session, skip: int = 0, limit: int = 100) -> tuple[list[Customer], int]:
        """Get all customers with pagination."""
        total = session.execute(select(func.count()).select_from(Customer)).scalar()
        customers = session.execute(
            select(Customer).offset(skip).limit(limit)
        ).scalars().all()

        logger.info(f"Retrieved {len(customers)} customers (total: {total})")
        return customers, total

    @staticmethod
    def get_customers_by_company(session: Session, company: str, skip: int = 0, limit: int = 100) -> tuple[list[Customer], int]:
        """Get customers by company."""
        total = session.execute(
            select(func.count()).select_from(Customer).where(Customer.company == company)
        ).scalar()

        customers = session.execute(
            select(Customer).where(Customer.company == company).offset(skip).limit(limit)
        ).scalars().all()

        logger.info(f"Retrieved {len(customers)} customers from {company}")
        return customers, total

    @staticmethod
    def update_customer(session: Session, customer_id: int, customer_data: CustomerUpdate) -> Customer:
        """Update a customer."""
        try:
            customer = session.execute(
                select(Customer).where(Customer.id == customer_id)
            ).scalar_one_or_none()

            if not customer:
                logger.warning(f"Customer {customer_id} not found for update")
                raise HTTPException(status_code=404, detail="Customer not found")

            # Check if new email already exists
            if customer_data.email and customer_data.email != customer.email:
                existing = session.execute(
                    select(Customer).where(Customer.email == customer_data.email)
                ).scalar_one_or_none()

                if existing:
                    logger.warning(f"Email {customer_data.email} already in use")
                    raise HTTPException(status_code=400, detail="Email already in use")

            # Update only provided fields
            update_data = customer_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(customer, field, value)

            session.commit()
            session.refresh(customer)
            logger.info(f"Customer {customer_id} updated")
            return customer
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update customer {customer_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update customer")

    @staticmethod
    def delete_customer(session: Session, customer_id: int) -> None:
        """Delete a customer."""
        try:
            customer = session.execute(
                select(Customer).where(Customer.id == customer_id)
            ).scalar_one_or_none()

            if not customer:
                logger.warning(f"Customer {customer_id} not found for deletion")
                raise HTTPException(status_code=404, detail="Customer not found")

            session.delete(customer)
            session.commit()
            logger.info(f"Customer {customer_id} deleted")
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to delete customer {customer_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to delete customer")
