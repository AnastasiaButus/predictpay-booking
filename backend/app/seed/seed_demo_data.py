from app.db.session import SessionLocal
from app.seed.seed_model_metadata import seed_model_metadata
from app.seed.seed_promocodes import seed_promocodes


def seed_demo_data() -> None:
    db = SessionLocal()
    try:
        seed_model_metadata(db)
        seed_promocodes(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("seeded/updated model metadata")
    print("seeded/updated promocodes")


if __name__ == "__main__":
    seed_demo_data()
