# polycell: urn=urn:wm:cell:shop:customer.validate:v1 contract=021800618efc
# Komórka logiki. Jeden plik = jedna funkcja `run`. Nie importuje transportu ani DB.
import re

from polycell_types import CustomerValidateInput, CustomerValidateOutput

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$")


def run(input: CustomerValidateInput) -> CustomerValidateOutput:
    errors: list[str] = []
    email = input["email"].strip().lower()
    country = input["country"].strip().upper()
    if not input["name"].strip():
        errors.append("name_required")
    if not EMAIL.match(email):
        errors.append("email_invalid")
    if not re.fullmatch(r"[A-Z]{2}", country):
        errors.append("country_invalid")
    return {"valid": not errors, "errors": errors, "normalized_email": email, "country": country}
