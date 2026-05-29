# app/hotel_map.py
# Resolución de sociedades a partir de hotel/UE o lista explícita

HOTEL_TO_SOC = {
    "Maya": ["5600", "5601", "5602", "5603", "5604", "5606", "6300", "7000", "P300"],
    "Bavaro": ["7400", "7401", "7402", "7601", "7800", "7801", "J400"],
    "Sants": ["8504"],
    "Punta Umbria Beach": ["3200", "3201"],
    "Illetas Albatros": ["1001"],
    # añadir todas
}


def resolve_sociedades(hotel: str | None, sociedades: list[str] | None) -> list[str]:
    """
    Resuelve la lista final de sociedades a consultar.

    Prioridad:
    1. Si el request trae sociedades explícitas, se usan esas.
    2. Si no, se intenta resolver a partir del hotel/UE.
    """
    if sociedades:
        return [str(s).strip().upper() for s in sociedades]

    if hotel:
        key = hotel.strip()

        if key in HOTEL_TO_SOC:
            return HOTEL_TO_SOC[key]

        for k, v in HOTEL_TO_SOC.items():
            if k.lower() == key.lower():
                return v

        raise ValueError(f"Hotel no reconocido: {hotel}")

    raise ValueError("Debes informar 'sociedades' o 'hotel'")