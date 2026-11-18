from unittest.mock import Mock, patch

from google.genai import errors

from core.orchestrator import responder
import httpx

def _erro_503():
    return errors.ServerError(
        503,
        {
            "error": {
                "code": 503,
                "message": "High demand",
                "status": "UNAVAILABLE",
            }
        },
    )


def test_responder_retry_apos_503_e_depois_sucesso():
    chat = Mock()

    # Um Chat real recém-criado não possui fallback ativo.
    chat._sabor_chat_ativo = None

    resposta = Mock()
    resposta.text = "OK"

    chat.send_message.side_effect = [
        _erro_503(),
        resposta,
    ]

    with patch("core.orchestrator.time.sleep") as sleep:
        texto, chamadas = responder(chat, "Teste")

    assert texto == "OK"
    assert chamadas == []
    assert chat.send_message.call_count == 2
    sleep.assert_called_once()


def test_responder_usa_fallback_com_historico():
    chat_principal = Mock()

    chat_principal._sabor_chat_ativo = None
    chat_principal._sabor_modelo = "gemini-3.8-flash"
    chat_principal._sabor_ferramentas = ["ferramenta-teste"]

    chat_principal.send_message.side_effect = [
        _erro_503(),
        _erro_503(),
    ]

    historico = [
        {
            "role": "user",
            "parts": [{"text": "Quem possui certificação?"}],
        },
        {
            "role": "model",
            "parts": [{"text": "José possui certificação."}],
        },
    ]

    chat_principal.get_history.return_value = historico

    chat_fallback = Mock()
    chat_fallback._sabor_modelo = "gemini-3.1-flash-lite"
    chat_fallback._sabor_ferramentas = ["ferramenta-teste"]

    resposta_fallback = Mock()
    resposta_fallback.text = "Resposta pelo fallback"

    chat_fallback.send_message.return_value = resposta_fallback

    with (
        patch("core.orchestrator.time.sleep"),
        patch(
            "core.orchestrator.novo_chat",
            return_value=chat_fallback,
        ) as criar_fallback,
    ):
        texto, chamadas = responder(
            chat_principal,
            "E a Josefa?",
        )

    assert texto == "Resposta pelo fallback"
    assert chamadas == []

    assert chat_principal.send_message.call_count == 2
    chat_principal.get_history.assert_called_once_with()

    criar_fallback.assert_called_once_with(
        ["ferramenta-teste"],
        modelo="gemini-3.1-flash-lite",
        historico=historico,
    )

    chat_fallback.send_message.assert_called_once_with(
        "E a Josefa?"
    )

    # O fallback passa a ser o chat ativo desta sessão.
    assert chat_principal._sabor_chat_ativo is chat_fallback


def test_proxima_mensagem_continua_no_mesmo_fallback():
    chat_principal = Mock()
    chat_fallback = Mock()

    # Simula uma sessão em que o fallback já foi ativado anteriormente.
    chat_principal._sabor_chat_ativo = chat_fallback

    chat_fallback._sabor_modelo = "gemini-3.1-flash-lite"
    chat_fallback._sabor_ferramentas = ["ferramenta-teste"]

    resposta = Mock()
    resposta.text = "Continuei no fallback"

    chat_fallback.send_message.return_value = resposta

    texto, chamadas = responder(
        chat_principal,
        "E quais produtos ela possui?",
    )

    assert texto == "Continuei no fallback"
    assert chamadas == []

    # Não deve voltar ao modelo principal.
    chat_principal.send_message.assert_not_called()

    # A nova mensagem continua no mesmo objeto Chat de fallback.
    chat_fallback.send_message.assert_called_once_with(
        "E quais produtos ela possui?"
    )


def test_responder_usa_fallback_apos_timeouts():
    chat_principal = Mock()

    chat_principal._sabor_chat_ativo = None
    chat_principal._sabor_modelo = "gemini-3.8-flash"
    chat_principal._sabor_ferramentas = ["ferramenta-teste"]

    chat_principal.send_message.side_effect = [
        httpx.ReadTimeout("Timeout no modelo principal"),
        httpx.ReadTimeout("Timeout no modelo principal"),
    ]

    historico = [
        {
            "role": "user",
            "parts": [{"text": "Pergunta anterior"}],
        },
        {
            "role": "model",
            "parts": [{"text": "Resposta anterior"}],
        },
    ]

    chat_principal.get_history.return_value = historico

    chat_fallback = Mock()
    chat_fallback._sabor_modelo = "gemini-3.1-flash-lite"
    chat_fallback._sabor_ferramentas = ["ferramenta-teste"]

    resposta = Mock()
    resposta.text = "Resposta após timeout"
    chat_fallback.send_message.return_value = resposta

    with (
        patch("core.orchestrator.time.sleep"),
        patch(
            "core.orchestrator.novo_chat",
            return_value=chat_fallback,
        ),
    ):
        texto, chamadas = responder(
            chat_principal,
            "Teste de timeout",
        )

    assert texto == "Resposta após timeout"
    assert chamadas == []
    assert chat_principal.send_message.call_count == 2
    assert chat_principal._sabor_chat_ativo is chat_fallback


def _erro_504():
    return errors.ServerError(
        504,
        {
            "error": {
                "code": 504,
                "message": "Deadline expired before operation could complete.",
                "status": "DEADLINE_EXCEEDED",
            }
        },
    )

def test_fallback_tambem_faz_retry_apos_504():
    chat_principal = Mock()

    chat_principal._sabor_chat_ativo = None
    chat_principal._sabor_modelo = "gemini-3.8-flash"
    chat_principal._sabor_ferramentas = ["ferramenta-teste"]

    # Principal falha nas duas tentativas.
    chat_principal.send_message.side_effect = [
        _erro_503(),
        _erro_503(),
    ]

    chat_principal.get_history.return_value = []

    chat_fallback = Mock()
    chat_fallback._sabor_modelo = "gemini-3.1-flash-lite"
    chat_fallback._sabor_ferramentas = ["ferramenta-teste"]

    resposta = Mock()
    resposta.text = "Fallback recuperado"

    # Primeira tentativa do fallback recebe 504;
    # segunda tentativa funciona.
    chat_fallback.send_message.side_effect = [
        _erro_504(),
        resposta,
    ]

    with (
        patch("core.orchestrator.time.sleep"),
        patch(
            "core.orchestrator.novo_chat",
            return_value=chat_fallback,
        ),
    ):
        texto, chamadas = responder(
            chat_principal,
            "Teste de 504 no fallback",
        )

    assert texto == "Fallback recuperado"
    assert chamadas == []

    assert chat_principal.send_message.call_count == 2
    assert chat_fallback.send_message.call_count == 2
    assert chat_principal._sabor_chat_ativo is chat_fallback