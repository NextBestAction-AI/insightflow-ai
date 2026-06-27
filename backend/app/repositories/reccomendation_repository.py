from sqlalchemy.orm import Session
from app.models.recommendation import Recommendation
from app.schemas.recommendation import RecommendationCreate

class RecommendationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, recommendation: RecommendationCreate) -> Recommendation:
        data = recommendation.model_dump()
        data["reason"] = data.pop("reason", None)
        db_rec = Recommendation(**data)
        self.db.add(db_rec)
        self.db.commit()
        self.db.refresh(db_rec)
        return db_rec

    def get_by_id(self, recommendation_id: int) -> Recommendation | None:
        return self.db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()

    def update_status(self, recommendation_id: int, status: str) -> Recommendation | None:
        db_rec = self.get_by_id(recommendation_id)
        if db_rec:
            db_rec.status = status
            self.db.commit()
            self.db.refresh(db_rec)
        return db_rec

    def get_pending(self) -> list[Recommendation]:
        return self.db.query(Recommendation).filter(Recommendation.status == "Pending").all()