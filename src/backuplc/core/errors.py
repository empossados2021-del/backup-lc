class BackupLcError(Exception):
    """Erro base da aplicação."""


class ConfigError(BackupLcError):
    """Configuração ausente ou inválida. A mensagem cita a variável, nunca o valor."""
