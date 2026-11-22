import uuid

from flask import current_app

from app.utils.datetime_utils import utcnow
from app.utils.integridade import sha256_base64, sha256_hex


class ArmazenamentoError(Exception):
    pass


def s3_configurado(config=None):
    config = config if config is not None else current_app.config
    return bool(config.get("S3_BUCKET"))


def _criar_cliente(config):
    import boto3

    opcoes = {}
    if config.get("S3_REGION"):
        opcoes["region_name"] = config["S3_REGION"]
    if config.get("S3_ENDPOINT_URL"):
        opcoes["endpoint_url"] = config["S3_ENDPOINT_URL"]
    return boto3.client("s3", **opcoes)


def montar_chave(entidade, config=None):
    config = config if config is not None else current_app.config
    prefixo = (config.get("S3_PREFIX") or "").strip("/")
    carimbo = utcnow().strftime("%Y/%m/%d")
    nome = f"{entidade}-{utcnow().strftime('%H%M%S')}-{uuid.uuid4().hex[:12]}.csv"
    return "/".join(parte for parte in (prefixo, entidade, carimbo, nome) if parte)


def enviar_relatorio(conteudo, entidade, cliente=None, config=None):
    config = config if config is not None else current_app.config
    if not s3_configurado(config):
        raise ArmazenamentoError("S3_BUCKET não configurado.")

    chave = montar_chave(entidade, config)
    try:
        cliente = cliente or _criar_cliente(config)
        cliente.put_object(
            Bucket=config["S3_BUCKET"],
            Key=chave,
            Body=conteudo,
            ContentType="text/csv; charset=utf-8",
            ServerSideEncryption="AES256",
            ChecksumAlgorithm="SHA256",
            ChecksumSHA256=sha256_base64(conteudo),
            Metadata={"sha256": sha256_hex(conteudo)},
        )
    except Exception as erro:
        current_app.logger.exception("Falha ao enviar relatório ao S3")
        raise ArmazenamentoError("Não foi possível enviar o relatório ao armazenamento.") from erro
    return chave


def gerar_url_download(chave, cliente=None, config=None):
    config = config if config is not None else current_app.config
    try:
        cliente = cliente or _criar_cliente(config)
        return cliente.generate_presigned_url(
            "get_object",
            Params={"Bucket": config["S3_BUCKET"], "Key": chave},
            ExpiresIn=int(config.get("S3_URL_EXPIRA_SEGUNDOS", 900)),
        )
    except Exception as erro:
        current_app.logger.exception("Falha ao gerar URL pré-assinada")
        raise ArmazenamentoError("Não foi possível gerar o link de download.") from erro
