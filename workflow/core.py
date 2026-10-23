import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Protocol


class ClassificationProvider(Protocol):
    def classify(self, query: str) -> dict: ...


class CopyProvider(Protocol):
    def supports(self, task: dict, classification: dict) -> bool: ...
    def generate(self, task: dict) -> dict: ...
from production.classifier import classify as baseline

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {'intro', 'procedure', 'recommendation', 'inventory', 'comparison', 'review'}
TEMPLATES = {'intro': 'customer-intro-v1', 'recommendation': 'customer-recommend-v1',
             'inventory': 'customer-list-v1', 'comparison': 'customer-compare-v1'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def task_input(value):
    if set(value) - {'task_id', 'query', 'direction'}:
        raise ValueError('INPUT_SCHEMA: unknown fields')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value.get('task_id', '')):
        raise ValueError('TASK_ID: invalid identifier')
    query = value.get('query')
    if not isinstance(query, str) or not query.strip():
        raise ValueError('QUERY: nonempty string required')
    if not isinstance(value.get('direction', ''), str):
        raise ValueError('DIRECTION: string required')
    match = re.search(r'[（(]([^（）()]*)[）)]\s*$', query)
    return {**value, 'direction': value.get('direction') or (match.group(1) if match else ''),
            'original_query': query, 'search_query': query[:match.start()].strip() if match else query.strip()}


class ModelClassifier:
    """Optional OpenAI-compatible endpoint; no credentials stored in reports."""
    def __init__(self, endpoint, model, key):
        if not endpoint.startswith('https://'):
            raise ValueError('MODEL_ENDPOINT: HTTPS required')
        self.endpoint, self.model, self.key = endpoint, model, key

    def classify(self, query):
        payload = {'model': self.model, 'temperature': 0, 'messages': [
            {'role': 'system', 'content': 'Return JSON only: category, confidence (0..1), reason. Categories: ' + ','.join(sorted(CATEGORIES))},
            {'role': 'user', 'content': query}]}
        request = urllib.request.Request(self.endpoint, json.dumps(payload).encode(),
            {'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        return json.loads(result['choices'][0]['message']['content'])


def classifier(query, provider=None):
    rules = baseline(query)
    # Explicit recommendation takes precedence over incidental “有哪些”.
    if '推荐' in query and set(rules['candidates']) <= {'recommendation', 'inventory'}:
        rules['category'] = 'recommendation'
        rules['reason'] = '明确推荐指令优先于枚举问法'
    result = {'category': rules['category'], 'confidence': .65 if rules['category'] else 0,
              'provider': 'rules_fallback', 'reason': rules['reason'], 'rules': rules,
              'review_required': True}
    if provider:
        try:
            prediction = provider.classify(query)
            confidence = prediction['confidence']
            if prediction['category'] not in CATEGORIES or isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1 or not isinstance(prediction['reason'], str):
                raise ValueError('invalid model schema')
            result.update(prediction, provider=type(provider).__name__,
                          review_required=confidence < .85 or prediction['category'] != rules['category'])
        except Exception as error:
            result['model_error'] = type(error).__name__  # Never expose credentials/server bodies.
    return result


def configured_model():
    values = [os.getenv('WORKFLOW_MODEL_' + key) for key in ['ENDPOINT', 'NAME', 'API_KEY']]
    return ModelClassifier(*values) if all(values) else None


def match_assets(registry, subject, purpose, minimum=(1, 1), authorized=True):
    matches = []
    for key, asset in registry.items():
        size = asset.get('size', [0, 0])
        path = (ROOT / asset['path']).resolve()
        if not path.is_relative_to(ROOT):
            continue
        if asset['subject'] != subject or purpose not in asset.get('purposes', []):
            continue
        if any(actual < required for actual, required in zip(size, minimum)):
            continue
        if authorized and asset.get('license_status') != 'authorized':
            continue
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == asset['sha256']:
            matches.append({'id': key, **asset})
    return matches


def verify_claims(claims, sources):
    errors = []
    for claim in claims:
        refs = claim.get('source_ids', [])
        valid = []
        for source_id in refs:
            source = sources.get(source_id, {})
            path = (ROOT / source.get('path', '__missing__')).resolve()
            if not path.is_relative_to(ROOT):
                continue
            if source.get('kind') != claim['kind'] or not source.get('locator') or not path.is_file():
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest() == source.get('sha256'):
                valid.append(source_id)
        if not valid:
            errors.append({'code': 'EVIDENCE_MISSING', 'claim': claim['id']})
    return errors


def safe_rework(document, attempt):
    """Only whitespace normalization is safe without editorial approval. Never truncate."""
    if attempt >= 3:
        return None
    changed = json.loads(json.dumps(document))
    for page in changed['pages']:
        for key, text in page['values'].items():
            page['values'][key] = '\n'.join(line.strip() for line in text.strip().splitlines())
    return changed if changed != document else None
