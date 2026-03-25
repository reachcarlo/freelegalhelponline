"""Tests for CaseStorage artifact CRUD operations (V2.4.6)."""

from pathlib import Path

import pytest

from employee_help.storage.case_storage import CaseStorage
from employee_help.storage.models import (
    ArtifactType,
    Case,
    CaseArtifact,
)
from employee_help.storage.storage import Storage


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def case_storage(storage: Storage) -> CaseStorage:
    return CaseStorage(conn=storage._conn)


@pytest.fixture
def saved_case(case_storage: CaseStorage) -> Case:
    case = Case(name="Artifact Test Case", user_id="u1", organization_id="o1")
    return case_storage.create_case(case)


class TestArtifactCRUD:
    def test_create_artifact(self, case_storage: CaseStorage, saved_case: Case):
        artifact = CaseArtifact(
            case_id=saved_case.id,
            artifact_type=ArtifactType.DISCOVERY,
            tool_source="srogs",
            summary="SROGs Set 1 generated",
            metadata={"filename": "SROGs_24STCV99999.docx", "file_size": 12345},
        )
        result = case_storage.create_artifact(artifact)
        assert result.id == artifact.id
        assert result.case_id == saved_case.id
        assert result.artifact_type == ArtifactType.DISCOVERY
        assert result.tool_source == "srogs"
        assert result.summary == "SROGs Set 1 generated"
        assert result.metadata["filename"] == "SROGs_24STCV99999.docx"
        assert result.created_by is None

    def test_list_artifacts_empty(self, case_storage: CaseStorage, saved_case: Case):
        artifacts = case_storage.list_artifacts(saved_case.id)
        assert artifacts == []

    def test_list_artifacts_returns_newest_first(
        self, case_storage: CaseStorage, saved_case: Case
    ):
        a1 = CaseArtifact(
            case_id=saved_case.id,
            artifact_type=ArtifactType.DISCOVERY,
            tool_source="srogs",
            summary="SROGs Set 1",
        )
        a2 = CaseArtifact(
            case_id=saved_case.id,
            artifact_type=ArtifactType.DISCOVERY,
            tool_source="rfpds",
            summary="RFPDs Set 1",
        )
        case_storage.create_artifact(a1)
        case_storage.create_artifact(a2)

        artifacts = case_storage.list_artifacts(saved_case.id)
        assert len(artifacts) == 2
        # Newest first (a2 created after a1)
        assert artifacts[0].tool_source == "rfpds"
        assert artifacts[1].tool_source == "srogs"

    def test_get_artifact(self, case_storage: CaseStorage, saved_case: Case):
        artifact = CaseArtifact(
            case_id=saved_case.id,
            artifact_type=ArtifactType.PROOF_OF_SERVICE,
            tool_source="pos",
            summary="POS generated",
        )
        case_storage.create_artifact(artifact)

        result = case_storage.get_artifact(artifact.id)
        assert result is not None
        assert result.id == artifact.id
        assert result.artifact_type == ArtifactType.PROOF_OF_SERVICE

    def test_get_artifact_not_found(self, case_storage: CaseStorage):
        assert case_storage.get_artifact("nonexistent") is None

    def test_delete_artifact(self, case_storage: CaseStorage, saved_case: Case):
        artifact = CaseArtifact(
            case_id=saved_case.id,
            artifact_type=ArtifactType.DISCOVERY,
            tool_source="rfas",
        )
        case_storage.create_artifact(artifact)
        assert case_storage.delete_artifact(artifact.id) is True
        assert case_storage.get_artifact(artifact.id) is None

    def test_delete_artifact_not_found(self, case_storage: CaseStorage):
        assert case_storage.delete_artifact("nonexistent") is False

    def test_cascade_delete_on_case_delete(
        self, case_storage: CaseStorage, saved_case: Case
    ):
        artifact = CaseArtifact(
            case_id=saved_case.id,
            artifact_type=ArtifactType.DISCOVERY,
            tool_source="srogs",
        )
        case_storage.create_artifact(artifact)
        case_storage.delete_case(saved_case.id)
        assert case_storage.get_artifact(artifact.id) is None

    def test_metadata_none(self, case_storage: CaseStorage, saved_case: Case):
        artifact = CaseArtifact(
            case_id=saved_case.id,
            artifact_type=ArtifactType.DISCOVERY,
            tool_source="srogs",
            metadata=None,
        )
        result = case_storage.create_artifact(artifact)
        fetched = case_storage.get_artifact(result.id)
        assert fetched is not None
        assert fetched.metadata is None
