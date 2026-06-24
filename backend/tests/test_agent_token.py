from sqlalchemy import select
from app.models.agent_token import AgentToken

def test_persistir_agent_token(db_session):
    db_session.add(AgentToken(token_hash="a" * 64, label="PC-contador"))
    db_session.commit()
    t = db_session.scalar(select(AgentToken))
    assert t.token_hash == "a" * 64
    assert t.label == "PC-contador"
    assert t.created_at is not None
