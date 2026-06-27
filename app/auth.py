from app.actors import ACTORS, Actor


def get_actor_from_cookie(actor_id: str | None) -> Actor | None:
    if not actor_id:
        return None
    return ACTORS.get(actor_id)
