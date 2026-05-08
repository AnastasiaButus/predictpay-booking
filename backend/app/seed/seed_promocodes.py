from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.promocode import Promocode


POINCARE_CHALLENGE_WORDING_RU = (
    "Всякое замкнутое односвязное трёхмерное многообразие "
    "гомеоморфно трёхмерной сфере."
)
POINCARE_CHALLENGE_WORDING_EN = (
    "Every simply connected, closed 3-manifold is homeomorphic to the 3-sphere."
)
POINCARE_CHALLENGE_MVP_NOTE = (
    "MVP checks only URL format and does not verify mathematical correctness."
)

PROMOCODE_DEFINITIONS = [
    {
        "code": "WELCOME100",
        "credits_amount": 100,
        "max_activations": 100000,
        "is_active": True,
        "description": "Welcome bonus: +100 credits for new users.",
    },
    {
        "code": "ANISIMOV100",
        "credits_amount": 100,
        "max_activations": 100000,
        "is_active": True,
        "description": (
            "Course easter egg in honor of the instructor: "
            "Анисимов Ян Олегович."
        ),
    },
    {
        "code": "SPRINGFIELD100",
        "credits_amount": 100,
        "max_activations": 100000,
        "is_active": True,
        "description": "Light cartoon-style easter egg for the course demo.",
    },
    {
        "code": "POINCARE_CHALLENGE",
        "credits_amount": 1000,
        "max_activations": 100000,
        "is_active": True,
        "description": (
            "Special challenge bonus for submitting a URL related to the "
            "Poincaré conjecture proof."
        ),
    },
]


def seed_promocodes(db: Session) -> list[Promocode]:
    seeded_promocodes = []

    for definition in PROMOCODE_DEFINITIONS:
        promocode = db.scalar(
            select(Promocode).where(Promocode.code == definition["code"])
        )

        if promocode is None:
            promocode = Promocode(**definition)
            db.add(promocode)
        else:
            promocode.credits_amount = definition["credits_amount"]
            promocode.max_activations = definition["max_activations"]
            promocode.is_active = definition["is_active"]
            promocode.description = definition["description"]

        seeded_promocodes.append(promocode)

    db.flush()
    return seeded_promocodes
