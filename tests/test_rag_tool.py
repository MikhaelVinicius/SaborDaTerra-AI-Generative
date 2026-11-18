from unittest.mock import patch

from sabor_rag.models import DocumentChunk, RetrievalHit
from sabor_rag.tool import TOOLS, consultar_documentos


def _hit(
    *,
    source_path="certificacoes/josefa_souza_P008.txt",
    category="certificacoes",
    score=0.7826,
):
    chunk = DocumentChunk(
        chunk_id="josefa_souza_P008::chunk-0000",
        document_id="josefa_souza_P008",
        text="Certificação vencida em 30/09/2026.",
        source_path=source_path,
        category=category,
        metadata={},
    )

    return RetrievalHit(
        chunk=chunk,
        score=score,
    )


def test_tool_is_exposed_to_orchestrator():
    assert TOOLS == [consultar_documentos]


def test_rejects_empty_question():
    result = consultar_documentos("")

    assert result["resultados"] == []
    assert "erro" in result


def test_rejects_invalid_category():
    result = consultar_documentos(
        "Consultar documento",
        categoria="dados_csv",
    )

    assert result["resultados"] == []
    assert "erro" in result


def test_rejects_invalid_k():
    result = consultar_documentos(
        "Consultar documento",
        k=0,
    )

    assert result["resultados"] == []
    assert "erro" in result


@patch("sabor_rag.tool.retrieve")
def test_returns_retrieved_document(mock_retrieve):
    mock_retrieve.return_value = [_hit()]

    result = consultar_documentos(
        "Qual a situação da certificação de Josefa?",
        categoria="certificacoes",
        k=5,
    )

    mock_retrieve.assert_called_once_with(
        "Qual a situação da certificação de Josefa?",
        top_k=5,
        categoria="certificacoes",
    )

    assert "erro" not in result
    assert len(result["resultados"]) == 1

    documento = result["resultados"][0]

    assert documento["fonte"] == "certificacoes/josefa_souza_P008.txt"
    assert len(documento["trechos"]) == 1
    assert documento["trechos"][0]["documento"] == "josefa_souza_P008"
    assert documento["trechos"][0]["categoria"] == "certificacoes"
    assert documento["trechos"][0]["score"] == 0.7826


@patch("sabor_rag.tool.retrieve")
def test_groups_chunks_from_same_source(mock_retrieve):
    mock_retrieve.return_value = [
        _hit(score=0.91),
        _hit(score=0.82),
    ]

    result = consultar_documentos(
        "Situação documental de Josefa"
    )

    assert len(result["resultados"]) == 1
    assert len(result["resultados"][0]["trechos"]) == 2


@patch("sabor_rag.tool.retrieve")
def test_returns_safe_response_when_no_hits(mock_retrieve):
    mock_retrieve.return_value = []

    result = consultar_documentos(
        "Informação inexistente"
    )

    assert result["resultados"] == []
    assert "erro" in result
    assert "Não invente" in result["erro"]


@patch("sabor_rag.tool.retrieve")
def test_handles_retrieval_failure(mock_retrieve):
    mock_retrieve.side_effect = RuntimeError(
        "falha simulada"
    )

    result = consultar_documentos(
        "Consultar certificação"
    )

    assert result["resultados"] == []
    assert "erro" in result
    assert "falha simulada" in result["erro"]