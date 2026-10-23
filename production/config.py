"""Configuration files use the JSON subset of YAML 1.2; no YAML dependency."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def load(name):
    data = json.loads((ROOT / name).read_text(encoding='utf-8'))
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported schema_version')
    return data

def categories():
    return load('production_rules.yaml')['categories']

def normalize_category(value):
    for key, rule in categories().items():
        if value in [key, rule['name'], *rule['aliases']]:
            return key
    raise ValueError('Unknown category: ' + str(value))

def template(template_id):
    for entry in load('template_catalog.yaml')['templates']:
        if entry['id'] == template_id:
            return entry
    raise ValueError('Unknown template: ' + str(template_id))
