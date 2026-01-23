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
    web_search = data.get('web_search', False)
    cache_key = f"{prompt}|{max_tokens}|{temperature}|{web_search}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify({'text': cached, 'cached': True})
    import traceback
    try:
        facts = None
        if web_search:
            # 1. 先用qwen-flash结构化生成事实
            writer = AIWriter()
            fact_prompt = f"请基于以下文本，搜索并输出与之相关的最新事实，要求结构化输出JSON，字段为 facts: [ ... ]。\n文本：{prompt}"
            fact_resp = writer.continue_text(fact_prompt, max_tokens=256, temperature=0.2, model='qwen-flash')
            import json
            try:
                fact_json = json.loads(fact_resp)
                facts = fact_json.get('facts', [])
                fact_str = '\n'.join(facts) if isinstance(facts, list) else str(facts)
            except Exception:
                fact_str = fact_resp
                facts = fact_resp
            # 2. 用结构化prompt续写，加入restrict字段，约束模型只续写正文内容
            restrict = "仅续写正文内容，不要重复已有内容，不要生成独立段落或总结，不要输出代码块以外的说明。"
            struct_prompt = {
                "content": prompt,
                "facts": fact_str,
                "restrict": restrict
            }
            result = writer.continue_text(struct_prompt, max_tokens, temperature, model='qwen-flash')
        else:
            writer = AIWriter()
            result = writer.continue_text(prompt, max_tokens, temperature)
        set_cache(cache_key, result)
        return jsonify({'text': result, 'facts': facts, 'cached': False})
    except Exception as e:
        print('[AI续写异常]', str(e))
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500
