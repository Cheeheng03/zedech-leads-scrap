"""Search terms targeting established businesses with revenue but no proper website.

Target: B2B leads for Zedech AI automation & solutions.
Profile: Businesses with real revenue that would benefit from a landing page,
         AI automation, or digital presence. Not small walk-in shops.
"""

LAYER_1_HIGH_VALUE_SERVICES: list[str] = [
    # Construction & building (high-ticket, project-based)
    "contractor", "pembinaan", "renovation", "interior design",
    "construction company", "building contractor",
    # Registered businesses (revenue signal)
    "sdn bhd", "enterprise",
    # Trades that do quoting / project work
    "fabrication", "installation", "maintenance company",
    "pest control", "cleaning company",
    # Digital-ready services
    "aircond service", "electrical contractor", "plumber",
    "landscaping", "security company", "fire safety",
]

LAYER_2_HOSPITALITY_PROPERTY: list[str] = [
    # Airbnb / hospitality (high value, need booking pages)
    "homestay", "airbnb", "resort", "chalet", "villa",
    "guest house", "budget hotel",
    # Property services
    "property management", "real estate agent",
    # Events (need inquiry/booking pages)
    "event management", "event space", "wedding planner",
    "catering company", "canopy rental",
]

LAYER_3_INDUSTRIAL_MANUFACTURING: list[str] = [
    # Metal & fabrication (like the 70M aluminium gate business)
    "aluminium", "stainless steel", "steel works", "gate grill",
    "welding", "machining", "metal fabrication",
    "powder coating", "galvanizing",
    # Building materials & supply
    "kitchen cabinet", "wardrobe", "awning", "roofing",
    "ceiling", "tiling", "waterproofing", "flooring",
    "glass supplier", "timber supplier",
    # Automotive services (not retail)
    "bodywork", "spray paint", "car wrapping", "car detailing",
    "fleet management", "workshop",
    # Packaging & manufacturing
    "packaging", "manufacturer", "OEM", "printing company",
]

LAYER_4_PROFESSIONAL_NICHE: list[str] = [
    # Health & wellness (appointment-driven, need online presence)
    "clinic", "dental", "physiotherapy", "spa",
    "traditional medicine", "wellness center",
    # Education & training
    "tuition centre", "training centre", "driving school",
    # Professional services
    "accounting firm", "audit firm", "consultant",
    "engineering firm", "surveyor",
    # Logistics & transport
    "transport company", "logistics", "freight", "warehousing",
    "cold storage", "movers",
    # Niche high-value services
    "signage company", "signboard", "led sign",
    "embroidery", "uniform supplier", "trophy",
    "curtain", "carpet supplier",
    "CCTV", "alarm system", "automation",
]

ALL_LAYERS: dict[str, list[str]] = {
    "layer_1": LAYER_1_HIGH_VALUE_SERVICES,
    "layer_2": LAYER_2_HOSPITALITY_PROPERTY,
    "layer_3": LAYER_3_INDUSTRIAL_MANUFACTURING,
    "layer_4": LAYER_4_PROFESSIONAL_NICHE,
}


def get_terms(layers: list[str] | None = None) -> list[str]:
    """Return search terms for the specified layers. Defaults to all layers."""
    if layers is None:
        layers = list(ALL_LAYERS.keys())
    terms: list[str] = []
    for layer in layers:
        terms.extend(ALL_LAYERS[layer])
    return terms
