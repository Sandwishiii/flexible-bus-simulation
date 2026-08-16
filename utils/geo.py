"""
地理计算工具
"""
import math


def haversine_distance(lng1, lat1, lng2, lat2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calc_bearing(lng1, lat1, lng2, lat2):
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlambda = math.radians(lng2 - lng1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def point_in_radius(lng, lat, radius_m):
    import random
    R = 6371000
    d = random.uniform(0, radius_m)
    theta = random.uniform(0, 2 * math.pi)
    dlat = d * math.cos(theta) / R
    dlng = d * math.sin(theta) / (R * math.cos(math.radians(lat)))
    return lng + math.degrees(dlng), lat + math.degrees(dlat)
