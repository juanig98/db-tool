from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FieldRule:
    field_pattern: re.Pattern[str]
    value_pattern: re.Pattern[str] | None
    faker_type: str
    source: str = "fixed"


# Field name patterns → faker provider
_FIXED_RULES: list[tuple[str, str | None, str]] = [
    # emails
    (r".*email.*", r".+@.+", "email"),
    (r".*e_mail.*", r".+@.+", "email"),
    # names
    (r"^(first_?name|firstName|given_?name)$", None, "first_name"),
    (r"^(last_?name|lastName|family_?name|surname)$", None, "last_name"),
    (r"^(full_?name|fullName|nombre_completo)$", None, "name"),
    (r"^(name|nombre)$", None, "name"),
    # phones
    (r".*phone.*", r"\d{5,}", "phone_number"),
    (r".*telefono.*", r"\d{5,}", "phone_number"),
    (r".*mobile.*", r"\d{5,}", "phone_number"),
    (r".*celular.*", r"\d{5,}", "phone_number"),
    # addresses
    (r"^(address|direccion|domicilio)$", None, "address"),
    (r"^(street|street_address|calle)$", None, "street_address"),
    (r"^(city|ciudad)$", None, "city"),
    (r"^(zip|zip_code|postal_code|codigo_postal)$", None, "postcode"),
    # identity docs
    (r"^(dni|nid|cedula|document_number|id_number)$", None, "numerify"),
    (r"^(tax_id|fiscal_id|cuit|rfc|nif)$", None, "numerify"),
    # generic PII
    (r"^(birth_?date|birthDate|fecha_nacimiento)$", None, "date_of_birth"),
    (r"^(gender|sexo|genero)$", None, "random_element"),
]

FIXED_RULES: list[FieldRule] = [
    FieldRule(
        field_pattern=re.compile(field_pat, re.IGNORECASE),
        value_pattern=re.compile(val_pat, re.IGNORECASE) if val_pat else None,
        faker_type=faker_type,
        source="fixed",
    )
    for field_pat, val_pat, faker_type in _FIXED_RULES
]
