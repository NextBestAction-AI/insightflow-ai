from sqlalchemy.orm import Session
from app.models.interaction import Interaction
from app.schemas.interaction import InteractionCreate

class InteractionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, interaction: InteractionCreate) -> Interaction:
        db_interaction = Interaction(**interaction.model_dump())
        self.db.add(db_interaction)
        self.db.commit()
        self.db.refresh(db_interaction)
        return db_interaction

    def get_by_id(self, interaction_id: int) -> Interaction | None:
        return self.db.query(Interaction).filter(Interaction.id == interaction_id).first()

    def get_by_customer(self, customer_id: int) -> list[Interaction]:
        return self.db.query(Interaction).filter(Interaction.customer_id == customer_id).all()