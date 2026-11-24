"""Источник расстояний. Пока — по прямой с поправочным коэффициентом;
в блоке «Рейсы» добавится OSRM (шаблон «Стратегия», рисунок 2.12)."""
import math

ROAD_FACTOR = 1.3


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class HaversineProvider:
    def distance_km(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        return round(haversine_km(*a, *b) * ROAD_FACTOR, 1)


provider = HaversineProvider()
