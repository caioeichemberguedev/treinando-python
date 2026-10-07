"""Sessão da área adm (`/admin`) usando só a biblioteca padrão.

Decisão 6 do ID-008 (ver `docs/backlog.md`):

- A senha vem da variável de ambiente `ADMIN_SENHA`, lida a cada chamada
  (nunca guardada em variável global). Ausente ou vazia → área desligada.
- A comparação da senha usa `secrets.compare_digest`, que leva o mesmo
  tempo independente de onde os textos diferem (comparar com `==` vaza, pelo
  tempo de resposta, quantos caracteres do início estão certos).
- O token do cookie é `"<expira_em_segundos>.<assinatura_hex>"`, assinado
  com HMAC-SHA256 sobre `f"{expira}|{sha256(senha)}"` usando `CHAVE`, gerada
  aleatoriamente ao importar o módulo. Consequências: reiniciar o servidor
  desloga; trocar `ADMIN_SENHA` invalida tokens antigos; o token não carrega
  a senha (nem o hash dela), só a expiração e a assinatura.

A senha nunca vai para token, log ou mensagem de erro.
"""

import hashlib
import hmac
import os
import secrets
import time

COOKIE_SESSAO = "sessao_admin"
DURACAO_SESSAO = 8 * 60 * 60  # 8 horas, em segundos

# Expiração em segundos desde 1970: 12 dígitos cobrem até o ano ~33658.
# Limitar antes do `int()` evita o `ValueError` do limite de dígitos do
# Python (e trabalho à toa) com tokens gigantes vindos do cookie.
MAX_DIGITOS_EXPIRACAO = 12

CHAVE = secrets.token_bytes(32)


def _senha_admin() -> str:
    """Senha configurada no servidor, ou `""` se não houver.

    Só espaços ou caractere que não codifica em UTF-8 contam como "sem
    senha" (área desligada): é configuração inválida, e desligar é o lado
    seguro.
    """
    senha = os.environ.get("ADMIN_SENHA", "")
    if not senha.strip():
        return ""
    try:
        senha.encode("utf-8")
    except UnicodeEncodeError:
        return ""
    return senha


def area_admin_ativa() -> bool:
    """`True` só quando `ADMIN_SENHA` está definida e não vazia."""
    return bool(_senha_admin())


def senha_confere(tentativa: str) -> bool:
    """Compara a tentativa com `ADMIN_SENHA` em tempo constante.

    Sempre `False` com a área desligada ou tentativa vazia.
    """
    senha = _senha_admin()
    if not senha or not tentativa:
        return False
    try:
        bytes_tentativa = tentativa.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return secrets.compare_digest(bytes_tentativa, senha.encode("utf-8"))


def _assinatura(expira: int, senha: str) -> str:
    """HMAC-SHA256 (hex) de `expira` + hash da senha atual."""
    hash_senha = hashlib.sha256(senha.encode("utf-8")).hexdigest()
    mensagem = f"{expira}|{hash_senha}".encode("utf-8")
    return hmac.new(CHAVE, mensagem, "sha256").hexdigest()


def criar_token_sessao(agora: float | None = None) -> str:
    """Cria um token válido por `DURACAO_SESSAO` segundos a partir de `agora`.

    Só deve ser chamado depois de `senha_confere` dar `True`. Com a área
    desligada levanta `RuntimeError` (sem token possível sem senha).
    """
    senha = _senha_admin()
    if not senha:
        raise RuntimeError("Área adm desligada: ADMIN_SENHA não definida.")
    if agora is None:
        agora = time.time()
    expira = int(agora) + DURACAO_SESSAO
    return f"{expira}.{_assinatura(expira, senha)}"


def token_sessao_valido(token: str | None, agora: float | None = None) -> bool:
    """`True` se o token foi assinado por este servidor, com a senha atual,
    e ainda não expirou. Tokens malformados dão `False` sem exceção.
    """
    senha = _senha_admin()
    if not senha or not token:
        return False

    partes = token.split(".")
    if len(partes) != 2:
        return False
    texto_expira, assinatura = partes
    if len(texto_expira) > MAX_DIGITOS_EXPIRACAO:
        return False
    if not (texto_expira.isascii() and texto_expira.isdigit()):
        return False
    if not assinatura.isascii():
        return False

    expira = int(texto_expira)
    esperada = _assinatura(expira, senha)
    if not secrets.compare_digest(assinatura, esperada):
        return False

    if agora is None:
        agora = time.time()
    return agora < expira
