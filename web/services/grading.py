import ctypes
import sys
import os

class GradingService:
    def __init__(self, dll_path):
        self.lib = None
        self.dll_path = dll_path
        self._load_library()

    def _load_library(self):
        try:
            self.lib = ctypes.CDLL(self.dll_path)
            # int calculate_score(const char* user_ans, const char* correct_ans, int full_score);
            self.lib.calculate_score.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
            self.lib.calculate_score.restype = ctypes.c_int
            print(f"Successfully loaded DLL from {self.dll_path}")
        except Exception as e:
            print(f"Error loading DLL: {e}")
            self.lib = None

    def calculate_score(self, user_ans_bytes, correct_ans_bytes, full_score):
        """
        Wraps the C library call.
        Expects bytes for user_ans and correct_ans.
        Returns score (int).
        """
        if not self.lib:
            # Fallback logic if library not loaded? 
            # Or just return 0? Or raise?
            # Assuming fallback logic is handled by caller (QueueManager) if specific logic needed,
            # but usually exact match fallback is simple.
            # Here we just implement the C call wrapper.
            # If C lib is missing, maybe return -1 to signal caller to use Python fallback?
            # Existing specific logic in GradingQueue handles "if self.lib" check.
            # So if this method is called, self.lib might be None.
            return 0 
        
        return self.lib.calculate_score(user_ans_bytes, correct_ans_bytes, full_score)

    def is_available(self):
        return self.lib is not None
