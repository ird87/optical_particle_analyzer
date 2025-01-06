import json
from .models import MICROSCOPES

def microscopes(request):
    microscopes_serialized = json.dumps([microscope.to_dict() for microscope in MICROSCOPES])
    return {'microscopes': microscopes_serialized}
