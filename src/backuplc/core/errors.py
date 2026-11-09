class BackupLcError(Exception):
    """Erro base da aplicação."""


class ConfigError(BackupLcError):
    """Configuração ausente ou inválida. A mensagem cita a variável, nunca o valor."""


class DuplicateError(BackupLcError):
    """Tentativa de criar um recurso com chave que já existe."""
