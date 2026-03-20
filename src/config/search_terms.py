"""Three layers of search terms for finding niche SMEs."""

LAYER_1_MALAY_ENGLISH: list[str] = [
    "kedai", "workshop", "enterprise", "trading", "sdn bhd", "supplier",
    "repair", "services", "bengkel", "perkhidmatan", "pembekal", "pembaikan",
    "pembinaan", "paip", "elektrik", "jahit", "dobi", "cat", "bunga", "ukir",
    "contractor", "fabrication", "installation", "maintenance", "hardware",
    "spare parts", "printing", "signage", "cleaning", "pest control",
    "catering", "courier", "wholesale", "distributor", "manufacturer",
]

LAYER_2_CHINESE: list[str] = [
    "公司", "行", "店", "五金", "工程", "建筑", "装修", "电器", "机械",
    "汽车", "印刷", "冷气", "水管", "玻璃", "铁", "木", "漆", "布", "花", "食",
]

LAYER_3_TRADE_INDUSTRY: list[str] = [
    # Manufacturing / industrial
    "welding", "soldering", "machining", "stamping", "casting", "aluminium",
    "stainless steel", "steel works", "rubber", "plastic", "packaging",
    "powder coating", "chrome plating", "galvanizing", "wire harness",
    "injection moulding",
    # Building trades
    "roofing", "ceiling", "tiling", "waterproofing", "flooring", "glazing",
    "scaffolding", "renovation", "interior design", "kitchen cabinet",
    "wardrobe", "gate grill", "awning",
    # Automotive
    "bodywork", "spray paint", "upholstery", "tint", "car wrapping",
    "car accessories", "tyre", "rim", "exhaust",
    # Niche services
    "embroidery", "engraving", "laminating", "bookbinding", "foam",
    "neon sign", "led sign", "banner printing", "timber", "carpet",
    "curtain", "uniform", "trophy", "rubber stamp", "key cutting", "locksmith",
]

ALL_LAYERS: dict[str, list[str]] = {
    "layer_1": LAYER_1_MALAY_ENGLISH,
    "layer_2": LAYER_2_CHINESE,
    "layer_3": LAYER_3_TRADE_INDUSTRY,
}


def get_terms(layers: list[str] | None = None) -> list[str]:
    """Return search terms for the specified layers. Defaults to all layers."""
    if layers is None:
        layers = list(ALL_LAYERS.keys())
    terms: list[str] = []
    for layer in layers:
        terms.extend(ALL_LAYERS[layer])
    return terms
