import json
from .models import MICROSCOPES, DIVISION_PRICES

def microscopes(request):
    microscopes_serialized = json.dumps([microscope.to_dict() for microscope in MICROSCOPES])
    return {'microscopes': microscopes_serialized}

def division_prices(request):
    division_prices_serialized = json.dumps([division_price.to_dict() for division_price in DIVISION_PRICES])
    return {'division_prices': division_prices_serialized}
