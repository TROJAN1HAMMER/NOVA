"""
NOVA — Knowledge Graph API & Snapshot Endpoint Tests
Validates symbolic entity-relation knowledge graph serialization,
document filtering, empty graph handling, and RBAC permission enforcement (KNOWLEDGE_READ).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.endpoints.knowledge import get_knowledge_graph as api_get_knowledge_graph
from app.auth.permissions import Permission, require_permission
from app.models.enums import AuthProvider, UserRole
from app.models.knowledge import KnowledgeEntity, KnowledgeRelation
from app.models.user import User
from app.schemas.knowledge import GraphSnapshotResponse


@pytest.fixture
def test_user():
    return User(
        id=uuid.uuid4(),
        email="analyst@nova.example",
        role=UserRole.SECURITY_ENGINEER,
        is_active=True,
        auth_provider=AuthProvider.LOCAL,
    )


class TestKnowledgeGraphEndpoint:
    @pytest.mark.asyncio
    async def test_get_knowledge_graph_empty(self, test_user):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        res = await api_get_knowledge_graph(
            _current_user=test_user,
            db=mock_db,
            document_id=None,
        )

        assert isinstance(res, GraphSnapshotResponse)
        assert res.total_nodes == 0
        assert res.total_relations == 0
        assert res.nodes == []
        assert res.relations == []
        assert res.generated_at is not None

    @pytest.mark.asyncio
    async def test_get_knowledge_graph_populated(self, test_user):
        doc_id = uuid.uuid4()
        e1_id = uuid.uuid4()
        e2_id = uuid.uuid4()
        rel_id = uuid.uuid4()

        e1 = KnowledgeEntity(
            id=e1_id,
            document_id=doc_id,
            entity_name="AEKOF Architecture",
            entity_type="CONCEPT",
            mention_count=4,
        )
        e2 = KnowledgeEntity(
            id=e2_id,
            document_id=doc_id,
            entity_name="PostgreSQL pgvector",
            entity_type="PRODUCT",
            mention_count=7,
        )
        r1 = KnowledgeRelation(
            id=rel_id,
            source_entity_id=e1_id,
            target_entity_id=e2_id,
            relation_type="FUSES_WITH",
        )

        mock_db = AsyncMock()

        async def mock_execute(statement):
            mock_res = MagicMock()
            statement_str = str(statement).lower()
            if "knowledge_entities" in statement_str:
                mock_res.scalars.return_value.all.return_value = [e1, e2]
            else:
                mock_res.scalars.return_value.all.return_value = [r1]
            return mock_res

        mock_db.execute.side_effect = mock_execute

        res = await api_get_knowledge_graph(
            _current_user=test_user,
            db=mock_db,
            document_id=None,
        )

        assert isinstance(res, GraphSnapshotResponse)
        assert res.total_nodes == 2
        assert res.total_relations == 1

        node_labels = {n.label for n in res.nodes}
        assert "AEKOF Architecture" in node_labels
        assert "PostgreSQL pgvector" in node_labels

        rel = res.relations[0]
        assert rel.id == str(rel_id)
        assert rel.source_id == str(e1_id)
        assert rel.target_id == str(e2_id)
        assert rel.relation_type == "FUSES_WITH"

    @pytest.mark.asyncio
    async def test_get_knowledge_graph_document_filter(self, test_user):
        target_doc_id = uuid.uuid4()
        other_doc_id = uuid.uuid4()
        e1_id = uuid.uuid4()

        e1 = KnowledgeEntity(
            id=e1_id,
            document_id=target_doc_id,
            entity_name="Specific Policy",
            entity_type="POLICY",
            mention_count=2,
        )

        mock_db = AsyncMock()

        async def mock_execute(statement):
            mock_res = MagicMock()
            statement_str = str(statement).lower()
            if "knowledge_entities" in statement_str:
                mock_res.scalars.return_value.all.return_value = [e1]
            else:
                mock_res.scalars.return_value.all.return_value = []
            return mock_res

        mock_db.execute.side_effect = mock_execute

        res = await api_get_knowledge_graph(
            _current_user=test_user,
            db=mock_db,
            document_id=target_doc_id,
        )

        assert res.total_nodes == 1
        assert res.nodes[0].label == "Specific Policy"
        assert res.nodes[0].document_id == str(target_doc_id)

    @pytest.mark.asyncio
    async def test_knowledge_graph_permissions_gating(self):
        dep = require_permission(Permission.KNOWLEDGE_READ)

        # All 5 platform roles have KNOWLEDGE_READ
        all_roles = [
            UserRole.ADMIN,
            UserRole.SECURITY_ENGINEER,
            UserRole.DEVELOPER,
            UserRole.AUDITOR,
            UserRole.READ_ONLY,
        ]

        for role in all_roles:
            user = User(
                id=uuid.uuid4(),
                email=f"{role.value}@nova.example",
                role=role,
                is_active=True,
                auth_provider=AuthProvider.LOCAL,
            )
            assert await dep(current_user=user) == user
