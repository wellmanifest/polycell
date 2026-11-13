"""Stary moduł (symulacja istniejącego projektu) - logika przemieszana z I/O."""
import json


def shipping_cost(weight_kg: float, country: str) -> float:
    """Koszt wysyłki wg starego cennika"""
    if country == "PL":
        return 9.99 if weight_kg <= 5 else 19.99
    return 29.99 if weight_kg <= 5 else 49.99


def report(path):
    with open(path) as f:
        data = json.load(f)
    return shipping_cost(data["w"], data["c"])
