import os
import dashscope
from dashscope import Generation
import contextvars

DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
# 用 contextvars 隔离 dashscope.api_key，防止多线程/异步串用
_api_key_ctx = contextvars.ContextVar('dashscope_api_key', default=DASHSCOPE_API_KEY)

class AIWriter:
    def __init__(self, api_key=None):
        self.api_key = api_key or DASHSCOPE_API_KEY
        print(f"[AIWriter] 初始化, api_key={'已设置' if self.api_key else '未设置'}")

    def continue_text(self, prompt, max_tokens=300, temperature=0.7, model='qwen-turbo'):
        print(f"[AIWriter] 调用参数: prompt={prompt[:50]}... max_tokens={max_tokens} temperature={temperature} model={model}")
        token = _api_key_ctx.set(self.api_key)
        try:
            dashscope.api_key = _api_key_ctx.get()
            print(f"[AIWriter] dashscope.api_key={'已设置' if dashscope.api_key else '未设置'}")
            response = Generation.call(
                model=model,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
            print(f"[AIWriter] dashscope 返回: {response}")
            if response.get('code', 0) == 200:
                return response['output']['text']
            else:
                raise Exception(response.get('msg', 'AI续写失败'))
        except Exception as e:
            print(f"[AIWriter] 发生异常: {e}")
            import traceback
            print(traceback.format_exc())
            raise
        finally:
            _api_key_ctx.reset(token)
