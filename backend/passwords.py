def generar_password_secuencial(indice: int) -> str:
    if not 1 <= indice <= 999999:
        raise ValueError("El índice debe estar entre 1 y 999999")
    return f"{indice:06d}"
