"""Orquestrador: um chat Gemini com as ferramentas de todos os módulos.

Responsável: Engenheiro(a) Cloud & Fullstack / DevOps.

O histórico da sessão fica no objeto Chat (um por usuário/aba do Streamlit),
incluindo as chamadas e resultados de ferramentas: é isso que mantém o
contexto da conversa (requisito funcional).

O prompt de sistema é do(a) Arquiteto(a) de Prompts: basta salvar o texto em
prompts/system_prompt.md (ou apontar SYSTEM_PROMPT_FILE). Enquanto o arquivo
não existir, usamos o prompt mínimo de integração abaixo.
"""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path
import httpx
from google.genai import errors, types

from core import config
from core.integracao import Rastreio, carregar_ferramentas
from core.llm import get_client


PROMPT_INTEGRACAO = """Você é o assistente da Cooperativa Sabor da Terra. Hoje é {hoje}.
Use as ferramentas disponíveis para responder; não invente informações.
Se nenhuma ferramenta trouxer a resposta, diga claramente que não encontrou.
Quando uma ferramenta devolver fontes, cite-as.
Considere o histórico desta conversa ao interpretar a pergunta.
Responda em português do Brasil."""


def system_prompt() -> str:
    arq = Path(config.SYSTEM_PROMPT_FILE)

    texto = (
        arq.read_text(encoding="utf-8")
        if arq.exists()
        else PROMPT_INTEGRACAO
    )

    return texto.replace(
        "{hoje}",
        date.today().strftime("%d/%m/%Y"),
    )


def novo_chat(
    ferramentas: list,
    modelo: str | None = None,
    historico: list | None = None,
):
    """Cria um chat Gemini com ferramentas e histórico opcionais."""
    modelo_escolhido = modelo or config.GEMINI_MODEL

    chat = get_client().chats.create(
        model=modelo_escolhido,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt(),
            temperature=config.TEMPERATURE,
            tools=ferramentas or None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                maximum_remote_calls=config.MAX_CHAMADAS_FERRAMENTAS
            ),
        ),
        history=historico,
    )

    # Metadados usados para recriar a conversa em caso de fallback.
    chat._sabor_ferramentas = ferramentas
    chat._sabor_modelo = modelo_escolhido

    return chat


def _eh_erro_transitorio(exc: Exception) -> bool:
    """Identifica falhas temporárias que justificam retry/fallback."""
    if isinstance(exc, httpx.TimeoutException):
        return True

    codigo = getattr(exc, "code", None)
    return codigo in {500, 502, 503, 504}


def _enviar_com_retry(chat, mensagem: str):
    """Envia uma mensagem aplicando o retry curto configurado."""
    ultima_excecao = None

    for tentativa in range(config.GEMINI_MAX_RETRIES + 1):
        try:
            with Rastreio() as chamadas:
                resp = chat.send_message(mensagem)

            return resp, chamadas

        except (errors.ServerError, httpx.TimeoutException) as exc:
            # Erros fora da política de resiliência devem continuar
            # sendo propagados imediatamente.
            if not _eh_erro_transitorio(exc):
                raise

            ultima_excecao = exc

            if tentativa < config.GEMINI_MAX_RETRIES:
                time.sleep(config.GEMINI_RETRY_DELAY_SECONDS)

    if ultima_excecao is not None:
        raise ultima_excecao

    raise RuntimeError(
        "Não foi possível obter resposta do modelo."
    )


def responder(chat, mensagem: str) -> tuple[str, list[dict]]:
    """Envia a mensagem com retry curto e fallback automático de modelo."""

    # Se esta sessão já ativou um fallback anteriormente,
    # continua usando o mesmo chat.
    chat_ativo = getattr(chat, "_sabor_chat_ativo", None) or chat

    try:
        resp, chamadas = _enviar_com_retry(
            chat_ativo,
            mensagem,
        )

        return (
            resp.text
            or "Não consegui gerar uma resposta. Tente reformular.",
            chamadas,
        )

    except (errors.ServerError, httpx.TimeoutException) as exc:
        # Só erros transitórios podem provocar troca de modelo.
        if not _eh_erro_transitorio(exc):
            raise

    # O modelo ativo continuou indisponível após os retries.
    modelo_atual = getattr(
        chat_ativo,
        "_sabor_modelo",
        config.GEMINI_MODEL,
    )

    # Só troca para o fallback se ainda não estivermos nele.
    if (
        config.GEMINI_FALLBACK_MODEL
        and modelo_atual != config.GEMINI_FALLBACK_MODEL
    ):
        ferramentas = getattr(
            chat_ativo,
            "_sabor_ferramentas",
            [],
        )

        # Preserva o histórico ao trocar de modelo.
        historico = chat_ativo.get_history()

        chat_fallback = novo_chat(
            ferramentas,
            modelo=config.GEMINI_FALLBACK_MODEL,
            historico=historico,
        )

        # Mantém o fallback ativo nas próximas mensagens da sessão.
        chat._sabor_chat_ativo = chat_fallback

        # O fallback recebe exatamente a mesma política de retry.
        resp, chamadas = _enviar_com_retry(
            chat_fallback,
            mensagem,
        )

        return (
            resp.text
            or "Não consegui gerar uma resposta. Tente reformular.",
            chamadas,
        )

    # Se o próprio fallback esgotou seus retries,
    # _enviar_com_retry já propagou a última exceção.
    raise RuntimeError(
        "Não foi possível obter resposta do modelo."
    )


__all__ = [
    "carregar_ferramentas",
    "novo_chat",
    "responder",
    "system_prompt",
]