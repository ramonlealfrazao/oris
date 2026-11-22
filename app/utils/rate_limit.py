import time
from threading import Lock

JANELA_SEGUNDOS = 5 * 60
LIMITE_TENTATIVAS = 5

MAX_CHAVES = 10_000

_tentativas = {}
_lock = Lock()


def _chave(ip, email):
    return (ip or "desconhecido", (email or "").strip().lower())


def _recentes(tentativas, agora):
    return [t for t in tentativas if agora - t < JANELA_SEGUNDOS]


def _purgar(agora):
    for chave in [c for c, ts in _tentativas.items() if not _recentes(ts, agora)]:
        del _tentativas[chave]

    excesso = len(_tentativas) - (MAX_CHAVES - 1)
    if excesso > 0:
        mais_antigas = sorted(_tentativas, key=lambda c: max(_tentativas[c]))[:excesso]
        for chave in mais_antigas:
            del _tentativas[chave]


def registrar_tentativa_falha(ip, email):
    agora = time.time()
    with _lock:
        chave = _chave(ip, email)
        if chave not in _tentativas and len(_tentativas) >= MAX_CHAVES:
            _purgar(agora)
        _tentativas[chave] = _recentes(_tentativas.get(chave, []), agora) + [agora]


def limpar_tentativas(ip, email):
    with _lock:
        _tentativas.pop(_chave(ip, email), None)


def bloqueado(ip, email):
    agora = time.time()
    with _lock:
        chave = _chave(ip, email)
        tentativas_recentes = _recentes(_tentativas.get(chave, []), agora)
        if tentativas_recentes:
            _tentativas[chave] = tentativas_recentes
        else:
            _tentativas.pop(chave, None)
        return len(tentativas_recentes) >= LIMITE_TENTATIVAS
