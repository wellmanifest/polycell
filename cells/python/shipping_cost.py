# polycell: urn=urn:wm:cell:shop:shipping.cost:v1 contract=e41ae88b5509
# Zregenerowana komórka (zastępuje legacy_pricing.py:shipping_cost). Czysta funkcja.
from polycell_types import ShippingCostInput, ShippingCostOutput

RATES = {"PL": (9.99, 19.99)}
DEFAULT = (29.99, 49.99)


def run(input: ShippingCostInput) -> ShippingCostOutput:
    light, heavy = RATES.get(input["country"], DEFAULT)
    return {"result": light if input["weight_kg"] <= 5 else heavy}
