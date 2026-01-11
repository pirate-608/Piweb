import ctypes
import os
import sys

class AnalyzerService:
    def __init__(self, dll_path):
        self.lib = None
        self.dll_path = dll_path
        self._load_library()

    def _load_library(self):
        print(f"AnalyzerService: loading DLL from {self.dll_path}")
        try:
            self.lib = ctypes.CDLL(self.dll_path)
            # int analyze_text(const char* content, char* out_json, int out_size);
            self.lib.analyze_text.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
            self.lib.analyze_text.restype = ctypes.c_int
            print(f"Successfully loaded analyzer DLL from {self.dll_path}")
        except Exception as e:
            import traceback
            print(f"Error loading analyzer DLL: {e}\n{traceback.format_exc()}")
            self.lib = None

    def analyze(self, content: str) -> dict:
        print(f"AnalyzerService: analyze called, content length={len(content)}")
        if not self.lib:
            print("AnalyzerService: library not loaded")
            return {"ok": False, "msg": "Analyzer library not loaded"}
        out_buf = ctypes.create_string_buffer(8192)
        content_bytes = content.encode('utf-8')
        try:
            ret = self.lib.analyze_text(content_bytes, out_buf, 8192)
            print(f"AnalyzerService: analyze_text returned {ret}")
        except Exception as e:
            import traceback
            print(f"AnalyzerService: analyze_text exception: {e}\n{traceback.format_exc()}")
            return {"ok": False, "msg": f"Analyzer call exception: {e}"}
        if ret != 0:
            print("AnalyzerService: analyze_text call failed")
            return {"ok": False, "msg": "Analyzer call failed"}
        import json
        try:
            data = json.loads(out_buf.value.decode('utf-8'))
            print(f"AnalyzerService: JSON decoded {data}")
        except Exception as e:
            import traceback
            print(f"AnalyzerService: JSON decode failed: {e}\n{traceback.format_exc()}")
            return {"ok": False, "msg": f"JSON decode failed: {e}"}
        # 结果格式标准化
        # sections字段兼容字符串和对象
        sections = data.get("sections", [])
        if isinstance(sections, str):
            import json as _json
            try:
                sections = _json.loads(sections)
            except Exception:
                sections = []
        result = {
            "ok": True,
            "words": data.get("words", 0),
            "cn_chars": data.get("cn_chars", 0),
            "en_words": data.get("en_words", 0),
            "richness": data.get("richness", 0),
            "top_words": data.get("top_words", ""),
            "sensitive_words": data.get("sensitive_words", ""),
            "sections": sections,
        }
        print(f"AnalyzerService: result {result}")
        return result
