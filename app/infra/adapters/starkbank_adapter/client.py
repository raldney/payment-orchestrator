import starkbank

from app.infra.config import settings


def init_starkbank():
    user = starkbank.Project(
        environment=settings.stark_environment,
        id=settings.stark_project_id,
        private_key=settings.stark_private_key,
    )
    starkbank.user = user
