import os
import dashscope
from dashscope import Generation
import contextvars

_raw_key = os.getenv('DASHSCOPE_API_KEY')
DASHSCOPE_API_KEY = _raw_key.strip() if _raw_key else None
# 用 contextvars 隔离 dashscope.api_key，防止多线程/异步串用
_api_key_ctx = contextvars.ContextVar('dashscope_api_key', default=DASHSCOPE_API_KEY)

class AIWriter:
    def __init__(self, api_key=None):
        key = api_key.strip() if api_key else None
        self.api_key = key or DASHSCOPE_API_KEY
        if self.api_key:
            self.api_key = self.api_key.strip()
        print(f"[AIWriter] 初始化, api_key={'已设置' if self.api_key else '未设置'}")

    def continue_text(self, prompt, max_tokens=300, temperature=0.7, model='qwen-turbo', fact=None):
        # 支持结构化prompt（dict），fact为事实增强内容
        if isinstance(prompt, dict):
            # 结构化prompt，优先使用content、facts、restrict字段
            content = prompt.get('content', '')
            facts = prompt.get('facts', '')
            restrict = prompt.get('restrict', '')
            continue_prompt = (
                f"input:\n{content}\n\nfact:\n{facts}\n\n{restrict if restrict else '请基于上述事实和输入内容续写后续内容，不要重复已有内容，只输出新增部分。'}"
            )
        else:
            if fact:
                continue_prompt = (
                    f"input:\n{prompt.strip()}\n\nfact:\n{fact}\n\n请基于上述事实和输入内容续写后续内容，不要重复已有内容，只输出新增部分。"
                )
            else:
                continue_prompt = (
                    f"以下是需要续写的内容：\n" +
                    prompt.strip() +
                    "\n\n请你只续写后续内容，不要重复已有内容，不要输出任何与已有内容重复的句子或段落，只输出新增部分。"
                )
        print(f"[AIWriter] 调用参数: prompt={continue_prompt[:80]}... max_tokens={max_tokens} temperature={temperature} model={model}")
        token = _api_key_ctx.set(self.api_key.strip() if self.api_key else self.api_key)
        try:
            dashscope.api_key = _api_key_ctx.get()
            print(f"[AIWriter] dashscope.api_key={'已设置' if dashscope.api_key else '未设置'}")
            response = Generation.call(
                model=model,
                prompt=continue_prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
            print(f"[AIWriter] dashscope 返回: {response}")
            # 兼容 code 为空但 status_code=200 且 output.text 存在的情况
            if (
                (response.get('code', 0) == 200)
                or (response.get('status_code') == 200 and response.get('output', {}).get('text'))
            ):
                ai_text = response['output']['text']
                # 后端自动去除与 prompt 重复部分，仅保留新增内容
                cleaned = self._remove_prompt_prefix(ai_text, prompt)
                return cleaned
            else:
                print("[AIWriter] dashscope 返回异常，完整内容如下：")
                try:
                    import json
                    print(json.dumps(response, ensure_ascii=False, indent=2))
                except Exception as e:
                    print(f"[AIWriter] response 转 json 失败: {e}, 原始内容: {response}")
                raise Exception(response.get('msg', f"AI续写失败 (code={response.get('code')})"))
        except Exception as e:
            print(f"[AIWriter] 发生异常: {e}")
            import traceback
            print(traceback.format_exc())
            raise
        finally:
            _api_key_ctx.reset(token)

    @staticmethod
    def _remove_prompt_prefix(ai_text, prompt):
        """
        去除 AI 返回内容中与 prompt 重复的前缀，仅保留新增部分。
        支持中英文，自动忽略空白和换行。
        支持结构化prompt（dict），自动提取content字段。
        """
        import re
        # 如果prompt为dict，优先用content字段
        if isinstance(prompt, dict):
            prompt_str = prompt.get('content', '')
        else:
            prompt_str = prompt
        def normalize(s):
            return re.sub(r'[\s\u3000]+', '', s or '')
        norm_prompt = normalize(prompt_str)
        norm_ai = normalize(ai_text)
        # 找到 prompt 在 ai_text 中的最后一次出现位置
        idx = norm_ai.find(norm_prompt)
        if idx != -1:
            # 计算原始 ai_text 中对应的结束位置
            # 由于去除了空白，需逆向定位
            def find_end(orig, norm):
                i = j = 0
                while i < len(orig) and j < len(norm):
                    if orig[i] in '\r\n \t\u3000':
                        i += 1
                    elif orig[i] == norm[j]:
                        i += 1
                        j += 1
                    else:
                        i += 1
                return i
            end_pos = find_end(ai_text, norm_prompt)
            return ai_text[end_pos:].lstrip('\r\n \t\u3000')
        # 若未找到，直接返回原文
        return ai_text
