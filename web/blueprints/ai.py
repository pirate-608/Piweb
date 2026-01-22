from flask import Blueprint, request, jsonify
from web.services.ai_writer import AIWriter
from web.utils.cache import get_cache, set_cache

bp = Blueprint('ai', __name__, url_prefix='/api/ai')

@bp.route('/continue', methods=['POST'])
def ai_continue():
    data = request.json or {}
    prompt = data.get('prompt', '')
    max_tokens = int(data.get('max_tokens', 300))
    temperature = float(data.get('temperature', 0.7))
    cache_key = f"{prompt}|{max_tokens}|{temperature}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify({'text': cached, 'cached': True})
    import traceback
    try:
        writer = AIWriter()
        result = writer.continue_text(prompt, max_tokens, temperature)
        set_cache(cache_key, result)
        return jsonify({'text': result, 'cached': False})
    except Exception as e:
        print('[AI续写异常]', str(e))
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500
